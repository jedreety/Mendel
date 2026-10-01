"""Cloture contre sa moyenne mobile exponentielle sur n barres (modules/rules/exponential_moving_average.py) :
au-dessus +1, en dessous -1. Intensite : ecart en unites de volatilite, plafonne a 1.

Comme dans le moteur, la moyenne porte sur une fenetre fixe de 3n barres, amorcee par la moyenne simple des n
premieres.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_exponential_moving_average"
GENES = (ECHELLE, Gene("n", "entier", 2, 100))
ORDONNES = ()


def ema_fenetre(cloture: torch.Tensor, n: int) -> torch.Tensor:
    """Moyenne exponentielle des 3n dernieres clotures, amorcee par la moyenne simple des n premieres."""
    alpha = 2 / (n + 1)
    ema = ind.avant(ind.somme(cloture, n) / n, 2 * n)
    for d in range(2 * n - 1, -1, -1):
        ema = ema + alpha * (ind.avant(cloture, d) - ema)
    return ema


def calcul(b: dict) -> torch.Tensor:
    lignes = []
    for n in range(2, 101):
        ecart = b["cloture"] - ema_fenetre(b["cloture"], n)
        r = ind.volatilite(b, n)
        lignes.append(ind.vote(ind.signe(ecart), ind.plafond(ecart.abs() / r), r > 0))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 2)
CUDA = lecture_cuda(NOM, 1, 2)
