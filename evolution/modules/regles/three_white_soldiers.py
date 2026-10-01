"""Trois soldats blancs (modules/rules/three_white_soldiers.py) : trois bougies vertes a clotures croissantes,
chacune ouvrant dans le corps de la precedente, meches hautes d'au plus R/10. Vote +1. Intensite : progression
totale sur 3R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_three_white_soldiers"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    a, m = ind.decaler(b, 2), ind.decaler(b, 1)
    motif = torch.ones_like(r, dtype=torch.bool)
    for x in (a, m, b):
        motif &= (ind.corps(x) > 0) & (ind.meche_haute(x) <= r / 10)
    motif &= (a["ouverture"] <= m["ouverture"]) & (m["ouverture"] <= a["cloture"])
    motif &= (m["ouverture"] <= b["ouverture"]) & (b["ouverture"] <= m["cloture"])
    motif &= (a["cloture"] < m["cloture"]) & (m["cloture"] < b["cloture"])
    return ind.vote(1.0, ind.plafond((b["cloture"] - a["ouverture"]) / (3 * r)), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
