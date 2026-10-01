"""Structure de marche (modules/rules/market_structure.py) : `longueur` barres de suite a plus hauts et plus bas
croissants +1, decroissants -1, sinon s'abstient. Intensite : deplacement des clotures en unites de volatilite
ramenees a l'horizon par racine de la longueur, plafonne a 1.
"""
import math

import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_market_structure"
GENES = (ECHELLE, Gene("longueur", "entier", 1, 20))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    p = ind.decaler(b, 1)
    montee = (b["haut"] > p["haut"]) & (b["bas"] > p["bas"])
    descente = (b["haut"] < p["haut"]) & (b["bas"] < p["bas"])
    lignes = []
    for n in range(1, 21):
        hausse, baisse = ind.compte(montee, n) == n, ind.compte(descente, n) == n
        mouvement = (b["cloture"] - ind.avant(b["cloture"], n)).abs()
        echelle = ind.volatilite(b, n) * math.sqrt(n)
        y = ind.vote(torch.where(hausse, 1.0, -1.0), ind.plafond(mouvement / echelle), (hausse | baisse) & (echelle > 0))
        lignes.append(ind.depuis(y, n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("longueur", 1)
CUDA = lecture_cuda(NOM, 1, 1)
