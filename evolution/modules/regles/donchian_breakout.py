"""Cassure du canal de Donchian (modules/rules/donchian_breakout.py) : cloture au-dessus du plus haut des n barres
precedentes +1, sous leur plus bas -1, sinon s'abstient. Intensite : depassement en unites de volatilite, plafonne
a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_donchian_breakout"
GENES = (ECHELLE, Gene("n", "entier", 2, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    c = b["cloture"]
    lignes = []
    for n in range(2, 101):
        haut = ind.avant(ind.plus_haut(b["haut"], n), 1)
        bas = ind.avant(ind.plus_bas(b["bas"], n), 1)
        r = ind.volatilite(b, n)
        y = torch.where(c > haut, ind.plafond((c - haut) / r), torch.where(c < bas, -ind.plafond((bas - c) / r), 0.0))
        lignes.append(torch.where(r > 0, y, 0.0))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 2)
CUDA = lecture_cuda(NOM, 1, 2)
