"""Lecture des dossiers de runs pour l'interface. Rien n'y est jamais ecrit.

Tout se lit sans PyTorch. Deux precautions tiennent le bot a l'abri de l'interface :

- Tout fichier est ouvert en partage complet, suppression comprise (windows.lire) : a l'arret, le bot efface
  pantheon/ pendant qu'on peut le lire.
- etat.json et pantheon.json ne sont jamais ouverts pendant qu'un run ecrit. Sous Windows, un fichier ouvert
  fait echouer os.replace, donc l'ecriture du point de sauvegarde, et le run s'arreterait. Pendant un run, tout
  vient de generations.jsonl, ou le bot ne fait qu'ajouter des lignes.

Le bloc de test reste ferme : les prix d'apres le debut du test ne sont lus que si le dossier benchmark/ du run
existe, c'est-a-dire si le test a deja ete ouvert.
"""
import csv
import io
import json
import math
import re
import threading
import tomllib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from adapters.system_clock import SystemClock
from interface import windows

NOM = re.compile(r"^[A-Za-z0-9._-]+$")
MEMBRE = re.compile(r"^\d+-[A-Za-z0-9-]+$")
BOT_BENCHMARK = re.compile(r"^[A-Za-z0-9_]+$")
TRIMESTRE = re.compile(r"^(\d{4})-T([1-4])$")
IDENTIFIANT = re.compile(r"^[gh](\d+)-\d+$")
SECTION = re.compile(r"^#\s*---\s*(.+?)\s*---")
AFFECTATION = re.compile(r"^(\w+)\s*=\s*(.*?)\s*(#.*)?$")
REPOS_S = 300  # sans ecriture depuis cinq minutes, un run inconnu de l'interface est tenu pour arrete
HEURE = timedelta(hours=1)
REMPLACES = ("etat.json", "pantheon.json", "etat.json.tmp", "pantheon.json.tmp")  # remplaces par os.replace
FICHIERS_MAX = 5000


class Introuvable(Exception):
    pass


class Refus(Exception):
    """Lecture refusee pour ne pas gener le bot."""


def propre(contenu):
    """JSON strict : nombres non finis a null, decimaux et dates en texte."""
    if isinstance(contenu, float):
        return contenu if math.isfinite(contenu) else None
    if isinstance(contenu, dict):
        return {str(cle): propre(valeur) for cle, valeur in contenu.items()}
    if isinstance(contenu, (list, tuple)):
        return [propre(valeur) for valeur in contenu]
    if isinstance(contenu, (Decimal, date)):
        return str(contenu) if isinstance(contenu, Decimal) else contenu.isoformat()
    return contenu


def _texte(chemin: Path) -> str:
    return windows.lire(chemin).decode("utf-8")


def _json(chemin: Path):
    return json.loads(_texte(chemin))


def _signature(chemin: Path) -> tuple[int, int] | None:
    try:
        etat = chemin.stat()  # une lecture d'attributs : elle ne gene aucune ecriture
    except FileNotFoundError:
        return None
    return etat.st_mtime_ns, etat.st_size


def _court(valeur: float) -> float:
    return float(f"{valeur:.5g}")


class Lecteur:
    """connaissance(nom) -> (vivante, fin) : une tache de l'interface ecrit-elle ce run, et quand la derniere
    s'est-elle terminee (instant en secondes, ou None). noms(nom) -> nom donne au bot dans l'interface, ou None."""

    def __init__(self, racine: Path, connaissance, noms):
        self.racine, self.connaissance, self.noms = racine, connaissance, noms
        self.runs_dir = racine / "runs"
        self.cache: dict = {}
        self.verrou = threading.Lock()

    # --- Outils ---

    def _memo(self, chemin: Path, genre: str, fonction):
        """Resultat de fonction(chemin), garde tant que le fichier ne change pas."""
        signature = _signature(chemin)
        if signature is None:
            raise Introuvable(chemin.name)
        cle = (str(chemin), genre)
        with self.verrou:
            trouve = self.cache.get(cle)
        if trouve and trouve[0] == signature:
            return trouve[1]
        valeur = fonction(chemin)
        with self.verrou:
            self.cache[cle] = (signature, valeur)
        return valeur

    def dossier(self, nom: str) -> Path:
        if not NOM.match(nom or "") or not (self.runs_dir / nom).is_dir():
            raise Introuvable(f"run {nom!r}")
        return self.runs_dir / nom

    def evolutions(self) -> list[str]:
        """Dossiers de runs du bot evolutif, du plus recent au plus ancien."""
        noms = []
        for entree in self.runs_dir.iterdir():
            if entree.is_dir() and NOM.match(entree.name) and "-evolution" in entree.name \
                    and (entree / "manifest.json").exists():
                noms.append(entree.name)
        return sorted(noms, reverse=True)

    def config(self, dossier: Path) -> dict:
        return self._memo(dossier / "config.toml", "config",
                          lambda c: tomllib.loads(_texte(c), parse_float=Decimal))

    def manifeste(self, dossier: Path) -> dict:
        return self._memo(dossier / "manifest.json", "json", _json)

    def generations(self, nom: str, depuis: int = 0) -> list[dict]:
        dossier = self.dossier(nom)
        lignes = self._generations(dossier)
        return [l for l in lignes if l["generation"] >= depuis]

    def _generations(self, dossier: Path) -> list[dict]:
        """generations.jsonl, relu seulement depuis la derniere lecture : le bot n'y fait qu'ajouter des lignes,
        sauf a la reprise, ou il le reecrit plus court. Une derniere ligne incomplete attend la lecture suivante."""
        chemin = dossier / "generations.jsonl"
        signature = _signature(chemin)
        if signature is None:
            return []
        cle = (str(chemin), "generations")
        with self.verrou:
            trouve = self.cache.get(cle)
        if trouve and trouve["signature"] == signature:
            return trouve["lignes"]
        lignes, position, queue = [], 0, b""
        if trouve and trouve["position"] <= signature[1]:
            q = trouve["queue"]  # la derniere ligne lue doit etre encore la : sinon le fichier a ete reecrit
            if not q or windows.lire(chemin, trouve["position"] - len(q), len(q)) == q:
                lignes, position, queue = list(trouve["lignes"]), trouve["position"], q
        brut = windows.lire(chemin, position)
        fin = brut.rfind(b"\n") + 1
        for ligne in brut[:fin].decode("utf-8").splitlines():
            try:
                lignes.append(json.loads(ligne))
            except json.JSONDecodeError:
                continue
        if fin:
            queue = brut[brut.rfind(b"\n", 0, fin - 1) + 1:fin]
        with self.verrou:
            self.cache[cle] = {"signature": (signature[0], position + fin), "lignes": lignes,
                               "position": position + fin, "queue": queue}
        return lignes

    def ecriture(self, dossier: Path) -> float | None:
        """Instant de la derniere ecriture du run, en secondes."""
        instants = [s[0] / 1e9 for s in (_signature(dossier / f) for f in
                                         ("generations.jsonl", "etat.json", "pantheon.json")) if s]
        return max(instants) if instants else None

    def actif(self, nom: str, dossier: Path) -> bool:
        """Le run peut-il ecrire en ce moment ? Dans le doute, oui : on ne lit alors pas son point de sauvegarde."""
        vivante, fin = self.connaissance(nom)
        if vivante:
            return True
        if any((dossier / f).exists() for f in ("etat.json.tmp", "pantheon.json.tmp")):
            return True
        ecrit = self.ecriture(dossier)
        if ecrit is None:
            return False
        if fin is not None and fin >= ecrit:
            return False  # l'interface a vu s'arreter la tache qui l'a ecrit
        return SystemClock().now().timestamp() - ecrit < REPOS_S

    def _point(self, dossier: Path, fichier: str):
        """etat.json ou pantheon.json, seulement run arrete. None si le run peut ecrire."""
        if self.actif(dossier.name, dossier) or not (dossier / fichier).exists():
            return None
        return self._memo(dossier / fichier, "json", _json)

    # --- Runs ---

    def resume(self, nom: str) -> dict:
        dossier = self.dossier(nom)
        manifeste = self.manifeste(dossier)
        config = self.config(dossier)
        lignes = self._generations(dossier)
        mode = manifeste.get("mode")
        source = Path(manifeste["source"]).name if manifeste.get("source") else None
        derniere = lignes[-1] if lignes else None
        meilleure, gen_meilleure = None, None
        for l in lignes:
            if meilleure is None or l["meilleure_note_pantheon"] > meilleure:
                meilleure, gen_meilleure = l["meilleure_note_pantheon"], l["generation"]
        generation = derniere["generation"] + 1 if derniere else 0
        actif = self.actif(nom, dossier)
        etat = self._point(dossier, "etat.json")
        if etat is not None:
            generations_max = etat.get("generations_max")
        elif mode == "reel":
            generations_max = config.get("generations_max") or None
        else:  # un run a blanc ou une recherche aleatoire compte autant de generations que son run reel
            try:
                generations_max = len(self._generations(self.dossier(source)))
            except Introuvable:
                generations_max = None
        durees = [l["duree_s"] for l in lignes[-10:]]
        ecrit = self.ecriture(dossier)
        return propre({
            "nom": nom,
            "nom_bot": self.noms(nom),
            "mode": mode,
            "source": source,
            "donnees": config.get("donnees"),
            "symbole": Path(config.get("donnees", "")).stem.split("-")[0],
            "debut_entrainement": config.get("debut_entrainement"),
            "debut_validation": config.get("debut_validation"),
            "debut_test": config.get("debut_test"),
            "capital_initial": config.get("capital_initial"),
            "duree_totale_s": round(sum(l["duree_s"] for l in lignes), 1),
            "date": manifeste.get("date"),
            "gpu": manifeste.get("gpu"),
            "revision": manifeste.get("revision"),
            "noyaux": manifeste.get("noyaux"),
            "population": config.get("population"),
            "generation": generation,
            "generations_max": generations_max,
            "bots_evalues": derniere["bots_evalues"] if derniere else 0,
            "meilleure_note": meilleure,
            "generation_meilleure": gen_meilleure,
            "stagnation": generation - 1 - gen_meilleure if gen_meilleure is not None else None,
            "stagnation_max": config.get("stagnation_max") if mode == "reel" else None,
            "champion": derniere["pantheon"][0] if derniere and derniere["pantheon"] else None,
            "lot": derniere["lot"]["numero"] if derniere else None,
            "duree_moyenne_s": sum(durees) / len(durees) if durees else None,
            "ecriture": datetime.fromtimestamp(ecrit, UTC).isoformat() if ecrit else None,
            "actif": actif,
            "point_de_sauvegarde": (dossier / "etat.json").exists(),
            "pantheon_rejoue": (dossier / "pantheon").is_dir(),
            "benchmark": (dossier / "benchmark").is_dir(),
            "rapport": (dossier / "benchmark" / "rapport.json").exists(),
        })

    def runs(self) -> list[dict]:
        resumes = []
        for nom in self.evolutions():
            try:
                resumes.append(self.resume(nom))
            except (Introuvable, OSError, ValueError, KeyError, tomllib.TOMLDecodeError):
                continue  # un run en cours de creation : il reviendra a la lecture suivante
        for r in resumes:
            r["lies"] = [autre["nom"] for autre in resumes if autre["source"] == r["nom"]]
        return resumes

    def detail(self, nom: str) -> dict:
        dossier = self.dossier(nom)
        resume = self.resume(nom)
        resume["lies"] = self.temoins(nom)
        texte = _texte(dossier / "config.toml")
        etat = self._point(dossier, "etat.json")
        pantheon = self._point(dossier, "pantheon.json")
        membres = None
        if pantheon is not None:
            membres = [{"id": m["id"], "generation": m["generation"], "note": m["note"],
                        "parametres": m.get("parametres"), "detail": m.get("detail"),
                        "serie": [round(v, 4) for v in m.get("serie") or []]} for m in pantheon]
        if etat is not None:
            aleatoire = etat.get("champion_aleatoire") or {}
            etat = {cle: etat.get(cle) for cle in ("generation", "generations_max", "taille_paquet", "noyaux",
                                                    "meilleure_note", "generation_meilleure")}
            etat["champion_aleatoire"] = {cle: aleatoire.get(cle) for cle in ("id", "note_entrainement")}
        return propre({
            "resume": resume,
            "manifeste": self.manifeste(dossier),
            "config": {"texte": texte, "valeurs": self.config(dossier)},
            "etat": etat,
            "pantheon": membres,
            "rejeux": self._rejeux(dossier),
        })

    def temoins(self, nom: str) -> list[str]:
        """Runs a blanc et recherches aleatoires faits a partir de ce run reel."""
        return [n for n in self.evolutions() if n != nom and self._source(n) == nom]

    def _source(self, nom: str) -> str | None:
        try:
            source = self.manifeste(self.dossier(nom)).get("source")
        except (Introuvable, OSError, ValueError):
            return None
        return Path(source).name if source else None

    def _rejeux(self, dossier: Path) -> dict:
        """Dossiers rejoues dans le moteur : Pantheon du dernier arret, et benchmark s'il a eu lieu."""
        rejeux = {}
        for genre, motif in (("pantheon", MEMBRE), ("benchmark", BOT_BENCHMARK)):
            racine = dossier / genre
            if not racine.is_dir():
                continue
            rejeux[genre] = {
                sous.name: sorted(t.name for t in sous.iterdir() if t.is_dir() and TRIMESTRE.match(t.name))
                for sous in sorted(racine.iterdir()) if sous.is_dir() and motif.match(sous.name)
            }
        return rejeux

    def rapport(self, nom: str) -> dict:
        chemin = self.dossier(nom) / "benchmark" / "rapport.json"
        if not chemin.exists():
            raise Introuvable("rapport du benchmark")
        return self._memo(chemin, "json", _json)

    # --- Fichiers d'un run ---

    def fichiers(self, nom: str) -> dict:
        """Fichiers du dossier d'un run, par lectures d'attributs seulement. Ceux que le bot remplace sont
        verrouilles tant qu'il peut ecrire."""
        dossier = self.dossier(nom)
        actif = self.actif(nom, dossier)
        liste = []
        for chemin in sorted(dossier.rglob("*")):
            try:
                etat = chemin.stat()
            except FileNotFoundError:  # pantheon/ efface a l'arret du run pendant le parcours
                continue
            if not chemin.is_file():
                continue
            relatif = chemin.relative_to(dossier).as_posix()
            liste.append({"chemin": relatif, "octets": etat.st_size,
                          "modifie": datetime.fromtimestamp(etat.st_mtime, UTC).isoformat(),
                          "verrouille": actif and relatif in REMPLACES})
            if len(liste) >= FICHIERS_MAX:
                break
        return {"actif": actif, "fichiers": liste}

    def fichier(self, nom: str, chemin: str) -> tuple[bytes, str]:
        """Octets d'un fichier du run et son nom, pour le telecharger."""
        dossier = self.dossier(nom).resolve()
        cible = (dossier / chemin).resolve()
        if not cible.is_relative_to(dossier) or not cible.is_file():
            raise Introuvable("fichier")
        if cible.relative_to(dossier).as_posix() in REMPLACES and self.actif(nom, dossier):
            raise Refus("le run peut ecrire ce fichier en ce moment : il se lit a son arret")
        return windows.lire(cible), cible.name

    # --- Genealogie ---

    def genealogie(self, nom: str, bot: str) -> list[dict]:
        """Ascendance d'un bot retenu, de lui jusqu'a la generation 0 : chaque enfant garde l'identite de son
        parent dans generations.jsonl."""
        lignes = {l["generation"]: l for l in self._generations(self.dossier(nom))}
        presences: dict[str, list[int]] = {}
        for g, l in lignes.items():
            for p in l["parents"]:
                presences.setdefault(p["id"], []).append(g)
        chaine, courant = [], bot
        while courant and len(chaine) < 100_000:
            trouve = IDENTIFIANT.match(courant)
            ligne = lignes.get(int(trouve.group(1))) if trouve else None
            parent = next((p for p in ligne["parents"] if p["id"] == courant), None) if ligne else None
            if parent is None:
                break
            vu = presences.get(courant, [])
            chaine.append({"id": courant, "generation": ligne["generation"],
                           "note_entrainement": parent["note_entrainement"],
                           "note_validation": parent["note_validation"],
                           "sharpe_validation_annualise": parent.get("sharpe_validation_annualise"),
                           "generations_parent": len(vu), "derniere_generation_parent": vu[-1] if vu else None})
            courant = parent["origine"].get("parent")
        return propre(chaine)

    # --- Rejeux ---

    def rejeu(self, nom: str, genre: str, sous: str, trimestre: str) -> dict:
        """Un couloir rejoue dans le moteur : resume, trades, et le reseau barre par barre (reseau.jsonl)."""
        motif = {"pantheon": MEMBRE, "benchmark": BOT_BENCHMARK}.get(genre)
        if motif is None or not motif.match(sous) or not TRIMESTRE.match(trimestre):
            raise Introuvable("rejeu")
        dossier = self.dossier(nom) / genre / sous / trimestre
        if not dossier.is_dir():
            raise Introuvable("rejeu")
        try:
            return self._memo(dossier / "reseau.jsonl", "rejeu", lambda _: self._lire_rejeu(dossier))
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as erreur:
            raise Introuvable("rejeu en cours d'ecriture") from erreur

    def _lire_rejeu(self, dossier: Path) -> dict:
        resume = _json(dossier / "summary.json")
        trades = list(csv.DictReader(io.StringIO(_texte(dossier / "trades.csv"))))
        temps, capital, decisions, noms_decisions = [], [], [], []
        probas: dict[str, list] = {}
        sorties: dict[str, list] = {}
        entrees: dict[str, list] = {}
        for ligne in _texte(dossier / "reseau.jsonl").splitlines():
            r = json.loads(ligne)
            temps.append(int(datetime.fromisoformat(r["time"]).timestamp()))
            capital.append(r["capital"])
            if r["decision"] not in noms_decisions:
                noms_decisions.append(r["decision"])
            decisions.append(noms_decisions.index(r["decision"]))
            for groupe, cible in (("probas", probas), ("sorties", sorties), ("entrees", entrees)):
                for cle, valeur in r[groupe].items():
                    cible.setdefault(cle, []).append(_court(valeur))
        stops, cibles, prechauffage = [], [], 0
        for ligne in _texte(dossier / "journal.jsonl").splitlines():
            decision = json.loads(ligne)["decision"]
            prechauffage += decision["reason"] == "prechauffage"
            caps = decision.get("caps") or {}
            stops.append(caps.get("stop"))
            cibles.append(caps.get("target"))
        return propre({"resume": resume, "trades": trades, "temps": temps, "prechauffage": prechauffage,
                       "capital": capital, "decisions": {"noms": noms_decisions, "codes": decisions},
                       "probas": probas, "sorties": sorties, "entrees": entrees,
                       "caps": {"stop": stops, "cible": cibles}})

    # --- Prix ---

    def prix(self, nom: str, debut: str | None, fin: str | None, echelle: str) -> dict:
        """Barres du fichier de donnees du run : horaires, ou journalieres pour la vue d'ensemble. Instants
        d'ouverture, en secondes. Le bloc de test n'est lu que s'il a deja ete ouvert."""
        dossier = self.dossier(nom)
        config = self.config(dossier)
        chemin = (self.racine / config["donnees"]).resolve()
        if not chemin.is_relative_to((self.racine / "data").resolve()) or not chemin.is_file():
            raise Introuvable("fichier de donnees")
        test_ouvert = (dossier / "benchmark").is_dir()
        limite = None if test_ouvert else datetime.combine(config["debut_test"], datetime.min.time(), UTC)
        barres = self._memo(chemin, f"barres-{limite}", lambda c: _barres(c, limite))
        if echelle == "jour":
            barres = self._memo(chemin, f"jours-{limite}", lambda _: _journalieres(barres))
        a = int(datetime.fromisoformat(debut).timestamp()) if debut else None
        b = int(datetime.fromisoformat(fin).timestamp()) if fin else None
        choisies = [list(x) for x in barres if (a is None or x[0] >= a) and (b is None or x[0] < b)]
        return {"barres": choisies, "test_ouvert": test_ouvert, "debut_test": config["debut_test"].isoformat()}

    # --- Marches ---

    def marches(self) -> list[dict]:
        """Fichiers horaires de data/prepared/ : un marche par fichier, le symbole avant le premier tiret."""
        marches = []
        for chemin in sorted((self.racine / "data" / "prepared").glob("*-1h.csv")):
            try:
                marches.append(self._memo(chemin, "marche", _marche))
            except (OSError, ValueError, IndexError):
                continue  # fichier en cours d'ecriture par un telechargement
        return marches

    # --- Configuration ---

    def configuration(self, depuis: str | None) -> dict:
        """Texte d'une configuration, celle du bot ou celle d'un run, et ses champs pour le formulaire."""
        chemin = (self.dossier(depuis) if depuis else self.racine / "evolution") / "config.toml"
        texte = _texte(chemin)
        return propre({"texte": texte, "champs": champs(texte), "source": depuis or "evolution/config.toml"})


def champs(texte: str) -> list[dict]:
    """Champs d'une configuration : type lu par tomllib, section et commentaire lus dans le texte, position de
    la valeur dans sa ligne. Leve tomllib.TOMLDecodeError si le texte n'est pas du TOML."""
    valeurs = tomllib.loads(texte, parse_float=Decimal)
    trouves, section = [], None
    for numero, ligne in enumerate(texte.splitlines()):
        if trouve := SECTION.match(ligne):
            section = trouve.group(1)
            continue
        trouve = AFFECTATION.match(ligne)
        if not trouve or trouve.group(1) not in valeurs:
            continue
        valeur = valeurs[trouve.group(1)]
        genre = ("booleen" if isinstance(valeur, bool) else "entier" if isinstance(valeur, int)
                 else "decimal" if isinstance(valeur, Decimal) else "date" if isinstance(valeur, date)
                 else "liste" if isinstance(valeur, list) else "table" if isinstance(valeur, dict) else "texte")
        trouves.append({"cle": trouve.group(1), "section": section, "type": genre, "valeur": valeur,
                        "commentaire": (trouve.group(3) or "").lstrip("# ").strip(), "ligne": numero,
                        "debut": trouve.start(2), "fin": trouve.end(2)})
    return propre(trouves)


def _barres(chemin: Path, limite: datetime | None) -> list[tuple]:
    """(ouverture en secondes, ouverture, haut, bas, cloture, volume), prix en texte tels que le fichier les
    donne ; time y est l'instant de cloture."""
    barres = []
    lecteur = csv.reader(io.StringIO(_texte(chemin)))
    next(lecteur)
    for time, *valeurs in lecteur:
        cloture = datetime.fromisoformat(time)
        if limite is not None and cloture > limite:
            break  # le fichier est chronologique : tout ce qui suit est dans le bloc de test
        barres.append((int((cloture - HEURE).timestamp()), *valeurs))
    return barres


def _marche(chemin: Path) -> dict:
    """Premiere et derniere barre d'un fichier prepare, leur nombre, et le plus de decimales significatives d'un
    prix : le pas de prix le plus grossier que le fichier admet est 10 puissance moins ce nombre."""
    lignes = _texte(chemin).splitlines()[1:]
    decimales = 0
    for ligne in lignes:
        for prix in ligne.split(",")[1:5]:
            if "." in prix:
                decimales = max(decimales, len(prix.split(".", 1)[1].rstrip("0")))
    ouverture = lambda ligne: (datetime.fromisoformat(ligne.split(",", 1)[0]) - HEURE).isoformat()
    return {"symbole": chemin.stem.split("-")[0], "donnees": f"data/prepared/{chemin.name}", "barres": len(lignes),
            "premiere": ouverture(lignes[0]), "derniere": ouverture(lignes[-1]), "decimales_prix": decimales,
            "octets": chemin.stat().st_size}


def _journalieres(barres: list[tuple]) -> list[tuple]:
    """Barres du jour UTC, comparees en decimal."""
    jours: dict[int, list] = {}
    for t, ouverture, haut, bas, cloture, volume in barres:
        jour = t - t % 86400
        j = jours.get(jour)
        if j is None:
            jours[jour] = [jour, Decimal(ouverture), Decimal(haut), Decimal(bas), Decimal(cloture), Decimal(volume)]
            continue
        j[2], j[3], j[4], j[5] = max(j[2], Decimal(haut)), min(j[3], Decimal(bas)), Decimal(cloture), \
            j[5] + Decimal(volume)
    return [(j[0], *(str(v) for v in j[1:])) for j in jours.values()]
