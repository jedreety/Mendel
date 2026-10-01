"""Etoile du soir, sans gap (modules/rules/evening_star.py) : longue bougie verte (corps d'au moins R/2), petit
corps (sous R/2), puis bougie rouge qui clot en deca de 30 % du corps de la premiere. Vote -1. Intensite : corps de
la rouge sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_evening_star"
GENES = (ECHELLE,)
ORDONNES = ()
PENETRATION = 0.3


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    premiere, etoile = ind.decaler(b, 2), ind.decaler(b, 1)
    c1, c2, c3 = ind.corps(premiere), ind.corps(etoile), ind.corps(b)
    motif = ((c1 > 0) & (c1 >= r / 2) & (c2.abs() < r / 2) & (c3 < 0)
             & (b["cloture"] < premiere["cloture"] - PENETRATION * c1))
    return ind.vote(-1.0, ind.plafond(c3.abs() / r), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
