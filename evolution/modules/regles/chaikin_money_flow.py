"""Chaikin Money Flow sur n barres (modules/rules/chaikin_money_flow.py) : position de chaque cloture dans son
amplitude, ponderee par le volume. Vote le signe, 0 a l'equilibre, s'abstient sans volume. Intensite : |CMF|.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_chaikin_money_flow"
GENES = (ECHELLE, Gene("n", "entier", 2, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    etendue = b["haut"] - b["bas"]
    position = ((b["cloture"] - b["bas"]) - (b["haut"] - b["cloture"])) / etendue
    flux = torch.where(etendue > 0, position * b["volume"], 0.0)
    lignes = []
    for n in range(2, 101):
        y = ind.vote(1.0, ind.somme(flux, n) / ind.somme(b["volume"], n), ind.compte(b["volume"] > 0, n) > 0)
        lignes.append(y)
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 2)
CUDA = lecture_cuda(NOM, 1, 2)
