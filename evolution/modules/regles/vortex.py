"""Indicateur Vortex de Botes et Siepman sur n barres (modules/rules/vortex.py) : VI+ contre VI-. Vote le cote
dominant, 0 a egalite, s'abstient sans amplitude. VM+ : |plus haut - plus bas precedent|, VM- : |plus bas - plus
haut precedent|, rapportes a la somme des etendues vraies. Intensite : |VI+ - VI-|, plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_vortex"
GENES = (ECHELLE, Gene("n", "entier", 2, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    plus = torch.nan_to_num((b["haut"] - ind.avant(b["bas"], 1)).abs())
    moins = torch.nan_to_num((b["bas"] - ind.avant(b["haut"], 1)).abs())
    tr = ind.etendue_vraie(b)
    lignes = []
    for n in range(2, 101):
        p, m, etendues = ind.somme(plus, n), ind.somme(moins, n), ind.somme(tr, n)
        amplitude = ind.compte(tr > 0, n) > 0
        y = ind.vote(ind.signe(p - m), ind.plafond((p - m).abs() / etendues), amplitude)
        lignes.append(ind.depuis(y, n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 2)
CUDA = lecture_cuda(NOM, 1, 2)
