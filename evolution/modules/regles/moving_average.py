"""Cloture contre sa moyenne mobile simple sur n barres (modules/rules/moving_average.py) : au-dessus +1, en dessous
-1. Intensite : ecart en unites de volatilite, plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_moving_average"
GENES = (ECHELLE, Gene("n", "entier", 2, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    lignes = []
    for n in range(2, 101):
        ecart = b["cloture"] - ind.somme(b["cloture"], n) / n
        r = ind.volatilite(b, n)
        lignes.append(ind.vote(ind.signe(ecart), ind.plafond(ecart.abs() / r), r > 0))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 2)
CUDA = lecture_cuda(NOM, 1, 2)
