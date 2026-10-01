"""Barre interieure (modules/rules/inside_bar.py) : amplitude contenue dans celle de la precedente. La regle vote
0, la consolidation : son signal est la presence du motif, 1 ou 0.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_inside_bar"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    p = ind.decaler(b, 1)
    return torch.where((b["haut"] <= p["haut"]) & (b["bas"] >= p["bas"]), 1.0, 0.0)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
