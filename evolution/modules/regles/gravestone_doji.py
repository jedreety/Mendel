"""Doji pierre tombale (modules/rules/gravestone_doji.py) : doji, meche basse d'au plus R/10, meche haute plus
longue. Rejet des hauts : -1. Intensite : meche haute sur R, plafonnee a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_gravestone_doji"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    haute = ind.meche_haute(b)
    motif = (ind.corps(b).abs() <= r / 10) & (ind.meche_basse(b) <= r / 10) & (haute > r / 10)
    return ind.vote(-1.0, ind.plafond(haute / r), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
