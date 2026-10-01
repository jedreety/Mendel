"""Doji (modules/rules/doji.py) : corps d'au plus R/10. La regle vote 0, l'indecision : son signal est la
presence du motif, 1 ou 0. R : volatilite des 10 dernieres barres, motif compris.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_doji"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    return torch.where(ind.corps(b).abs() <= r / 10, 1.0, 0.0)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
