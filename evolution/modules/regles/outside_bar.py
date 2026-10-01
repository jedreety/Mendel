"""Barre exterieure (modules/rules/outside_bar.py) : amplitude qui deborde la precedente des deux cotes. Vote le
cote ou elle clot, sinon s'abstient. Intensite : ecart entre la cloture et le milieu de la barre, rapporte a la
demi-amplitude.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_outside_bar"
GENES = (ECHELLE,)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    p = ind.decaler(b, 1)
    ecart = b["cloture"] - (b["haut"] + b["bas"]) / 2
    motif = (b["haut"] > p["haut"]) & (b["bas"] < p["bas"])
    return ind.vote(ind.signe(ecart), ecart.abs() / ((b["haut"] - b["bas"]) / 2), motif)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
