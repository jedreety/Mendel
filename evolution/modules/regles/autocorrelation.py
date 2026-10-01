"""Autocorrelation d'ordre 1 des variations de cloture sur n variations (modules/rules/autocorrelation.py).
Positive, le marche prolonge ses mouvements : vote le sens de la derniere variation. Negative, il les corrige :
vote le sens oppose. Nulle, ou derniere variation nulle : 0. Variations toutes egales : s'abstient.
Intensite : |autocorrelation|.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_autocorrelation"
GENES = (ECHELLE, Gene("n", "entier", 3, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    variation = torch.nan_to_num(b["cloture"] - ind.avant(b["cloture"], 1))
    produits = variation * ind.avant(variation, 1)
    lignes = []
    for n in range(3, 101):
        somme = ind.somme(variation, n)
        moyenne = somme / n
        variance = ind.somme(variation * variation, n) - n * moyenne * moyenne
        premiere = ind.avant(variation, n - 1)
        # sum (d_k - m)(d_k+1 - m) sur les paires de la fenetre, d'apres les sommes glissantes.
        covariance = (ind.somme(torch.nan_to_num(produits), n - 1) - moyenne * (2 * somme - premiere - variation)
                      + (n - 1) * moyenne * moyenne)
        rho = covariance / variance
        differentes = ind.plus_haut(variation, n) > ind.plus_bas(variation, n)
        y = ind.vote(ind.signe(variation), rho, differentes)
        lignes.append(ind.depuis(y, n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 3)
CUDA = lecture_cuda(NOM, 1, 3)
