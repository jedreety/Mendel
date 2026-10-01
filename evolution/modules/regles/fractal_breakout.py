"""Cassure de fractale de Bill Williams (modules/rules/fractal_breakout.py) : cloture au-dessus de la derniere
fractale haute confirmee +1, sous la derniere fractale basse confirmee -1, sinon s'abstient.

Fractale haute : plus haut strictement superieur a ceux des deux barres de chaque cote ; basse, en miroir. Elle
n'est confirmee qu'une fois closes les deux barres qui la suivent. Recherche sur les `fenetre` dernieres barres,
de la plus recente a la plus ancienne : la premiere fractale rencontree est jugee d'abord. Intensite : depassement
en unites de volatilite (periode fenetre), plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_fractal_breakout"
GENES = (ECHELLE, Gene("fenetre", "entier", 5, 100))
ORDONNES = ()


def derniere(fractale: torch.Tensor) -> torch.Tensor:
    """Indice de la derniere fractale confirmee a chaque barre (deux barres apres elle), -1 s'il n'y en a pas."""
    indices = torch.where(fractale, torch.arange(fractale.shape[0]), -1).cummax(0).values
    return torch.cat((torch.full((2,), -1), indices[:-2]))


def calcul(b: dict) -> torch.Tensor:
    t = torch.arange(b["cloture"].shape[0])
    c, haut, bas = b["cloture"], b["haut"], b["bas"]
    voisins = (1, 2)
    haute = torch.ones_like(c, dtype=torch.bool)
    basse = torch.ones_like(c, dtype=torch.bool)
    for d in voisins:
        haute &= (haut > ind.avant(haut, d)) & (haut > torch.cat((haut[d:], torch.full((d,), torch.inf))))
        basse &= (bas < ind.avant(bas, d)) & (bas < torch.cat((bas[d:], torch.full((d,), -torch.inf))))
    kh, kb = derniere(haute), derniere(basse)
    niveau_haut, niveau_bas = haut[kh.clamp(min=0)], bas[kb.clamp(min=0)]
    lignes = []
    for fenetre in range(5, 101):
        r = ind.volatilite(b, fenetre)
        dh, db = kh >= t - fenetre + 3, kb >= t - fenetre + 3  # dans la fenetre de recherche
        hausse = dh & (c > niveau_haut)
        baisse = db & (c < niveau_bas)
        haute_d_abord = kh >= kb
        y_hausse, y_baisse = ind.plafond((c - niveau_haut) / r), -ind.plafond((niveau_bas - c) / r)
        y = torch.where(haute_d_abord, torch.where(hausse, y_hausse, torch.where(baisse, y_baisse, 0.0)),
                        torch.where(baisse, y_baisse, torch.where(hausse, y_hausse, 0.0)))
        lignes.append(ind.depuis(y, fenetre))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("fenetre", 5)
CUDA = lecture_cuda(NOM, 1, 5)
