"""Balance of Power de Livshin (modules/rules/balance_of_power.py) : moyenne sur n barres de (cloture - ouverture) /
amplitude ; une barre sans amplitude compte pour 0. Vote le signe, 0 a l'equilibre. Intensite : |BOP|.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_balance_of_power"
GENES = (ECHELLE, Gene("n", "entier", 1, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    etendue = b["haut"] - b["bas"]
    rapport = torch.where(etendue > 0, ind.corps(b) / etendue, 0.0)
    return torch.stack([ind.somme(rapport, n) / n for n in range(1, 101)])


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 1)
CUDA = lecture_cuda(NOM, 1, 1)
