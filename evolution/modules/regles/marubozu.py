"""Marubozu (modules/rules/marubozu.py) : corps long (au moins R/2), meches d'au plus R/10 chacune. Vote la
couleur. Intensite : corps sur R, plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_marubozu"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    c = ind.corps(b)
    motif = (c != 0) & (c.abs() >= r / 2) & (ind.meche_haute(b) <= r / 10) & (ind.meche_basse(b) <= r / 10)
    return ind.vote(ind.signe(c), ind.plafond(c.abs() / r), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
