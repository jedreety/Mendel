"""Pente de l'OBV sur n barres (modules/rules/on_balance_volume.py) : le volume compte en plus quand la cloture
monte, en moins quand elle baisse. Vote le signe, 0 a l'equilibre, s'abstient sans volume. Intensite : volume signe
rapporte au volume total.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_on_balance_volume"
GENES = (ECHELLE, Gene("n", "entier", 1, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    v = b["volume"]
    signe_variation = torch.nan_to_num(ind.signe(b["cloture"] - ind.avant(b["cloture"], 1)))
    flux = signe_variation * v
    lignes = []
    for n in range(1, 101):
        y = ind.vote(1.0, ind.somme(flux, n) / ind.somme(v, n), ind.compte(v > 0, n) > 0)
        lignes.append(ind.depuis(y, n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 1)
CUDA = lecture_cuda(NOM, 1, 1)
