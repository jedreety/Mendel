"""Marteau (modules/rules/hammer.py) : apres une baisse, petit corps et longue meche basse. Vote +1.

Forme : corps sous R/2, meche basse d'au moins deux fois le corps et d'au moins R/2, meche haute d'au plus R/10.
Baisse : la bougie precedente clot sous la cloture de 5 barres plus tot. Intensite : meche basse sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_hammer"
GENES = (ECHELLE,)
ORDONNES = ()


def forme(b: dict, r: torch.Tensor) -> torch.Tensor:
    """La forme du marteau et du pendu."""
    c, basse = ind.corps(b).abs(), ind.meche_basse(b)
    return (c < r / 2) & (basse >= 2 * c) & (basse >= r / 2) & (ind.meche_haute(b) <= r / 10)


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    baisse = ind.avant(b["cloture"], 1) < ind.avant(b["cloture"], 6)
    return ind.vote(1.0, ind.plafond(ind.meche_basse(b) / r), baisse & forme(b, r))


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
