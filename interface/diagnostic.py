"""Diagnostic du poste pour l'interface : ce qu'il faut pour entrainer, verifie sans rien lancer sur la GPU.

Le controle de PyTorch importe torch dans un processus a part. Il est refuse pendant une tache : il ouvrirait
CUDA a cote du bot, sur une GPU de 4 Go.
"""
import json
import shutil
import subprocess
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from interface import systeme, windows

CACHE_NOYAUX = Path(tempfile.gettempdir()) / "tradingbot-noyaux"  # evolution/compilation.py
CONTROLE_TORCH = ("import json, torch; print(json.dumps({'version': torch.__version__, 'cuda': torch.version.cuda, "
                  "'disponible': torch.cuda.is_available(), 'cartes': torch.cuda.device_count()}))")


def _contenu(dossier: Path) -> dict:
    fichiers = [f for f in dossier.rglob("*") if f.is_file()] if dossier.is_dir() else []
    return {"existe": dossier.is_dir(), "fichiers": len(fichiers), "octets": sum(f.stat().st_size for f in fichiers)}


def _date(chemin: Path) -> str:
    return datetime.fromtimestamp(chemin.stat().st_mtime, UTC).isoformat()


def rapide(racine: Path, python: str, verifier_config) -> dict:
    """Controles sans PyTorch : Python des taches, pilote NVIDIA, donnees, disque, cache des noyaux, configuration."""
    version = subprocess.run([python, "--version"], capture_output=True, encoding="utf-8", errors="replace",
                             creationflags=windows.SANS_FENETRE)
    try:
        pilote = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                                capture_output=True, encoding="utf-8", errors="replace", timeout=10,
                                creationflags=windows.SANS_FENETRE).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pilote = None
    config = racine / "evolution" / "config.toml"
    texte = config.read_text(encoding="utf-8")
    donnees = racine / tomllib.loads(texte).get("donnees", "")
    disque = shutil.disk_usage(racine)
    web = racine / "interface" / "web" / "dist" / "index.html"
    return {
        "python": {"chemin": python, "venv": ".venv" in Path(python).parts, "version": (version.stdout or version.stderr).strip()},
        "gpu": systeme.gpu(),
        "pilote": pilote,
        "donnees": {"chemin": donnees.relative_to(racine).as_posix() if donnees.is_relative_to(racine) else str(donnees),
                    "existe": donnees.is_file(), "octets": donnees.stat().st_size if donnees.is_file() else None,
                    "modifie": _date(donnees) if donnees.is_file() else None},
        "disque": {"libre": disque.free, "total": disque.total},
        "noyaux": {"chemin": str(CACHE_NOYAUX), **_contenu(CACHE_NOYAUX)},
        "etat_interface": {"chemin": "interface/etat", **_contenu(racine / "interface" / "etat")},
        "configuration": {"chemin": "evolution/config.toml", "erreur": verifier_config(texte)},
        "web": {"construit": web.is_file(), "modifie": _date(web) if web.is_file() else None},
    }


def torch(python: str) -> dict:
    """PyTorch et CUDA vus par le Python des taches."""
    controle = subprocess.run([python, "-c", CONTROLE_TORCH], capture_output=True, encoding="utf-8", errors="replace",
                              timeout=180, creationflags=windows.SANS_FENETRE)
    if controle.returncode != 0:
        lignes = controle.stderr.strip().splitlines()
        return {"ok": False, "erreur": lignes[-1] if lignes else f"code de sortie {controle.returncode}"}
    return {"ok": True, **json.loads(controle.stdout.strip().splitlines()[-1])}
