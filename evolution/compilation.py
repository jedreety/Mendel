"""Compilation de noyaux CUDA a l'execution, par NVRTC, livre avec PyTorch : aucune boite a outils CUDA.

Un noyau compile est garde sur le disque, dans le repertoire temporaire du systeme, sous l'empreinte de son
texte, de son nom, de l'architecture de la GPU et de la version de PyTorch (donc de NVRTC) : un run qui
demarre ou reprend ne recompile que ce qui a change. Le cache peut etre efface a tout moment.
"""
import hashlib
import os
import tempfile
from pathlib import Path

import torch

CACHE = Path(tempfile.gettempdir()) / "tradingbot-noyaux"
_compiles: dict = {}


def compiler(texte: str, nom: str):
    """Noyau `nom` du texte CUDA (declare extern "C"), charge une seule fois par processus pour un meme texte."""
    cle = (nom, texte)
    if cle not in _compiles:
        from torch.cuda._utils import _cuda_load_module, _nvrtc_compile

        proprietes = torch.cuda.get_device_properties(torch.cuda.current_device())
        empreinte = hashlib.sha256(
            f"{torch.__version__}|{proprietes.major}.{proprietes.minor}|{nom}|{texte}".encode("utf-8")).hexdigest()
        chemin = CACHE / f"{empreinte}.cubin"
        if chemin.exists():
            binaire = chemin.read_bytes()
        else:
            _sans_boite_a_outils()
            binaire, _ = _nvrtc_compile(texte, nom)
            CACHE.mkdir(parents=True, exist_ok=True)
            provisoire = chemin.with_name(f"{chemin.name}.{os.getpid()}.tmp")
            provisoire.write_bytes(binaire)
            os.replace(provisoire, chemin)
        _compiles[cle] = _cuda_load_module(binaire, [nom])[nom]
    return _compiles[cle]


def _sans_boite_a_outils() -> None:
    """PyTorch ajoute les en-tetes d'une boite a outils CUDA a toute compilation NVRTC, et en exige une.

    Les noyaux n'incluent aucun en-tete : NVRTC suffit. Faute de boite a outils, le repertoire de PyTorch en
    tient lieu.
    """
    from torch.utils import cpp_extension

    if cpp_extension.CUDA_HOME is None:
        cpp_extension.CUDA_HOME = str(Path(torch.__file__).parent)
