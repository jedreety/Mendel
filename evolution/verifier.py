"""Verifie les noyaux CUDA du bot evolutif contre leurs references.

    python -m evolution.verifier
    python -m evolution.verifier --bots 512 --config evolution/config.toml

Sur l'historique d'entrainement et de validation, jamais sur le bloc de test :
1. simulateur : le noyau contre la reference PyTorch (evolution/reference.py), sur le lot 0 et la validation.
   Seul l'ordre des sommes de la couche de sortie differe (cuBLAS d'un cote, un arbre de sommes de l'autre) :
   les probabilites different d'environ 1e-6, et de rares couloirs finissent a un pas de prix ou de quantite
   pres. Il faut au moins 99 % de capitaux finaux identiques.
2. rejeu exact : les flux d'ordres traces par le noyau, rejoues dans le grand livre du moteur, en decimal.
3. invariance au paquet et determinisme : des bots seuls, puis les memes au milieu d'un grand paquet, deux fois.
4. genomes et moyennes recursives : noyaux contre operations PyTorch, au bit pres.
5. regles portees : le signal de chaque module tire des regles du moteur contre le vote de la regle, sur des barres
   horaires au hasard, aux reglages du catalogue (evolution/modules/regles/moteur.py). Deux s'en ecartent a
   dessein, leurs moyennes exponentielles portant sur tout l'historique : elles sont rapportees sans echouer.

Code de sortie 1 si une verification echoue.
"""
import argparse
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore", message="Failed to initialize NumPy")  # PyTorch s'en passe tres bien
import torch  # noqa: E402

from evolution import gpu, philox, rejeu  # noqa: E402
from evolution.config import lire  # noqa: E402
from evolution.contexte import ROOT  # noqa: E402
from evolution.data import charger, fin_validation, lot, minuit, trimestres  # noqa: E402
from evolution.genome import MODULES, Disposition  # noqa: E402
from evolution.marche import PERIODE_ATR_MAX, Marche, lisser, lisser_reference  # noqa: E402
from evolution.modules.regles import moteur  # noqa: E402
from evolution.reference import PAQUET_MIN, SimulateurReference  # noqa: E402
from evolution.selection import enfants  # noqa: E402
from evolution.simulator import Simulateur  # noqa: E402

TRACES = 16  # bots traces en entier : decisions barre par barre et rejeu exact
ACCORD_MIN = 0.99  # part minimale de couloirs aux capitaux finaux identiques, noyau contre reference
BARRES_REGLES = 300  # barres horaires tirees au hasard pour comparer les regles portees au moteur

echecs: list[str] = []


def verifier(condition: bool, message: str) -> None:
    print(("  ok     " if condition else "  ECHEC  ") + message, flush=True)
    if not condition:
        echecs.append(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verification des noyaux CUDA du bot evolutif.")
    parser.add_argument("--config", type=Path, default=ROOT / "evolution" / "config.toml")
    parser.add_argument("--bots", type=int, default=256, help="bots compares au simulateur de reference")
    args = parser.parse_args()
    dev = gpu.preparer()
    config = lire(args.config.read_text(encoding="utf-8"))
    hist = charger(ROOT / config.donnees, config.pas_de_prix, minuit(config.debut_test))
    marche = Marche(hist, dev)
    tables = [module.preparer(marche) for module in MODULES]
    disp = Disposition(config.taille_cachee, config.canaux_modules).vers(dev)
    n = max(args.bots, TRACES)
    k0, k1, _ = philox.cles_t(config.graine_maitresse, philox.REFERENCE, 0, torch.arange(n, device=dev))
    parametres = disp.decoder(disp.generation0(k0, k1, config.sigma_initial_reseau, config.sigma_initial_autres))
    validation = trimestres(hist, config, config.debut_validation, fin_validation(config))

    print(f"1. Noyau contre reference, {n} bots", flush=True)
    traces = None
    for nom, fenetres in (("lot 0", lot(hist, config, 0)), ("validation", validation)):
        pas = max(f.prechauffage + f.longueur for f in fenetres)
        sim = Simulateur(marche, disp, tables, config, n, 4, pas, "complet", bots_traces=TRACES)
        sim.ecrire(0, parametres)
        sim.completer(n, fenetres)
        res = sim.executer(pas)
        ref = SimulateurReference(marche, disp, tables, config, max(n, PAQUET_MIN), 4, pas, "complet",
                                  bots_traces=TRACES)
        ref.ecrire(0, parametres)
        ref.completer(n, fenetres)
        attendu = ref.executer(pas)
        accord = (res.capital_final == attendu.capital_final).float().mean().item()
        decisions = (res.trace["decision"] == attendu.trace["decision"]).all(0).float().mean().item()
        print(f"  {nom} : capitaux identiques {accord:.4f} des couloirs, decisions identiques sur {decisions:.4f} "
              f"des couloirs traces, trades {int(res.trades.sum())} contre {int(attendu.trades.sum())}")
        verifier(accord >= ACCORD_MIN, f"{nom} : au moins {ACCORD_MIN:.0%} de capitaux finaux identiques")
        if nom == "validation":
            actifs = torch.sort(-res.trades.sum(1), stable=True).indices[:TRACES].tolist()
        del sim, ref
        torch.cuda.empty_cache()

    print(f"2. Rejeu exact des {TRACES} bots les plus actifs sur les {len(validation)} trimestres de validation",
          flush=True)
    pas = max(f.prechauffage + f.longueur for f in validation)
    sim = Simulateur(marche, disp, tables, config, TRACES, 4, pas, "complet")
    sim.ecrire(0, disp.decoder(disp.generation0(k0[actifs], k1[actifs], config.sigma_initial_reseau,
                                                config.sigma_initial_autres)))
    sim.completer(TRACES, validation)
    traces = sim.executer(pas)
    symbole = Path(config.donnees).stem.split("-")[0]
    with ProcessPoolExecutor(initializer=rejeu.initialiser, initargs=(hist, config, symbole)) as processus:
        futurs = [processus.submit(rejeu.verifier, trimestre, {nom: t[:, b, w].clone() for nom, t in traces.trace.items()},
                                   f"bot-{b}")
                  for b in range(TRACES) for w, trimestre in enumerate(validation)]
        resumes = [f.result() for f in futurs]
    trades = sum(r["trades"] for r in resumes)
    ecart = max(float(r["ecart_max"]) for r in resumes)
    verifier(all(r["conforme"] for r in resumes), f"{len(resumes)} couloirs, {trades} trades, ecart maximal {ecart} USDT")

    print("3. Invariance au paquet et determinisme", flush=True)
    petit = 64
    fenetres = lot(hist, config, 0)
    pas = max(f.prechauffage + f.longueur for f in fenetres)
    seuls = Simulateur(marche, disp, tables, config, petit, 4, pas)
    seuls.ecrire(0, disp.decoder(disp.generation0(k0[:petit], k1[:petit], config.sigma_initial_reseau,
                                                  config.sigma_initial_autres)))
    seuls.completer(petit, fenetres)
    a = seuls.executer(pas)
    grand = Simulateur(marche, disp, tables, config, n, 4, pas)
    grand.ecrire(0, parametres)
    grand.completer(n, fenetres)
    b = grand.executer(pas)
    grand.completer(n, fenetres)
    c = grand.executer(pas)
    champs = ("capital_final", "trades", "somme_r", "drawdown", "frais", "rotation")
    verifier(all(torch.equal(getattr(a, k), getattr(b, k)[:petit]) for k in champs),
             f"{petit} bots seuls ou dans un paquet de {n} : memes comptes")
    verifier(all(torch.equal(getattr(b, k), getattr(c, k)) for k in champs), "deux executions : memes comptes")

    print("4. Genomes et moyennes recursives, au bit pres", flush=True)
    m = 1024
    k0m, k1m, _ = philox.cles_t(config.graine_maitresse, philox.GENERATION0, 0, torch.arange(m, device=dev))
    g = disp.generation0(k0m, k1m, config.sigma_initial_reseau, config.sigma_initial_autres)
    verifier(torch.equal(g, disp.generation0_reference(k0m, k1m, config.sigma_initial_reseau,
                                                       config.sigma_initial_autres)), "generation 0")
    e0, e1, choix = enfants(config.graine_maitresse, philox.ENFANT, 1, torch.arange(m, device=dev), 5)
    reglages = (config.proba_categoriel, config.mutation_enfant, config.mutation_gene,
                disp.bornes_amplitudes(config.sigma_initial_reseau, config.sigma_initial_autres, config.amplitude_marge))
    enfants_ = disp.muter(g[:5], choix, e0, e1, *reglages)
    verifier(torch.equal(enfants_, disp.muter_reference(g[:5], choix, e0, e1, *reglages)), "mutation")
    periodes = torch.arange(1, PERIODE_ATR_MAX + 1, dtype=torch.int64)
    for echelle, b in zip(("1 h", "4 h", "24 h"), marche.barres):
        x, y = lisser(marche._etendue_vraie(b), periodes, 1.0 / periodes.double(), 0).cpu(), lisser_reference(
            marche._etendue_vraie(b), periodes, 1.0 / periodes.double(), 0)
        nx, ny = torch.isnan(x), torch.isnan(y)
        verifier(torch.equal(nx, ny) and torch.equal(x[~nx], y[~ny]), f"ATR de Wilder, echelle {echelle}")

    print(f"5. Regles portees contre les regles du moteur, {BARRES_REGLES} barres horaires au hasard", flush=True)
    for nom, regle, accord, votes in moteur.comparer(hist, marche, BARRES_REGLES, config.graine_maitresse):
        message = f"{nom} : {regle} redonne {accord:.1%} des votes ({votes} non nuls)"
        if nom in moteur.APPROCHEES:
            print(f"  ecart  {message}, moyennes sur tout l'historique", flush=True)
        else:
            verifier(accord == 1, message)

    print("Tout est conforme." if not echecs else f"{len(echecs)} verification(s) en echec.", flush=True)
    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
