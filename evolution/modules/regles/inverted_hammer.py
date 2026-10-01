"""Marteau inverse (modules/rules/inverted_hammer.py) : apres une baisse, petit corps et longue meche haute.
Vote +1.

Forme : corps sous R/2, meche haute d'au moins deux fois le corps et d'au moins R/2, meche basse d'au plus R/10.
Baisse : la bougie precedente clot sous la cloture de 5 barres plus tot. Intensite : meche haute sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_inverted_hammer"
GENES = (ECHELLE,)
ORDONNES = ()


def forme(b: dict, r: torch.Tensor) -> torch.Tensor:
    """La forme du marteau inverse et de l'etoile filante."""
    c, haute = ind.corps(b).abs(), ind.meche_haute(b)
    return (c < r / 2) & (haute >= 2 * c) & (haute >= r / 2) & (ind.meche_basse(b) <= r / 10)


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    baisse = ind.avant(b["cloture"], 1) < ind.avant(b["cloture"], 6)
    return ind.vote(1.0, ind.plafond(ind.meche_haute(b) / r), baisse & forme(b, r))


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
