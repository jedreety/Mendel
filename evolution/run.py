"""Point d'entree de l'entrainement evolutif.

    python -m evolution.run                               nouveau run, configuration evolution/config.toml
    python -m evolution.run --config fichier.toml         nouveau run, autre configuration
    python -m evolution.run --reprendre runs/<dossier>    reprend un run a son dernier point de sauvegarde
    python -m evolution.run --a-blanc runs/<dossier>      run a blanc associe a un run reel
    python -m evolution.run --hasard runs/<dossier>       recherche aleatoire a budget egal

La reprise d'un run reel accepte --generations-max N, generation ou il s'arrete desormais (0 : pas de limite),
et --stagnation-max N, qui remplace stagnation_max de sa configuration pour cette reprise (0 le desactive).

Ctrl+C arrete le run a la fin de la generation en cours. Le bloc de test n'est jamais lu ici.

Trois fils de travail. Le fil principal enchaine les generations sur la GPU. Les rejeux exacts des entrants du
Pantheon, en decimal, tournent dans des processus a part, pendant les generations suivantes. Un fil d'ecriture
enregistre, dans l'ordre, la ligne de journal et le point de sauvegarde de chaque generation, une fois verifies
les rejeux des membres du Pantheon qu'il contient.
"""
import argparse
import copy
import json
import os
import queue
import shutil
import signal
import threading
import warnings
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore", message="Failed to initialize NumPy")  # PyTorch s'en passe tres bien
import torch  # noqa: E402

from evolution import checkpoint, gpu, philox, rejeu
from evolution.bilan import bilans
from evolution.config import lire
from evolution.contexte import ROOT, Contexte, empreinte_noyaux, maintenant, manifeste, preparer
from evolution.data import confirmation, fin_validation, lot, renouvellement, trimestres
from evolution.evaluation import COMPLETS_MAX, lignes
from evolution.fitness import COMPOSANTES, composantes, noter, parts
from evolution.genome import GROUPES
from evolution.pantheon import Membre, mettre_a_jour
from evolution.selection import distincts, enfants


class Arret:
    """Ctrl+C demande l'arret a la fin de la generation ; un second Ctrl+C interrompt sur-le-champ."""

    def __init__(self):
        self.demande = False
        signal.signal(signal.SIGINT, self._signal)

    def _signal(self, *_):
        if self.demande:
            raise KeyboardInterrupt
        self.demande = True
        print("\nArret demande : fin de la generation en cours, puis point de sauvegarde.", flush=True)


class Chrono:
    """Duree de chaque phase d'une generation, lue par l'adaptateur d'horloge."""

    def __init__(self, durees: dict):
        self.durees, self.depuis = durees, maintenant()

    def __call__(self, phase: str) -> None:
        torch.cuda.synchronize()
        instant = maintenant()
        self.durees[phase] = round((instant - self.depuis).total_seconds(), 2)
        self.depuis = instant


class Ecrivain:
    """Fil d'ecriture : pour chaque generation, dans l'ordre, sa ligne de journal et son point de sauvegarde.

    Un point de sauvegarde attend les rejeux d'admission des generations qui le precedent : il ne contient que
    des membres du Pantheon verifies. Un rejeu non conforme arrete l'ecriture ; le fil
    principal leve l'erreur a la generation suivante, et le dernier point de sauvegarde reste intact.
    """

    def __init__(self, dossier: Path):
        self.dossier = dossier
        self.file: queue.Queue = queue.Queue()
        self.erreur: BaseException | None = None
        self.rejeux: dict[str, list[dict]] = {}  # identifiant -> resume du rejeu de chaque trimestre
        self.fil = threading.Thread(target=self._boucle, name="ecrivain", daemon=True)
        self.fil.start()

    def poser(self, ligne: dict, etat: dict, attentes: dict[str, list[Future]]) -> None:
        """etat : copie du point de sauvegarde, que le fil principal ne touche plus."""
        self.file.put((ligne, etat, attentes))

    def verifier(self) -> None:
        if self.erreur is not None:
            raise RuntimeError("arret : un point de sauvegarde n'a pas pu etre ecrit") from self.erreur

    def terminer(self) -> None:
        """Attend l'ecriture de toutes les generations posees."""
        self.file.put(None)
        self.fil.join()
        self.verifier()

    def _boucle(self) -> None:
        while (travail := self.file.get()) is not None:
            if self.erreur is None:
                try:
                    self._ecrire(*travail)
                except BaseException as erreur:  # rendue au fil principal par verifier
                    self.erreur = erreur

    def _ecrire(self, ligne: dict, etat: dict, attentes: dict[str, list[Future]]) -> None:
        for identifiant, futurs in attentes.items():
            resumes = [futur.result() for futur in futurs]
            for r in resumes:
                if not r["conforme"]:
                    raise RuntimeError(f"rejeu non conforme : {identifiant}, {r['trimestre']}, ecart {r['ecart_max']} "
                                       f"a la barre {r['barre_ecart']}. Le simulateur GPU doit etre corrige.")
            self.rejeux[identifiant] = [{cle: r[cle] for cle in ("trimestre", "ecart_max", "trades")} for r in resumes]
        for membre in etat["pantheon"]:  # un membre repris d'un point de sauvegarde a deja son rejeu
            if membre["id"] in self.rejeux:
                membre["detail"]["rejeu"] = self.rejeux[membre["id"]]
        with (self.dossier / "generations.jsonl").open("a", encoding="utf-8") as fichier:
            fichier.write(checkpoint.texte(ligne) + "\n")
        checkpoint.ecrire(self.dossier / "etat.json", etat)
        checkpoint.ecrire(self.dossier / "pantheon.json", etat["pantheon"])


def membre_json(m: Membre, ctx: Contexte) -> dict:
    return {"id": m.id, "generation": m.generation, "note": m.note,
            "parametres": ctx.disposition.lisible(m.genome), "detail": m.detail,
            "genome": checkpoint.liste(m.genome), "serie": checkpoint.liste(m.serie)}


def membre_lu(d: dict) -> Membre:
    return Membre(d["id"], d["generation"], checkpoint.tenseur(d["genome"]), d["note"],
                  checkpoint.tenseur(d["serie"]), d["detail"])


class Evolution:
    def __init__(self, ctx: Contexte, dossier: Path, etat: dict):
        self.ctx, self.dossier, self.etat = ctx, dossier, etat
        config = ctx.config
        self.validation = trimestres(ctx.hist, config, config.debut_validation, fin_validation(config))
        self.pantheon = [membre_lu(m) for m in etat["pantheon"]]
        self.unite = float(ctx.evaluateur.principal.unite)
        self.arret = Arret()
        # Un processus de rejeu par coeur physique (la moitie des coeurs logiques), moins celui du fil principal.
        self.processus = ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) // 2 - 1),
                                             initializer=rejeu.initialiser, initargs=(ctx.hist, config, ctx.symbole))

    # --- Population d'une generation ---

    def _population(self, g: int):
        """Source des genomes, identifiant et origine de chaque bot de la generation g."""
        ctx, config, mode = self.ctx, self.ctx.config, self.etat["mode"]
        disp = ctx.disposition
        indices = torch.arange(config.population, device=disp.appareil)
        sigmas = (config.sigma_initial_reseau, config.sigma_initial_autres)
        if mode == "hasard" or g == 0:
            usage, rang, prefixe = (philox.HASARD, g, f"h{g}") if mode == "hasard" else (philox.GENERATION0, 0, "g0")
            k0, k1, _ = philox.cles_t(config.graine_maitresse, usage, rang, indices)
            source = lambda i: disp.generation0(k0[i], k1[i], *sigmas)
            return source, lambda i: f"{prefixe}-{i}", lambda i: {"cle": [int(k0[i]), int(k1[i])]}
        noms = [p["id"] for p in self.etat["parents"]]
        parents = torch.stack([checkpoint.tenseur(p["genome"]) for p in self.etat["parents"]]).to(disp.appareil)
        p = len(noms)
        k0, k1, choix = enfants(config.graine_maitresse, philox.ENFANT, g, indices, p)
        bornes = disp.bornes_amplitudes(*sigmas, config.amplitude_marge)

        def source(i: torch.Tensor) -> torch.Tensor:
            """Les p premiers bots sont les parents, inchanges (elitisme) ; les autres, leurs enfants."""
            mutes = disp.muter(parents, choix[i], k0[i], k1[i], config.proba_categoriel, config.mutation_enfant,
                               config.mutation_gene, bornes)
            return torch.where((i < p)[:, None], parents.index_select(0, i.clamp(max=p - 1)), mutes)

        identite = lambda i: noms[i] if i < p else f"g{g}-{i}"
        origine = lambda i: ({"elite": noms[i]} if i < p else
                             {"parent": noms[int(choix[i])], "cle": [int(k0[i]), int(k1[i])]})
        return source, identite, origine

    # --- Une generation ---

    def generation(self) -> tuple[dict, dict[str, list[Future]]]:
        """Une generation. Renvoie sa ligne de journal et les rejeux d'admission lances pour ses entrants."""
        ctx, config, etat = self.ctx, self.ctx.config, self.etat
        g = etat["generation"]
        debut = maintenant()
        torch.cuda.reset_peak_memory_stats()
        numero = g // renouvellement(config)
        fenetres = lot(ctx.hist, config, g)
        revues = confirmation(ctx.hist, config, g)
        source, identite, origine = self._population(g)
        durees = {}
        chrono = Chrono(durees)
        evaluation = ctx.evaluateur.evaluer(source, config.population, fenetres)
        res = evaluation.resultats
        comp = composantes(res, ctx.capital0)
        notes, _ = noter(comp, config)
        chrono("evaluation")
        # Candidats au role de parent : les meilleures notes du lot, et les parents en place, les premiers bots de
        # la generation, qui ne cedent leur place qu'a un candidat meilleur qu'eux.
        elites = len(etat["parents"]) if etat["mode"] != "hasard" and g > 0 else 0
        ordre = torch.sort(-notes, stable=True).indices[:config.candidats_examines].tolist()
        ordre += [i for i in range(elites) if i not in ordre]
        # Capital de chaque bot en fin de fenetre, en moyenne sur le lot, pour l'interface.
        capitaux = res.capital_final.double().mean(1) * self.unite
        p10, mediane, p90 = torch.quantile(capitaux, torch.tensor([0.1, 0.5, 0.9], dtype=torch.float64)).tolist()
        genomes = source(torch.tensor(ordre, device=ctx.disposition.appareil)).cpu()
        # Un seul paquet : les candidats sur le lot (series de positions), sur les fenetres de confirmation et en
        # validation. Leur note confirmee porte sur le lot et la confirmation : elle classe les parents.
        series, revus, validation = ctx.evaluateur.candidats(genomes, fenetres, revues, self.validation)
        comp_revue = composantes(revus, ctx.capital0)
        notes_revues, _ = noter(comp_revue, config)
        classement = torch.sort(-notes_revues, stable=True).indices.tolist()
        rangs_retenus = [classement[r] for r in distincts(series[classement], config.nb_parents,
                                                          config.seuil_distinction)]
        retenus = [ordre[r] for r in rangs_retenus]
        chrono("selection_et_validation")
        if g == 0 and etat["mode"] != "hasard":
            etat["champion_aleatoire"] = {"id": identite(ordre[0]), "note_entrainement": float(notes[ordre[0]]),
                                          "genome": checkpoint.liste(genomes[0])}
        # Seules les validations des parents retenus servent : elles seules comptent comme essais.
        res_parents = lignes(validation, rangs_retenus)
        genomes_parents = genomes[rangs_retenus]
        bilans_ = bilans([res_parents], self.validation, ctx.capital0, self.unite, config)
        candidats = [Membre(identite(bot), g, genome, b.note, b.serie, b.resume())
                     for bot, genome, b in zip(retenus, genomes_parents, bilans_)]
        for c, b in zip(candidats, bilans_):
            etat["validations"].setdefault(c.id, b.sharpe)  # essais en validation, pour le Deflated Sharpe Ratio
        anciens = {m.id for m in self.pantheon}
        nouveau = mettre_a_jour(self.pantheon, candidats, config.nb_parents, config.seuil_distinction)
        entrants = [m for m in nouveau if m.id not in anciens]
        attentes = {}
        if entrants:
            positions = [next(i for i, c in enumerate(candidats) if c.id == m.id) for m in entrants]
            attentes = self._admettre(entrants, res_parents.capital_final[positions])
        self.pantheon = nouveau
        chrono("admission")
        meilleure = self.pantheon[0].note
        if etat["meilleure_note"] is None or meilleure > etat["meilleure_note"]:
            etat["meilleure_note"], etat["generation_meilleure"] = meilleure, g
        etat["parents"] = [{"id": identite(bot), "genome": checkpoint.liste(genome),
                            "note_entrainement": float(notes[bot]), "note_confirmee": float(notes_revues[r])}
                           for bot, r, genome in zip(retenus, rangs_retenus, genomes_parents)]
        etat["pantheon"] = [membre_json(m, ctx) for m in self.pantheon]
        etat["bots_evalues"] += config.population
        etat["generation"] = g + 1
        duree = (maintenant() - debut).total_seconds()
        return {
            "generation": g,
            "date": maintenant().isoformat(),
            "duree_s": round(duree, 2),
            "durees_s": durees,
            "memoire_max_mo": torch.cuda.max_memory_allocated() // 2**20,
            "bots_evalues": etat["bots_evalues"],
            "validations_uniques": len(etat["validations"]),
            "lot": {"numero": numero, "fenetres": [
                {"nom": f.nom, "debut": ctx.hist.ouverture_de(f.debut + f.prechauffage).isoformat(),
                 "frais_ppm": f.frais, "glissement_ppm": f.glissement} for f in fenetres]},
            "confirmation": [f.nom for f in revues],
            "note_entrainement_max": float(notes[ordre[0]]),
            "note_entrainement_mediane": float(notes.median()),
            "note_confirmee_max": float(notes_revues[classement[0]]),
            "criteres": dict(zip(COMPOSANTES, parts(comp_revue, classement[0], config))),
            "capital_final": {"p10": p10, "mediane": mediane, "p90": p90, "meilleur": float(capitaux[ordre[0]])},
            "parents": [{"id": c.id, "origine": origine(bot), "note_entrainement": float(notes[bot]),
                         "note_confirmee": float(notes_revues[r]), "note_validation": c.note,
                         "sharpe_validation_annualise": b.sharpe_annualise}
                        for bot, r, c, b in zip(retenus, rangs_retenus, candidats, bilans_)],
            "pantheon": [{"id": m.id, "note": m.note} for m in self.pantheon],
            "meilleure_note_pantheon": meilleure,
            "sigma_moyen": evaluation.sigma_moyen,
        }, attentes

    def _admettre(self, entrants: list[Membre], capitaux_valides: torch.Tensor) -> dict[str, list[Future]]:
        """Admission des nouveaux membres du Pantheon.

        Leur trace complete est recalculee : elle doit redonner les capitaux de leur validation, puisqu'un bot
        a le meme resultat dans tout paquet. Leur flux d'ordres part ensuite se rejouer dans le grand livre du
        moteur, un processus par trimestre ; l'ecrivain en attend le resultat avant tout point de sauvegarde.
        """
        traces = self.ctx.evaluateur.traces(torch.stack([m.genome for m in entrants]), self.validation)
        attentes = {}
        for position, membre in enumerate(entrants):
            res, b = traces[position // COMPLETS_MAX], position % COMPLETS_MAX
            if not torch.equal(res.capital_final[b], capitaux_valides[position]):
                raise RuntimeError(f"{membre.id} : la trace complete ne redonne pas sa validation. "
                                   "Le simulateur GPU doit etre corrige.")
            attentes[membre.id] = [
                self.processus.submit(rejeu.verifier, trimestre, _couloir(res.trace, b, w), membre.id)
                for w, trimestre in enumerate(self.validation)
            ]
        return attentes

    # --- La boucle ---

    def boucle(self) -> None:
        ctx, config, etat = self.ctx, self.ctx.config, self.etat
        journal = self.dossier / "generations.jsonl"
        if journal.exists():  # une reprise efface les generations d'apres le point de sauvegarde
            gardees = [l for l in journal.read_text(encoding="utf-8").splitlines() if _avant(l, etat["generation"])]
            journal.write_text("".join(l + "\n" for l in gardees), encoding="utf-8")
        limite = etat["generations_max"]
        print(f"Run {self.dossier.name} ({etat['mode']}), paquets de {ctx.evaluateur.taille_paquet} bots, "
              f"generation {etat['generation']}.", flush=True)
        ecrivain = Ecrivain(self.dossier)
        while limite is None or etat["generation"] < limite:
            ecrivain.verifier()
            ligne, attentes = self.generation()
            ecrivain.poser(ligne, copy.deepcopy(etat), attentes)
            afficher(ligne)
            if self.arret.demande:
                break
            stagnation = etat["generation"] - 1 - etat["generation_meilleure"]
            if etat["mode"] == "reel" and config.stagnation_max and stagnation >= config.stagnation_max:
                print(f"Arret : la validation stagne depuis {stagnation} generations.", flush=True)
                break
        ecrivain.terminer()
        self.cloturer()
        self.processus.shutdown()

    def cloturer(self) -> None:
        """Rejoue et journalise chaque membre du Pantheon sur la validation, trimestre par trimestre.

        Le dossier pantheon/ ne tient que le Pantheon du dernier arret : celui d'un arret precedent, avant une
        reprise, est efface. Tout s'y recalcule a partir du point de sauvegarde.
        """
        ctx = self.ctx
        if not self.pantheon:
            return
        dossier = self.dossier / "pantheon"
        if dossier.exists():
            shutil.rmtree(dossier)
        traces = ctx.evaluateur.traces(torch.stack([m.genome for m in self.pantheon]), self.validation)
        futurs = []
        for position, membre in enumerate(self.pantheon):
            res, b = traces[position // COMPLETS_MAX], position % COMPLETS_MAX
            for w, trimestre in enumerate(self.validation):
                cible = dossier / f"{position + 1}-{membre.id}" / trimestre.nom
                futurs.append(self.processus.submit(rejeu.consigner_a_part, trimestre, _couloir(res.trace, b, w),
                                                    membre.id, cible))
        for futur in futurs:
            futur.result()
        print(f"Pantheon : {dossier}", flush=True)
        for position, membre in enumerate(self.pantheon):
            print(f"  {position + 1}. {membre.id}  note de validation {membre.note:.4f}", flush=True)


def _couloir(trace: dict, b: int, w: int) -> dict:
    """Trace d'un couloir, copiee : un processus de rejeu ne recoit que ses propres series."""
    return {nom: t[:, b, w].clone() for nom, t in trace.items()}


def _avant(ligne: str, generation: int) -> bool:
    """Ligne de generations.jsonl a garder a la reprise : complete, et d'avant le point de sauvegarde.

    Un arret brutal pendant l'ecriture peut laisser une derniere ligne tronquee.
    """
    try:
        return json.loads(ligne)["generation"] < generation
    except json.JSONDecodeError:
        return False


def afficher(ligne: dict) -> None:
    sigma = " ".join(f"{g[:3]} {ligne['sigma_moyen'][g]:.4g}" for g in GROUPES)
    parents = " ".join(f"{p['note_validation']:.3f}" for p in ligne["parents"])
    bots = f"{ligne['bots_evalues']:,}".replace(",", " ")
    print(f"gen {ligne['generation']:>4} | bots {bots:>11} | lot {ligne['lot']['numero']:>3} | "
          f"entr. {ligne['note_entrainement_max']:.4f} | conf. {ligne['note_confirmee_max']:.4f} | valid. {parents} | "
          f"Pantheon {ligne['meilleure_note_pantheon']:.4f} | sigma {sigma} | "
          f"{ligne['duree_s']:.0f} s, {ligne['memoire_max_mo']} Mo", flush=True)


def etat_initial(mode: str, source: str | None, limite: int | None, ctx: Contexte) -> dict:
    return {"version": 1, "mode": mode, "source": source, "generations_max": limite, "generation": 0,
            "bots_evalues": 0, "taille_paquet": ctx.evaluateur.taille_paquet, "parents": [], "pantheon": [],
            "champion_aleatoire": None, "validations": {}, "meilleure_note": None, "generation_meilleure": None,
            "noyaux": [{"generation": 0, "empreinte": empreinte_noyaux(ctx)}]}


def noter_noyaux(etat: dict, ctx: Contexte) -> None:
    """A la reprise : si les noyaux ont change depuis le debut du run, le dire, et noter a quelle generation.

    Le run continue, mais il ne redonnera pas le Pantheon d'un run continu.
    """
    empreinte = empreinte_noyaux(ctx)
    historique = etat.setdefault("noyaux", [])
    if historique and historique[-1]["empreinte"] == empreinte:
        return
    avant = historique[-1]["empreinte"] if historique else "non enregistree"
    print(f"Attention : les noyaux CUDA ont change depuis le debut du run (empreinte {avant}, maintenant "
          f"{empreinte}). A partir de la generation {etat['generation']}, le run ne redonnera pas un run continu.",
          flush=True)
    historique.append({"generation": etat["generation"], "empreinte": empreinte})


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrainement evolutif du bot sur GPU.")
    groupe = parser.add_mutually_exclusive_group()
    groupe.add_argument("--config", type=Path, default=ROOT / "evolution" / "config.toml")
    groupe.add_argument("--reprendre", type=Path, help="dossier d'un run a reprendre")
    groupe.add_argument("--a-blanc", type=Path, dest="a_blanc", help="dossier du run reel a doubler a blanc")
    groupe.add_argument("--hasard", type=Path, help="dossier du run reel a comparer au hasard")
    parser.add_argument("--generations-max", type=int, dest="generations_max",
                        help="avec --reprendre : generation ou le run s'arrete desormais ; 0 : pas de limite")
    parser.add_argument("--stagnation-max", type=int, dest="stagnation_max",
                        help="avec --reprendre : remplace stagnation_max pour cette reprise ; 0 le desactive")
    args = parser.parse_args()
    limites = [v for v in (args.generations_max, args.stagnation_max) if v is not None]
    if limites and not args.reprendre:
        parser.error("--generations-max et --stagnation-max ne valent qu'avec --reprendre")
    if any(v < 0 for v in limites):
        parser.error("--generations-max et --stagnation-max sont des entiers positifs ou nuls")
    appareil = gpu.preparer()
    etat = None
    if args.reprendre:
        dossier = args.reprendre
        texte = (dossier / "config.toml").read_text(encoding="utf-8")
        etat = checkpoint.lire(dossier / "etat.json")
        mode, source = etat["mode"], etat["source"]
        if limites and mode != "reel":
            raise SystemExit(f"{dossier} n'est pas un run reel : il garde le nombre de generations de son run reel")
        if args.generations_max is not None:
            etat["generations_max"] = args.generations_max or None
    elif args.a_blanc or args.hasard:
        reel = args.a_blanc or args.hasard
        texte = (reel / "config.toml").read_text(encoding="utf-8")
        etat_reel = checkpoint.lire(reel / "etat.json")
        if etat_reel["mode"] != "reel":
            raise SystemExit(f"{reel} n'est pas un run reel")
        mode, source, limite = ("a-blanc" if args.a_blanc else "hasard"), reel.as_posix(), etat_reel["generation"]
    else:
        texte = args.config.read_text(encoding="utf-8")
        mode, source, limite = "reel", None, None
    config = lire(texte)
    if args.stagnation_max is not None:
        config = replace(config, stagnation_max=args.stagnation_max)
    if limites:
        fin = f"jusqu'a la generation {etat['generations_max']}" if etat["generations_max"] else "sans limite de generations"
        stagne = (f"arret apres {config.stagnation_max} generations sans progres" if config.stagnation_max
                  else "pas d'arret sur stagnation")
        print(f"Reprise {fin} ; {stagne}.", flush=True)
    ctx = preparer(config, appareil, test=False, a_blanc=mode == "a-blanc",
                   taille_paquet=etat["taille_paquet"] if etat else None)
    if etat is None:
        suffixe = "" if mode == "reel" else f"-{mode}"
        dossier = ROOT / "runs" / f"{maintenant():%Y%m%dT%H%M%SZ}-evolution{suffixe}"
        dossier.mkdir(parents=True)
        (dossier / "config.toml").write_text(texte, encoding="utf-8")
        checkpoint.ecrire(dossier / "manifest.json", manifeste(ctx, mode, source))
        etat = etat_initial(mode, source, limite if mode != "reel" else (config.generations_max or None), ctx)
        if mode != "reel" and etat_reel.get("noyaux", [{}])[-1].get("empreinte") != etat["noyaux"][0]["empreinte"]:
            print("Attention : le run reel a ete calcule avec d'autres noyaux CUDA : la comparaison melera deux "
                  "simulateurs.", flush=True)
    else:
        noter_noyaux(etat, ctx)
    Evolution(ctx, dossier, etat).boucle()


if __name__ == "__main__":
    main()
