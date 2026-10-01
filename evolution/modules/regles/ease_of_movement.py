"""Ease of Movement d'Arms sur n barres, sans moyenne mobile (modules/rules/ease_of_movement.py) : somme des
deplacements du milieu de barre, multiplies par l'amplitude et divises par le volume ; une barre sans volume ne compte
pas. Vote le signe, 0 a l'equilibre, s'abstient sans volume. Intensite : somme signee rapportee a la somme des
valeurs absolues.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_ease_of_movement"
GENES = (ECHELLE, Gene("n", "entier", 1, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    milieu = b["haut"] + b["bas"]
    avec_volume = b["volume"] > 0
    valeurs = torch.where(avec_volume, (milieu - ind.avant(milieu, 1)) / 2 * (b["haut"] - b["bas"]) / b["volume"], 0.0)
    valeurs = torch.nan_to_num(valeurs)
    lignes = []
    for n in range(1, 101):
        y = ind.vote(1.0, ind.somme(valeurs, n) / ind.somme(valeurs.abs(), n), ind.compte(valeurs != 0, n) > 0)
        lignes.append(ind.depuis(torch.where(ind.compte(avec_volume, n) > 0, y, ind.NAN), n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 1)
CUDA = lecture_cuda(NOM, 1, 1)
