"""Serie de bougies de meme couleur (modules/rules/candle_streak.py) : longueur bougies vertes +1, rouges -1,
sinon s'abstient. Intensite : deplacement net de la serie rapporte a son amplitude totale.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_candle_streak"
GENES = (ECHELLE, Gene("longueur", "entier", 1, 10))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    c = ind.corps(b)
    lignes = []
    for n in range(1, 11):
        vertes, rouges = ind.compte(c > 0, n) == n, ind.compte(c < 0, n) == n
        mouvement = (b["cloture"] - ind.avant(b["ouverture"], n - 1)).abs()
        etendue = ind.plus_haut(b["haut"], n) - ind.plus_bas(b["bas"], n)
        lignes.append(ind.vote(torch.where(vertes, 1.0, -1.0), mouvement / etendue, vertes | rouges))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("longueur", 1)
CUDA = lecture_cuda(NOM, 1, 1)
