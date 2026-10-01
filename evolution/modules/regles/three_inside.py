"""Trois a l'interieur (modules/rules/three_inside.py) : un harami (longue bougie, puis petit corps oppose contenu
dans le sien), confirme par une troisieme bougie de la couleur du petit corps qui clot au-dela de l'ouverture de la
premiere. Haussier +1, baissier -1, sinon s'abstient. Intensite : corps de la troisieme sur R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda
from evolution.modules.regles.harami import contenu

NOM = "regle_three_inside"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    a, m = ind.decaler(b, 2), ind.decaler(b, 1)
    ca, cm, c = ind.corps(a), ind.corps(m), ind.corps(b)
    harami = contenu(a, m) & (ca.abs() >= r / 2) & (cm.abs() < r / 2)
    hausse = harami & (ca < 0) & (cm > 0) & (c > 0) & (b["cloture"] > a["ouverture"])
    baisse = harami & (ca > 0) & (cm < 0) & (c < 0) & (b["cloture"] < a["ouverture"])
    return ind.vote(torch.where(hausse, 1.0, -1.0), ind.plafond(c.abs() / r), hausse | baisse)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
