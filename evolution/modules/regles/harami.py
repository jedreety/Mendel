"""Harami (modules/rules/harami.py) : longue bougie (corps d'au moins R/2), puis petit corps (sous R/2) de couleur
opposee contenu dans le sien. Vote le sens de la seconde, sinon s'abstient. Intensite : corps de la premiere sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_harami"
GENES = (ECHELLE,)
ORDONNES = ()


def contenu(a: dict, b: dict) -> torch.Tensor:
    """Le corps de b tient dans celui de a."""
    return ((torch.minimum(b["ouverture"], b["cloture"]) >= torch.minimum(a["ouverture"], a["cloture"]))
            & (torch.maximum(b["ouverture"], b["cloture"]) <= torch.maximum(a["ouverture"], a["cloture"])))


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    p = ind.decaler(b, 1)
    c, pc = ind.corps(b), ind.corps(p)
    motif = contenu(p, b) & (pc.abs() >= r / 2) & (c.abs() < r / 2)
    hausse, baisse = motif & (pc < 0) & (c > 0), motif & (pc > 0) & (c < 0)
    return ind.vote(torch.where(hausse, 1.0, -1.0), ind.plafond(pc.abs() / r), hausse | baisse)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
