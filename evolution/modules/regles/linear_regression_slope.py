"""Pente de la regression lineaire des clotures sur n barres (modules/rules/linear_regression_slope.py) : son
signe. Intensite : deplacement ajuste sur la periode, en unites de volatilite ramenees a l'horizon par racine de n,
plafonne a 1.
"""
import math

import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_linear_regression_slope"
GENES = (ECHELLE, Gene("n", "entier", 2, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    c = b["cloture"]
    t = torch.arange(c.shape[0], dtype=torch.float64)
    lignes = []
    for n in range(2, 101):
        # Sur la fenetre, sum (i - moyenne des i) C_i avec i = t - (debut de la fenetre) : sommes glissantes.
        somme_c, somme_tc = ind.somme(c, n), ind.somme(t * c, n)
        covariance = somme_tc - (t - n + 1 + (n - 1) / 2) * somme_c
        pente = covariance / (n * (n * n - 1) / 12)
        echelle = ind.volatilite(b, n) * math.sqrt(n)
        lignes.append(ind.vote(ind.signe(pente), ind.plafond(pente.abs() * (n - 1) / echelle), echelle > 0))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 2)
CUDA = lecture_cuda(NOM, 1, 2)
