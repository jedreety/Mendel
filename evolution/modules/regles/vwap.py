"""Cloture contre le VWAP glissant sur n barres (modules/rules/vwap.py), prix typique pondere par le volume : au-dessus
+1, en dessous -1 ; s'abstient sans volume. Intensite : ecart en unites de volatilite, plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_vwap"
GENES = (ECHELLE, Gene("n", "entier", 1, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    v = b["volume"]
    pondere = (b["haut"] + b["bas"] + b["cloture"]) / 3 * v
    lignes = []
    for n in range(1, 101):
        ecart = b["cloture"] - ind.somme(pondere, n) / ind.somme(v, n)
        r = ind.volatilite(b, n)
        y = ind.vote(ind.signe(ecart), ind.plafond(ecart.abs() / r), (ind.compte(v > 0, n) > 0) & (r > 0))
        lignes.append(y)
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 1)
CUDA = lecture_cuda(NOM, 1, 1)
