"""Couverture en nuage noir, sans gap (modules/rules/dark_cloud_cover.py) : longue bougie verte (corps d'au moins
R/2), puis bougie rouge qui ouvre au moins a sa cloture et clot sous le milieu de son corps, sans passer sous son
ouverture. Vote -1. Intensite : corps de la rouge sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_dark_cloud_cover"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    p = ind.decaler(b, 1)
    c, pc = ind.corps(b), ind.corps(p)
    milieu = (p["ouverture"] + p["cloture"]) / 2
    motif = ((pc > 0) & (pc >= r / 2) & (c < 0) & (b["ouverture"] >= p["cloture"])
             & (p["ouverture"] < b["cloture"]) & (b["cloture"] < milieu))
    return ind.vote(-1.0, ind.plafond(c.abs() / r), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
