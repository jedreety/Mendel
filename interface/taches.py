"""Taches lancees par l'interface : les commandes du README, comme au terminal.

Chaque tache tourne dans sa propre console Windows, cachee, et ecrit sa sortie dans un fichier : elle survit a
l'interface, qui la retrouve a son redemarrage. L'arret propre envoie un vrai Ctrl+C a cette console : le bot
finit la generation en cours et ecrit son point de sauvegarde ; ses processus de rejeu ignorent le signal
(evolution/rejeu.py). Un second Ctrl+C l'interrompt sur-le-champ, comme au clavier.

Une seule tache a la fois, telechargement d'un marche compris : les autres se servent toutes de la GPU. Le
benchmark final ouvre le bloc de test, une seule fois : il part sans run a blanc (--sans-a-blanc), le champion
face au bot tire au hasard et a l'achat conserve ; le bot refait ensuite ses propres verifications avant de
poser son verrou.
"""
import json
import os
import re
import subprocess
import threading
import tomllib
from pathlib import Path

from adapters.system_clock import SystemClock
from interface import windows
from interface.lecture import Introuvable, Lecteur

TYPES = ("nouveau", "reprendre", "a-blanc", "hasard", "verifier", "benchmark", "donnees")
SUFFIXES = {"nouveau": "-evolution", "a-blanc": "-evolution-a-blanc", "hasard": "-evolution-hasard"}
LIGNE_RUN = re.compile(rb"^Run (\S+) \(", re.MULTILINE)
EN_COURS = ("en cours", "arret demande")
BOTS_VERIFIES = (128, 16384)
GENERATIONS_PLUS = 100_000  # generations de plus au plus, a la reprise
SYMBOLE = re.compile(r"^[A-Z0-9]{5,20}$")
MOIS = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
NOM_MAX = 60
QUEUE_JOURNAL = 65536  # octets du journal envoyes a l'ouverture
LECTURE_MAX = 262144
GARDEES = 200
# Relit une configuration avec le lecteur du bot lui-meme : les memes regles, sans les recopier.
LIRE_CONFIG = "import sys; from evolution.config import lire; lire(sys.stdin.read())"


class ErreurDemande(Exception):
    pass


def _maintenant():
    return SystemClock().now()


class Taches:
    """nommer(run, nom) : donne son nom au bot qu'une tache « nouveau » vient de creer."""

    def __init__(self, racine: Path, python: str, lecteur: Lecteur | None, nommer=None):
        self.racine, self.python, self.lecteur, self.nommer = racine, python, lecteur, nommer
        self.dossier = racine / "interface" / "etat"
        self.fichier = self.dossier / "taches.json"
        self.verrou = threading.RLock()
        self.processus: dict[str, subprocess.Popen] = {}
        self.liste: list[dict] = json.loads(self.fichier.read_text(encoding="utf-8")) if self.fichier.exists() else []

    # --- Consultation ---

    def lister(self) -> list[dict]:
        with self.verrou:
            return [dict(t) for t in reversed(self.liste)]

    def vivante(self) -> dict | None:
        with self.verrou:
            return next((dict(t) for t in self.liste if t["etat"] in EN_COURS), None)

    def pid_actif(self) -> int | None:
        tache = self.vivante()
        return tache["pid"] if tache else None

    def connaissance(self, nom: str) -> tuple[bool, float | None]:
        """Pour le lecteur : une tache ecrit-elle ce run, et quand la derniere qui l'a ecrit s'est-elle arretee."""
        with self.verrou:
            siennes = [t for t in self.liste if t.get("run") == nom and t["type"] != "benchmark"]
        if any(t["etat"] in EN_COURS for t in siennes):
            return True, None
        fins = [t["fin_s"] for t in siennes if t.get("fin_s")]
        return False, max(fins) if fins else None

    def fichier_journal(self, ident: str) -> Path:
        return self.racine / self._tache(ident)["journal"]

    def journal(self, ident: str, depuis: int | None) -> dict:
        """Sortie d'une tache a partir de l'octet depuis, en lignes completes ; sans depuis, sa fin."""
        tache = self._tache(ident)
        chemin = self.racine / tache["journal"]
        taille = chemin.stat().st_size if chemin.exists() else 0
        debut_queue = depuis is None or depuis < 0 or depuis > taille
        if debut_queue:
            depuis = max(0, taille - QUEUE_JOURNAL)
        brut = windows.lire(chemin, depuis, min(taille - depuis, LECTURE_MAX)) if taille > depuis else b""
        if debut_queue and depuis > 0:  # commencer a une ligne entiere
            coupe = brut.find(b"\n") + 1
            brut, depuis = brut[coupe:], depuis + coupe
        if tache["etat"] in EN_COURS:
            brut = brut[:brut.rfind(b"\n") + 1]
        return {"texte": brut.decode("utf-8", errors="replace"), "position": depuis + len(brut)}

    # --- Lancement ---

    def verifier_config(self, texte: str) -> str | None:
        """None si le bot accepte cette configuration, sinon son message d'erreur."""
        verification = subprocess.run([self.python, "-c", LIRE_CONFIG], input=texte, cwd=self.racine,
                                      capture_output=True, encoding="utf-8", errors="replace", timeout=60,
                                      env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                                      creationflags=windows.SANS_FENETRE)
        if verification.returncode == 0:
            return None
        lignes = verification.stderr.strip().splitlines()
        return lignes[-1] if lignes else f"code de sortie {verification.returncode}"

    def lancer(self, demande: dict) -> dict:
        with self.verrou:
            if self.vivante() is not None:
                raise ErreurDemande("Une tache tourne deja : la GPU ne sert qu'a une a la fois.")
            genre = demande.get("type")
            if genre not in TYPES:
                raise ErreurDemande(f"type de tache inconnu : {genre!r}")
            instant = _maintenant()
            ident = f"{instant:%Y%m%dT%H%M%SZ}-{genre}"
            arguments, run, extras = self._arguments(genre, demande, ident)
            journal = self.dossier / "journaux" / f"{ident}.log"
            journal.parent.mkdir(parents=True, exist_ok=True)
            processus = self._demarrer([self.python, *arguments], journal)
            etat = windows.processus(processus.pid)
            tache = {"id": ident, "type": genre, "commande": "python " + " ".join(arguments), "run": run, **extras,
                     "debut": instant.isoformat(), "fin": None, "fin_s": None, "pid": processus.pid,
                     "creation": etat["creation"] if etat else None,
                     "journal": journal.relative_to(self.racine).as_posix(), "etat": "en cours", "code": None,
                     "arrets": 0, "tuee": False}
            self.processus[ident] = processus
            self.liste = [*self.liste, tache][-GARDEES:]
            self._ecrire()
            return dict(tache)

    def _arguments(self, genre: str, demande: dict, ident: str) -> tuple[list[str], str | None, dict]:
        """Arguments de python, run vise, et ce que la tache retient pour l'affichage : nom du bot, run reel d'un
        temoin, generation de depart et generation visee (objectif, None sans limite). Les dossiers sont passes
        relativement a la racine du depot, comme dans le README : le benchmark compare ces chemins a ceux notes
        dans les runs a blanc."""
        if genre == "nouveau":
            texte = demande.get("config") or ""
            erreur = self.verifier_config(texte)
            if erreur:
                raise ErreurDemande(f"Configuration refusee par le bot : {erreur}")
            chemin = self.dossier / "configs" / f"{ident}.toml"
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(texte, encoding="utf-8")
            extras = {"nom": str(demande.get("nom") or "").strip()[:NOM_MAX],
                      "objectif": tomllib.loads(texte)["generations_max"] or None}
            return ["-m", "evolution.run", "--config", chemin.relative_to(self.racine).as_posix()], None, extras
        if genre == "verifier":
            bots = demande.get("bots", 256)
            if not isinstance(bots, int) or not BOTS_VERIFIES[0] <= bots <= BOTS_VERIFIES[1]:
                raise ErreurDemande(f"bots : un entier de {BOTS_VERIFIES[0]} a {BOTS_VERIFIES[1]}")
            return ["-m", "evolution.verifier", "--bots", str(bots)], None, {}
        if genre == "donnees":
            return self._donnees(demande)
        nom = self._run(demande.get("run"))
        resume = self.lecteur.resume(nom)
        if not resume["point_de_sauvegarde"]:
            raise ErreurDemande(f"{nom} n'a pas encore de point de sauvegarde.")
        if genre == "reprendre":
            return self._reprise(nom, resume, demande)
        if resume["mode"] != "reel":
            raise ErreurDemande(f"{nom} n'est pas un run reel.")
        if genre in ("a-blanc", "hasard"):
            return ["-m", "evolution.run", f"--{genre}", f"runs/{nom}"], None, {"source": nom}
        # Benchmark final : le bloc de test ne s'ouvre qu'une fois.
        if resume["benchmark"]:
            raise ErreurDemande("Le bloc de test de ce run a deja ete ouvert.")
        if demande.get("confirmation") != nom:
            raise ErreurDemande("Confirmation absente : retapez le nom exact du run reel.")
        return ["-m", "evolution.benchmark", f"runs/{nom}", "--sans-a-blanc"], nom, {}

    def _reprise(self, nom: str, resume: dict, demande: dict) -> tuple[list[str], str, dict]:
        """Une fois : exactement `generations` de plus. En boucle : jusqu'a l'arret demande. Sans l'un ni l'autre,
        le run reprend avec ses propres limites ; c'est la seule reprise d'un temoin."""
        arguments = ["-m", "evolution.run", "--reprendre", f"runs/{nom}"]
        generations, boucle = demande.get("generations"), demande.get("boucle") is True
        depart = resume["generation"]
        if (boucle or generations is not None) and resume["mode"] != "reel":
            raise ErreurDemande("Un témoin garde le nombre de générations de son run réel : il se reprend tel quel.")
        if boucle:
            return [*arguments, "--generations-max", "0", "--stagnation-max", "0"], nom, {"depart": depart, "objectif": None}
        if generations is None:
            return arguments, nom, {"depart": depart, "objectif": resume["generations_max"]}
        if isinstance(generations, bool) or not isinstance(generations, int) or not 1 <= generations <= GENERATIONS_PLUS:
            raise ErreurDemande(f"generations : un entier de 1 à {GENERATIONS_PLUS}")
        objectif = depart + generations
        return [*arguments, "--generations-max", str(objectif), "--stagnation-max", "0"], nom, {"depart": depart, "objectif": objectif}

    def _donnees(self, demande: dict) -> tuple[list[str], None, dict]:
        """Telechargement d'un marche en barres horaires. Un fichier deja prepare n'est jamais remplace d'ici :
        les runs qui le lisent en gardent l'empreinte."""
        symbole = str(demande.get("symbole") or "").strip().upper()
        debut, fin = demande.get("debut"), demande.get("fin")
        if not SYMBOLE.match(symbole):
            raise ErreurDemande("symbole : des lettres et des chiffres, comme EURUSDT")
        if not all(isinstance(m, str) and MOIS.match(m) for m in (debut, fin)) or debut > fin:
            raise ErreurDemande("mois : AAAA-MM, le premier avant le dernier")
        cible = self.racine / "data" / "prepared" / f"{symbole}-1h.csv"
        if cible.exists():
            raise ErreurDemande(f"{cible.name} existe déjà : les runs qui le lisent en gardent l'empreinte. "
                                "Pour le remplacer malgré tout, lancez le téléchargement depuis un terminal.")
        return ["-m", "scripts.fetch_binance", symbole, "1h", debut, fin], None, {"symbole": symbole}

    def _run(self, nom) -> str:
        try:
            return self.lecteur.dossier(nom if isinstance(nom, str) else "").name
        except Introuvable:
            raise ErreurDemande(f"run introuvable : {nom!r}") from None

    def _demarrer(self, commande: list[str], journal: Path) -> subprocess.Popen:
        """Console neuve et cachee : elle recevra Ctrl+C comme un terminal, sans toucher a celle de l'interface.
        La sortie va dans un fichier, pas dans un tube : la tache survit a l'arret de l'interface."""
        windows.autoriser_ctrl_c()  # la tache en herite
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 0  # SW_HIDE
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        with journal.open("ab") as sortie:
            return subprocess.Popen(commande, cwd=self.racine, stdin=subprocess.DEVNULL, stdout=sortie,
                                    stderr=subprocess.STDOUT, creationflags=windows.CONSOLE_NEUVE,
                                    startupinfo=info, env=env)

    # --- Arret ---

    def arreter(self, ident: str, mode: str) -> dict:
        with self.verrou:
            tache = self._tache(ident, interne=True)
            if tache["etat"] not in EN_COURS or not self._vivant(tache)[0]:
                raise ErreurDemande("Cette tache ne tourne plus.")
            if mode == "ctrl-c":
                if not windows.ctrl_c(self.python, tache["pid"]):
                    raise ErreurDemande("Ctrl+C n'a pas pu etre envoye a la console de la tache.")
                tache["arrets"] += 1
                tache["etat"] = "arret demande"
            elif mode == "tuer":
                windows.tuer(tache["pid"])
                tache["tuee"] = True
            else:
                raise ErreurDemande(f"mode d'arret inconnu : {mode!r}")
            self._ecrire()
            return dict(tache)

    # --- Surveillance ---

    def surveiller(self) -> bool:
        """Met a jour les taches en cours : run cree, fin du processus. True si quelque chose a change."""
        change = False
        with self.verrou:
            for tache in self.liste:
                if tache["etat"] not in EN_COURS:
                    continue
                if tache["run"] is None and tache["type"] in SUFFIXES:
                    tache["run"] = self._run_cree(tache)
                    change |= tache["run"] is not None
                    if tache["run"] is not None and tache.get("nom") and self.nommer:
                        self.nommer(tache["run"], tache["nom"])
                vivant, code = self._vivant(tache)
                if vivant:
                    continue
                instant = _maintenant()
                tache.update(fin=instant.isoformat(), fin_s=instant.timestamp(), code=code,
                             etat=self._etat_final(tache, code))
                self.processus.pop(tache["id"], None)
                change = True
            if change:
                self._ecrire()
        return change

    def _vivant(self, tache: dict) -> tuple[bool, int | None]:
        processus = self.processus.get(tache["id"])
        if processus is not None:
            code = processus.poll()
            return code is None, code
        etat = windows.processus(tache["pid"])  # tache d'une session precedente de l'interface
        return bool(etat and etat["vivant"] and etat["creation"] == tache["creation"]), None

    def _run_cree(self, tache: dict) -> str | None:
        """Dossier cree par la tache : annonce dans sa sortie, sinon le premier dossier au bon suffixe, date
        au plus tot de son lancement (le bot le nomme par l'heure de sa creation)."""
        chemin = self.racine / tache["journal"]
        if chemin.exists():
            trouve = LIGNE_RUN.search(windows.lire(chemin, 0, LECTURE_MAX))
            if trouve:
                return trouve.group(1).decode("utf-8")
        suffixe, depuis = SUFFIXES[tache["type"]], tache["id"][:16]
        candidats = sorted(n for n in self.lecteur.evolutions() if n.endswith(suffixe) and n[:16] >= depuis)
        return candidats[0] if candidats else None

    def _etat_final(self, tache: dict, code: int | None) -> str:
        if tache["tuee"]:
            return "tuee"
        if code is None:  # processus d'une session precedente : sa sortie dit s'il a echoue
            chemin = self.racine / tache["journal"]
            taille = chemin.stat().st_size if chemin.exists() else 0
            queue = windows.lire(chemin, max(0, taille - 4096)) if taille else b""
            return "echec" if b"Traceback" in queue else ("arretee" if tache["arrets"] else "terminee")
        if code == 0:
            return "arretee" if tache["arrets"] else "terminee"
        return "interrompue" if tache["arrets"] else "echec"

    def _tache(self, ident: str, interne: bool = False) -> dict:
        with self.verrou:
            for tache in self.liste:
                if tache["id"] == ident:
                    return tache if interne else dict(tache)
        raise Introuvable(f"tache {ident!r}")

    def _ecrire(self) -> None:
        self.dossier.mkdir(parents=True, exist_ok=True)
        provisoire = self.fichier.with_name(self.fichier.name + ".tmp")
        provisoire.write_text(json.dumps(self.liste, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(provisoire, self.fichier)
