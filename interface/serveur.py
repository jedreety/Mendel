"""Serveur de l'interface du bot evolutif : application web, API JSON et flux d'evenements.

    python -m interface.serveur                  http://127.0.0.1:8765
    python -m interface.serveur --port 8800 --ouvrir

Bibliotheque standard seulement. L'interface ne touche pas au fonctionnement du bot : elle lit les dossiers de
runs (interface/lecture.py), lance les commandes du README (interface/taches.py), nomme les bots et envoie a la
corbeille ceux qu'on supprime (interface/bots.py). Elle n'importe pas evolution/, donc pas PyTorch. Elle
n'ecoute que sur 127.0.0.1 et n'accepte une commande que d'une page servie par elle-meme. L'arreter n'arrete pas
les taches en cours : elle les retrouve a son redemarrage.
"""
import argparse
import gzip
import json
import queue
import re
import subprocess
import sys
import threading
import tomllib
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from adapters.system_clock import SystemClock
from interface import diagnostic, windows
from interface.bots import Bots
from interface.lecture import Introuvable, Lecteur, Refus, champs, propre
from interface.systeme import Echantillonneur
from interface.taches import ErreurDemande, Taches

RACINE = Path(__file__).resolve().parent.parent
WEB = (RACINE / "interface" / "web" / "dist").resolve()
PORT_DEV = 5173  # serveur de developpement de Vite, qui relaie /api vers ce serveur
TYPES_MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
              ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json",
              ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2", ".map": "application/json"}
PERIODE_S = 1.0
COMPRESSION_MIN = 32768
CORPS_MAX = 1 << 20
TYPES_TELECHARGES = {".json": "application/json", ".csv": "text/csv; charset=utf-8", ".jsonl": "text/plain; charset=utf-8",
                     ".toml": "text/plain; charset=utf-8", ".log": "text/plain; charset=utf-8"}


class Brut:
    """Reponse a telecharger telle quelle : le contenu d'un fichier, sous son nom."""

    def __init__(self, contenu: bytes, nom: str):
        self.contenu, self.nom = contenu, nom


class Diffusion:
    """Evenements du serveur vers les pages ouvertes (Server-Sent Events)."""

    def __init__(self):
        self.abonnes: set[queue.Queue] = set()
        self.verrou = threading.Lock()

    def abonner(self) -> queue.Queue:
        file = queue.Queue(maxsize=2000)
        with self.verrou:
            self.abonnes.add(file)
        return file

    def desabonner(self, file: queue.Queue) -> None:
        with self.verrou:
            self.abonnes.discard(file)

    def nombre(self) -> int:
        with self.verrou:
            return len(self.abonnes)

    def publier(self, evenement: str, donnees) -> None:
        texte = f"event: {evenement}\ndata: {json.dumps(propre(donnees), ensure_ascii=False)}\n\n".encode("utf-8")
        with self.verrou:
            abonnes = list(self.abonnes)
        for file in abonnes:
            try:
                file.put_nowait(texte)
            except queue.Full:  # page trop lente : elle se resynchronise a sa reconnexion
                pass


class Surveillant:
    """Fil de surveillance : etat des taches, sortie de la tache en cours, runs et nouvelles generations.
    Il ne fait que des lectures d'attributs et de generations.jsonl (interface/lecture.py)."""

    def __init__(self, taches: Taches, lecteur: Lecteur, diffusion: Diffusion):
        self.taches, self.lecteur, self.diffusion = taches, lecteur, diffusion
        self.journaux: dict[str, int] = {}
        self.signatures: dict[str, tuple] = {}
        self.vues: dict[str, tuple[int, int | None]] = {}
        self.demarrage = True
        self.arret = threading.Event()
        self.fil = threading.Thread(target=self._boucle, name="surveillant", daemon=True)

    def demarrer(self) -> None:
        self.fil.start()

    def _boucle(self) -> None:
        while True:
            try:
                self._tour()
            except Exception:  # la surveillance ne doit jamais s'arreter
                traceback.print_exc()
            self.demarrage = False
            if self.arret.wait(PERIODE_S):
                return

    def _tour(self) -> None:
        if self.taches.surveiller():
            self.diffusion.publier("taches", self.taches.lister())
            self.diffusion.publier("runs", self.lecteur.runs())  # un run cesse d'etre actif a la fin de sa tache
        for tache in self.taches.lister()[:3]:
            self._journal(tache)
        changes = []
        presents = self.lecteur.evolutions()
        for nom in presents:
            dossier = self.lecteur.runs_dir / nom
            signature = tuple(_stat(dossier / f) for f in ("generations.jsonl", "etat.json", "pantheon.json",
                                                         "pantheon", "benchmark", "benchmark/rapport.json"))
            if self.signatures.get(nom) != signature:
                self.signatures[nom] = signature
                changes.append(nom)
        disparus = set(self.signatures) - set(presents)  # supprimes, depuis l'interface ou l'Explorateur
        for nom in disparus:
            del self.signatures[nom]
            self.vues.pop(nom, None)
        if not changes and not disparus:
            return
        for nom in changes:
            self._generations(nom)
        if not self.demarrage:
            self.diffusion.publier("runs", self.lecteur.runs())

    def _journal(self, tache: dict) -> None:
        """Nouvelles lignes de sortie d'une tache en cours, puis une derniere lecture a sa fin."""
        ident = tache["id"]
        if ident not in self.journaux:
            if tache["etat"] not in ("en cours", "arret demande"):
                return
            self.journaux[ident] = 0
        position = self.journaux[ident]
        suite = self.taches.journal(ident, position)
        if suite["position"] != position:
            self.diffusion.publier("journal", {"id": ident, "debut": position, **suite})
            self.journaux[ident] = suite["position"]
        if tache["etat"] not in ("en cours", "arret demande"):
            del self.journaux[ident]

    def _generations(self, nom: str) -> None:
        try:
            lignes = self.lecteur.generations(nom)
        except (Introuvable, OSError, ValueError):
            return
        derniere = lignes[-1]["generation"] if lignes else None
        vu = self.vues.get(nom)
        self.vues[nom] = (len(lignes), derniere)
        if vu is None:
            if self.demarrage:
                return
            vu = (0, None)  # run apparu pendant que l'interface tourne : tout est nouveau
        n, avant = vu
        if len(lignes) >= n and (n == 0 or lignes[n - 1]["generation"] == avant):
            if len(lignes) > n:
                self.diffusion.publier("generations", {"run": nom, "lignes": lignes[n:]})
        else:  # generations.jsonl reecrit a la reprise
            self.diffusion.publier("generations", {"run": nom, "reinitialiser": True})


def _stat(chemin: Path):
    try:
        etat = chemin.stat()
    except FileNotFoundError:
        return None
    return etat.st_mtime_ns, etat.st_size


class Gestionnaire(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "InterfaceBot"

    # --- Routage ---

    def do_GET(self):
        self._traiter("GET")

    def do_POST(self):
        self._traiter("POST")

    def _traiter(self, methode: str) -> None:
        url = urlsplit(self.path)
        chemin = unquote(url.path)
        if not self._hote_autorise():
            return self._repondre({"erreur": "hote refuse"}, 403)
        if not chemin.startswith("/api/"):
            return self._statique(chemin) if methode == "GET" else self._repondre({"erreur": "introuvable"}, 404)
        if methode == "POST" and not self._commande_autorisee():
            return self._repondre({"erreur": "commande refusee : origine inconnue"}, 403)
        if methode == "GET" and chemin == "/api/flux":
            return self._flux()
        requete = {cle: valeurs[-1] for cle, valeurs in parse_qs(url.query).items()}
        for m, motif, action in ROUTES:
            trouve = motif.fullmatch(chemin)
            if m == methode and trouve:
                try:
                    corps = self._corps() if methode == "POST" else None
                    resultat = action(self.server, requete, corps, *trouve.groups())
                    if isinstance(resultat, Brut):
                        self._telecharger(resultat)
                    elif resultat is not None:
                        self._repondre(resultat)
                except Introuvable as erreur:
                    self._repondre({"erreur": f"introuvable : {erreur}"}, 404)
                except (ErreurDemande, Refus) as erreur:
                    self._repondre({"erreur": str(erreur)}, 409)
                except (ValueError, KeyError, TypeError) as erreur:
                    self._repondre({"erreur": f"requete invalide : {erreur}"}, 400)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    pass
                except Exception as erreur:
                    traceback.print_exc()
                    self._repondre({"erreur": f"{type(erreur).__name__} : {erreur}"}, 500)
                return
        self._repondre({"erreur": "introuvable"}, 404)

    # --- Securite ---

    def _hote_autorise(self) -> bool:
        """Contre le rebond DNS : seule une page adressee a 127.0.0.1 ou localhost est servie."""
        return self.headers.get("Host", "") in self.server.hotes

    def _commande_autorisee(self) -> bool:
        """Une page d'un autre site ne peut pas poser cet en-tete sans que le navigateur demande la permission,
        que ce serveur ne donne jamais."""
        origine = self.headers.get("Origin")
        return self.headers.get("X-Interface") == "1" and (origine is None or origine in self.server.origines)

    # --- Reponses ---

    def _corps(self) -> dict:
        taille = int(self.headers.get("Content-Length") or 0)
        if taille > CORPS_MAX:
            raise ValueError("corps trop grand")
        return json.loads(self.rfile.read(taille).decode("utf-8")) if taille else {}

    def _repondre(self, donnees, statut: int = 200) -> None:
        corps = json.dumps(propre(donnees), ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._envoyer(corps, "application/json; charset=utf-8", statut, "no-store")

    def _telecharger(self, brut: Brut) -> None:
        genre = TYPES_TELECHARGES.get(Path(brut.nom).suffix, "application/octet-stream")
        self._envoyer(brut.contenu, genre, 200, "no-store",
                      {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(brut.nom)}"})

    def _envoyer(self, corps: bytes, genre: str, statut: int, cache: str, entetes: dict | None = None) -> None:
        """Une reponse ordinaire ferme sa connexion. Le flux d'evenements en garde une ouverte en permanence ;
        des connexions gardees en attente de reutilisation atteindraient la limite de six par hote du
        navigateur, et la requete suivante attendrait indefiniment."""
        compresse = len(corps) > COMPRESSION_MIN and "gzip" in self.headers.get("Accept-Encoding", "")
        if compresse:
            corps = gzip.compress(corps, 5)
        self.send_response(statut)
        self.send_header("Content-Type", genre)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        if compresse:
            self.send_header("Content-Encoding", "gzip")
        for cle, valeur in (entetes or {}).items():
            self.send_header(cle, valeur)
        self.end_headers()
        self.wfile.write(corps)
        self.close_connection = True

    def _statique(self, chemin: str) -> None:
        if not (WEB / "index.html").is_file():
            page = ("<!doctype html><meta charset=utf-8><title>Interface</title><body style='font-family:system-ui;"
                    "background:#f5f5f2;color:#1b1b19;padding:2rem'><h1>Application web non construite</h1><p>Dans "
                    "interface/web : <code>npm install</code> puis <code>npm run build</code>, et rechargez.</p>")
            return self._envoyer(page.encode("utf-8"), TYPES_MIME[".html"], 200, "no-store")
        fichier = (WEB / chemin.lstrip("/")).resolve()
        if not fichier.is_relative_to(WEB) or not fichier.is_file():
            fichier = WEB / "index.html"  # application d'une seule page : les routes sont dans le navigateur
        immuable = fichier.parent.name == "assets"  # Vite y met l'empreinte du contenu dans le nom
        self._envoyer(fichier.read_bytes(), TYPES_MIME.get(fichier.suffix, "application/octet-stream"), 200,
                      "public, max-age=31536000, immutable" if immuable else "no-cache")

    def _flux(self) -> None:
        file = self.server.diffusion.abonner()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")  # le flux, sans longueur annoncee, finit a la fermeture
            self.end_headers()
            self.wfile.write(b"retry: 3000\n\n")
            self.wfile.flush()
            while True:
                try:
                    texte = file.get(timeout=15)
                except queue.Empty:
                    texte = b": ping\n\n"
                self.wfile.write(texte)
                self.wfile.flush()
        except OSError:  # page fermee
            pass
        finally:
            self.server.diffusion.desabonner(file)
            self.close_connection = True

    def log_message(self, format, *args):  # les requetes ordinaires ne sont pas journalisees
        pass

    def log_error(self, format, *args):
        sys.stderr.write(f"interface : {format % args}\n")


# --- Actions de l'API : (serveur, requete, corps, groupes de l'URL) ---

def _etat(s, r, c):
    return {"maintenant": SystemClock().now().isoformat(), "racine": str(RACINE), "python": s.taches.python,
            "tache": s.taches.vivante()}


def _generations(s, r, c, nom):
    return s.lecteur.generations(nom, int(r.get("depuis", 0)))


def _rejeu(s, r, c, nom, genre, sous, trimestre):
    return s.lecteur.rejeu(nom, genre, sous, trimestre)


def _prix(s, r, c):
    return s.lecteur.prix(r["run"], r.get("debut"), r.get("fin"), r.get("echelle", "heure"))


def _verifier(s, r, c):
    texte = c.get("texte", "")
    erreur = s.taches.verifier_config(texte)
    try:
        trouves = champs(texte)
    except tomllib.TOMLDecodeError:
        trouves = None
    return {"ok": erreur is None, "erreur": erreur, "champs": trouves}


def _lancer(s, r, c):
    tache = s.taches.lancer(c)
    s.diffusion.publier("taches", s.taches.lister())
    return tache


def _arreter(s, r, c, ident):
    tache = s.taches.arreter(ident, c.get("mode", "ctrl-c"))
    s.diffusion.publier("taches", s.taches.lister())
    return tache


def _renommer(s, r, c, nom):
    resultat = s.bots.renommer(nom, c.get("nom", ""))
    s.diffusion.publier("runs", s.lecteur.runs())
    return resultat


def _supprimer(s, r, c, nom):
    resultat = s.bots.supprimer(nom)
    s.diffusion.publier("runs", s.lecteur.runs())
    return resultat


def _journal(s, r, c, ident):
    return s.taches.journal(ident, int(r["depuis"]) if "depuis" in r else None)


def _journal_brut(s, r, c, ident):
    chemin = s.taches.fichier_journal(ident)
    return Brut(windows.lire(chemin) if chemin.exists() else b"", chemin.name)


def _diagnostic(s, r, c):
    return diagnostic.rapide(RACINE, s.taches.python, s.taches.verifier_config)


def _torch(s, r, c):
    if s.taches.vivante() is not None:
        raise ErreurDemande("Une tache tourne : importer PyTorch ouvrirait CUDA a cote du bot. Relancez ce controle a son arret.")
    return diagnostic.torch(s.taches.python)


def _fichier(s, r, c, nom):
    return Brut(*s.lecteur.fichier(nom, r["chemin"]))


def _ouvrir(s, r, c):
    """Montre dans l'Explorateur le dossier d'un run ou l'un de ses fichiers, ou l'etat de l'interface."""
    if c.get("run"):
        dossier = s.lecteur.dossier(c["run"]).resolve()
        cible = (dossier / (c.get("chemin") or "")).resolve()
        if not cible.is_relative_to(dossier) or not cible.exists():
            raise Introuvable("chemin du run")
    elif c.get("cible") == "etat":
        cible = RACINE / "interface" / "etat"
        if not cible.is_dir():
            raise Introuvable("interface/etat : aucune tache lancee pour l'instant")
    else:
        raise ErreurDemande("rien a ouvrir")
    subprocess.Popen(["explorer", f"/select,{cible}"] if cible.is_file() else ["explorer", str(cible)])
    return {"ouvert": str(cible)}


_NOM = r"([A-Za-z0-9._-]+)"
ROUTES = [(m, re.compile(p), a) for m, p, a in (
    ("GET", r"/api/etat", _etat),
    ("GET", r"/api/runs", lambda s, r, c: s.lecteur.runs()),
    ("GET", rf"/api/runs/{_NOM}", lambda s, r, c, nom: s.lecteur.detail(nom)),
    ("GET", rf"/api/runs/{_NOM}/generations", _generations),
    ("GET", rf"/api/runs/{_NOM}/genealogie/{_NOM}", lambda s, r, c, nom, bot: s.lecteur.genealogie(nom, bot)),
    ("GET", rf"/api/runs/{_NOM}/rejeu/(pantheon|benchmark)/{_NOM}/{_NOM}", _rejeu),
    ("GET", rf"/api/runs/{_NOM}/rapport", lambda s, r, c, nom: s.lecteur.rapport(nom)),
    ("GET", rf"/api/runs/{_NOM}/fichiers", lambda s, r, c, nom: s.lecteur.fichiers(nom)),
    ("GET", rf"/api/runs/{_NOM}/fichier", _fichier),
    ("POST", rf"/api/bots/{_NOM}/nom", _renommer),
    ("POST", rf"/api/bots/{_NOM}/supprimer", _supprimer),
    ("GET", r"/api/marches", lambda s, r, c: s.lecteur.marches()),
    ("POST", r"/api/ouvrir", _ouvrir),
    ("GET", r"/api/diagnostic", _diagnostic),
    ("POST", r"/api/diagnostic/torch", _torch),
    ("GET", r"/api/prix", _prix),
    ("GET", r"/api/config", lambda s, r, c: s.lecteur.configuration(r.get("depuis"))),
    ("POST", r"/api/config/verifier", _verifier),
    ("GET", r"/api/taches", lambda s, r, c: s.taches.lister()),
    ("POST", r"/api/taches", _lancer),
    ("GET", rf"/api/taches/{_NOM}/journal", _journal),
    ("GET", rf"/api/taches/{_NOM}/journal/brut", _journal_brut),
    ("POST", rf"/api/taches/{_NOM}/arreter", _arreter),
    ("GET", r"/api/systeme", lambda s, r, c: s.echantillonneur.echantillons()),
)]


class Serveur(ThreadingHTTPServer):
    daemon_threads = True
    # Sous Windows, SO_REUSEADDR laisse un second serveur ecouter sur le meme port sans erreur : les requetes
    # iraient au hasard a l'un ou a l'autre. Sans lui, un second lancement echoue clairement.
    allow_reuse_address = False

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return  # page fermee pendant un echange : rien a signaler
        super().handle_error(request, client_address)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interface du bot evolutif.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ouvrir", action="store_true", help="ouvrir l'interface dans le navigateur")
    args = parser.parse_args()
    venv = RACINE / ".venv" / "Scripts" / "python.exe"
    python = str(venv if venv.is_file() else Path(sys.executable))
    try:
        serveur = Serveur(("127.0.0.1", args.port), Gestionnaire)
    except OSError:
        raise SystemExit(f"Le port {args.port} est deja pris : l'interface tourne peut-etre deja "
                         f"(http://127.0.0.1:{args.port}). Sinon, choisissez un autre port avec --port.")
    serveur.hotes = {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}
    serveur.origines = {f"http://{h}" for h in serveur.hotes} | {f"http://{h}:{PORT_DEV}" for h in
                                                                 ("127.0.0.1", "localhost")}
    serveur.diffusion = Diffusion()
    serveur.taches = Taches(RACINE, python, None)
    serveur.bots = Bots(RACINE, serveur.taches, None)
    serveur.lecteur = Lecteur(RACINE, serveur.taches.connaissance, serveur.bots.nom)
    serveur.taches.lecteur = serveur.lecteur
    serveur.taches.nommer = serveur.bots.nommer
    serveur.bots.lecteur = serveur.lecteur
    serveur.echantillonneur = Echantillonneur(
        RACINE, lambda: serveur.diffusion.nombre() > 0 or serveur.taches.vivante() is not None,
        serveur.taches.pid_actif, serveur.diffusion.publier)
    serveur.echantillonneur.demarrer()
    Surveillant(serveur.taches, serveur.lecteur, serveur.diffusion).demarrer()
    adresse = f"http://127.0.0.1:{args.port}"
    print(f"Interface : {adresse}  (Ctrl+C pour l'arreter ; les taches en cours continuent)", flush=True)
    if not (WEB / "index.html").is_file():
        print("Application web non construite : cd interface/web, npm install, npm run build.", flush=True)
    if args.ouvrir:
        webbrowser.open(adresse)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("Interface arretee.", flush=True)
    finally:
        serveur.server_close()


if __name__ == "__main__":
    main()
