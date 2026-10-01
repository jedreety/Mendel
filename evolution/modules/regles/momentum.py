"""Momentum de la regle du moteur (modules/rules/momentum.py) : sens de la variation de cloture sur n barres.
Intensite : variation en unites de volatilite, ramenee a l'horizon par racine de n, plafonnee a 1.
"""
import math

import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_momentum"
GENES = (ECHELLE, Gene("n", "entier", 1, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    lignes = []
    for n in range(1, 101):
        ecart = b["cloture"] - ind.avant(b["cloture"], n)
        echelle = ind.volatilite(b, n) * math.sqrt(n)
        lignes.append(ind.vote(ind.signe(ecart), ind.plafond(ecart.abs() / echelle), echelle > 0))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 1)
CUDA = lecture_cuda(NOM, 1, 1)
