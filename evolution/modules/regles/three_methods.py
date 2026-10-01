"""Trois methodes montantes ou descendantes (modules/rules/three_methods.py) : longue bougie (corps d'au moins R/2),
trois petits corps (sous R/2) contenus dans son amplitude, puis longue bougie de meme couleur qui clot au-dela de la
premiere. Vote la couleur, sinon s'abstient. Intensite : corps de la derniere sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_three_methods"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    premiere = ind.decaler(b, 4)
    cp, c = ind.corps(premiere), ind.corps(b)
    motif = (cp.abs() >= r / 2) & (c.abs() >= r / 2)
    for k in (1, 2, 3):
        milieu = ind.decaler(b, k)
        motif &= ((milieu["haut"] <= premiere["haut"]) & (milieu["bas"] >= premiere["bas"])
                  & (ind.corps(milieu).abs() < r / 2))
    hausse = motif & (cp > 0) & (c > 0) & (b["cloture"] > premiere["cloture"])
    baisse = motif & (cp < 0) & (c < 0) & (b["cloture"] < premiere["cloture"])
    return ind.vote(torch.where(hausse, 1.0, -1.0), ind.plafond(c.abs() / r), hausse | baisse)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
