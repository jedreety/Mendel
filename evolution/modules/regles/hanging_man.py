"""Pendu (modules/rules/hanging_man.py) : forme du marteau, mais apres une hausse. Vote -1.

Hausse : la bougie precedente clot au-dessus de la cloture de 5 barres plus tot. Intensite : meche basse sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda
from evolution.modules.regles.hammer import forme

NOM = "regle_hanging_man"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    hausse = ind.avant(b["cloture"], 1) > ind.avant(b["cloture"], 6)
    return ind.vote(-1.0, ind.plafond(ind.meche_basse(b) / r), hausse & forme(b, r))


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
