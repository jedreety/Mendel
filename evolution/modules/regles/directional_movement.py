"""Mouvement directionnel de Wilder sur n barres, sans lissage (modules/rules/directional_movement.py) : +DM contre
-DM. Vote le cote dominant, 0 a egalite, s'abstient sans aucun mouvement. Intensite : |+DM - -DM| / (+DM + -DM).
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_directional_movement"
GENES = (ECHELLE, Gene("n", "entier", 1, 100))
ORDONNES = ()


def mouvements(b: dict) -> tuple[torch.Tensor, torch.Tensor]:
    """+DM et -DM de chaque barre, 0 pour la premiere."""
    hausse = b["haut"] - ind.avant(b["haut"], 1)
    baisse = ind.avant(b["bas"], 1) - b["bas"]
    plus = torch.where((hausse > baisse) & (hausse > 0), hausse, 0.0)
    moins = torch.where((baisse > hausse) & (baisse > 0), baisse, 0.0)
    return plus, moins


def calcul(b: dict) -> torch.Tensor:
    plus, moins = mouvements(b)
    lignes = []
    for n in range(1, 101):
        p, m = ind.somme(plus, n), ind.somme(moins, n)
        mouvement = ind.compte((plus > 0) | (moins > 0), n) > 0
        y = ind.vote(ind.signe(p - m), (p - m).abs() / (p + m), mouvement)
        lignes.append(ind.depuis(y, n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 1)
CUDA = lecture_cuda(NOM, 1, 1)
