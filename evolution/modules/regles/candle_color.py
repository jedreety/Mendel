"""Couleur d'une bougie close (modules/rules/candle_color.py) : verte +1, rouge -1, sans corps 0. Intensite : part
du corps dans l'amplitude de la bougie. decalage : 1 pour la derniere bougie close, 2 pour celle d'avant.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_candle_color"
GENES = (ECHELLE, Gene("decalage", "entier", 1, 5))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    c = ind.corps(b)
    y = ind.vote(ind.signe(c), c.abs() / (b["haut"] - b["bas"]), c != 0)
    return torch.stack([ind.avant(y, d - 1) for d in range(1, 6)])


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("decalage", 1)
CUDA = lecture_cuda(NOM, 1, 1)
