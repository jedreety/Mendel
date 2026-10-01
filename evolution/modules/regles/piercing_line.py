"""Ligne penetrante, sans gap (modules/rules/piercing_line.py) : longue bougie rouge (corps d'au moins R/2), puis
bougie verte qui ouvre au plus a sa cloture et clot au-dessus du milieu de son corps, sans depasser son ouverture.
Vote +1. Intensite : corps de la verte sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_piercing_line"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    p = ind.decaler(b, 1)
    c, pc = ind.corps(b), ind.corps(p)
    milieu = (p["ouverture"] + p["cloture"]) / 2
    motif = ((pc < 0) & (pc.abs() >= r / 2) & (c > 0) & (b["ouverture"] <= p["cloture"])
             & (milieu < b["cloture"]) & (b["cloture"] < p["ouverture"]))
    return ind.vote(1.0, ind.plafond(c / r), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
