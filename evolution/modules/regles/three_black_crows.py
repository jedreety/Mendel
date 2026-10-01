"""Trois corbeaux noirs (modules/rules/three_black_crows.py) : trois bougies rouges a clotures decroissantes,
chacune ouvrant dans le corps de la precedente, meches basses d'au plus R/10. Vote -1. Intensite : baisse totale
sur 3R.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_three_black_crows"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    r = ind.volatilite(b, ind.REF)
    a, m = ind.decaler(b, 2), ind.decaler(b, 1)
    motif = torch.ones_like(r, dtype=torch.bool)
    for x in (a, m, b):
        motif &= (ind.corps(x) < 0) & (ind.meche_basse(x) <= r / 10)
    motif &= (a["cloture"] <= m["ouverture"]) & (m["ouverture"] <= a["ouverture"])
    motif &= (m["cloture"] <= b["ouverture"]) & (b["ouverture"] <= m["ouverture"])
    motif &= (a["cloture"] > m["cloture"]) & (m["cloture"] > b["cloture"])
    return ind.vote(-1.0, ind.plafond((a["ouverture"] - b["cloture"]) / (3 * r)), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
