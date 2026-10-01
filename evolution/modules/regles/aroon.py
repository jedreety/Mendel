"""Aroon sur n barres (modules/rules/aroon.py) : Aroon haut moins Aroon bas, sur les n + 1 dernieres barres. Vote
le signe, 0 a egalite ; a egalite de plus haut ou de plus bas, le plus recent compte. Intensite : ecart entre Aroon
haut et Aroon bas, sur 100.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_aroon"
GENES = (ECHELLE, Gene("n", "entier", 2, 100))
ORDONNES = ()


def depuis_extreme(serie: torch.Tensor, n: int) -> torch.Tensor:
    """Barres ecoulees depuis le maximum des n + 1 dernieres valeurs, le plus recent a egalite."""
    recentes_d_abord = ind.fenetres(torch.nan_to_num(serie, nan=-torch.inf), n + 1).flip(1)
    return recentes_d_abord.argmax(1).double()


def calcul(b: dict) -> torch.Tensor:
    lignes = []
    for n in range(2, 101):
        ecart = (depuis_extreme(-b["bas"], n) - depuis_extreme(b["haut"], n)) / n
        lignes.append(ind.depuis(ecart, n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 2)
CUDA = lecture_cuda(NOM, 1, 2)
