"""Pinces (modules/rules/tweezer.py) : deux plus bas egaux a R/20 pres, rouge puis verte : +1. Deux plus hauts
egaux, verte puis rouge : -1. Sinon s'abstient. Intensite : corps de la derniere bougie sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_tweezer"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    p = ind.decaler(b, 1)
    c, pc = ind.corps(b), ind.corps(p)
    hausse = (pc < 0) & (c > 0) & ((p["bas"] - b["bas"]).abs() <= r / 20)
    baisse = ~hausse & (pc > 0) & (c < 0) & ((p["haut"] - b["haut"]).abs() <= r / 20)
    return ind.vote(torch.where(hausse, 1.0, -1.0), ind.plafond(c.abs() / r), hausse | baisse)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
