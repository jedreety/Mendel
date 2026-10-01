"""Couleur de la derniere bougie Heikin-Ashi (modules/rules/heikin_ashi.py) : verte +1, rouge -1, sans corps 0.

Cloture HA : moyenne de l'ouverture, du plus haut, du plus bas et de la cloture. Ouverture HA : milieu du corps HA
precedent. La serie part d'une fenetre fixe de 10 barres, amorcee au milieu du corps de la premiere, comme dans le
moteur. Intensite : part du corps HA dans l'amplitude HA.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_heikin_ashi"
GENES = (ECHELLE,)
ORDONNES = ()
FENETRE = 10


def calcul(b: dict) -> torch.Tensor:
    premiere = ind.decaler(b, FENETRE - 1)
    ha_ouverture = (premiere["ouverture"] + premiere["cloture"]) / 2
    ha_cloture = (premiere["ouverture"] + premiere["haut"] + premiere["bas"] + premiere["cloture"]) / 4
    for k in range(FENETRE - 2, -1, -1):
        barre = ind.decaler(b, k)
        ha_ouverture = (ha_ouverture + ha_cloture) / 2
        ha_cloture = (barre["ouverture"] + barre["haut"] + barre["bas"] + barre["cloture"]) / 4
    corps = ha_cloture - ha_ouverture
    etendue = torch.maximum(b["haut"], ha_ouverture) - torch.minimum(b["bas"], ha_ouverture)
    return ind.vote(ind.signe(corps), corps.abs() / etendue, corps != 0)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture()
CUDA = lecture_cuda(NOM)
