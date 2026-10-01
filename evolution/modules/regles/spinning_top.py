"""Toupie (modules/rules/spinning_top.py) : petit corps, entre R/10 et R/2, et deux meches plus longues que lui.
La regle vote 0, l'indecision : son signal est la presence du motif, 1 ou 0.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_spinning_top"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    c = ind.corps(b).abs()
    motif = (r / 10 < c) & (c < r / 2) & (ind.meche_haute(b) > c) & (ind.meche_basse(b) > c)
    return torch.where(motif, 1.0, 0.0)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
