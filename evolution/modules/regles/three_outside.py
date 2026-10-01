"""Trois a l'exterieur (modules/rules/three_outside.py) : un avalement, confirme par une troisieme bougie de meme
couleur que la deuxieme qui clot au-dela d'elle. Haussier +1, baissier -1, sinon s'abstient. Intensite : corps de la
troisieme sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_three_outside"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    a, m = ind.decaler(b, 2), ind.decaler(b, 1)
    ca, cm, c = ind.corps(a), ind.corps(m), ind.corps(b)
    hausse = ((ca < 0) & (cm > 0) & (m["ouverture"] <= a["cloture"]) & (m["cloture"] > a["ouverture"]) & (c > 0)
              & (b["cloture"] > m["cloture"]))
    baisse = ((ca > 0) & (cm < 0) & (m["ouverture"] >= a["cloture"]) & (m["cloture"] < a["ouverture"]) & (c < 0)
              & (b["cloture"] < m["cloture"]))
    return ind.vote(torch.where(hausse, 1.0, -1.0), ind.plafond(c.abs() / r), hausse | baisse)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
