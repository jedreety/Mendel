"""Doji libellule (modules/rules/dragonfly_doji.py) : doji, meche haute d'au plus R/10, meche basse plus longue.
Rejet des bas : +1. Intensite : meche basse sur R, plafonnee a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_dragonfly_doji"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    basse = ind.meche_basse(b)
    motif = (ind.corps(b).abs() <= r / 10) & (ind.meche_haute(b) <= r / 10) & (basse > r / 10)
    return ind.vote(1.0, ind.plafond(basse / r), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
