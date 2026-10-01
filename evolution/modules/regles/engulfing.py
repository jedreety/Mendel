"""Avalement (modules/rules/engulfing.py) : le corps de la derniere bougie englobe celui de la precedente, de
couleur opposee. Haussier +1, baissier -1, sinon s'abstient. Intensite : corps de la derniere sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_engulfing"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    p = ind.decaler(b, 1)
    c, pc = ind.corps(b), ind.corps(p)
    hausse = (pc < 0) & (c > 0) & (b["ouverture"] <= p["cloture"]) & (b["cloture"] > p["ouverture"])
    baisse = (pc > 0) & (c < 0) & (b["ouverture"] >= p["cloture"]) & (b["cloture"] < p["ouverture"])
    return ind.vote(torch.where(hausse, 1.0, -1.0), ind.plafond(c.abs() / r), hausse | baisse)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
