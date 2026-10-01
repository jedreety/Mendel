"""Cassure apres contraction, d'apres Crabel (modules/rules/narrow_range.py) : l'avant-derniere barre a l'amplitude
la plus faible des `longueur` barres qui precedent la derniere. La derniere clot au-dessus de son plus haut +1, sous
son plus bas -1, sinon s'abstient. Intensite : depassement en unites de volatilite, plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_narrow_range"
GENES = (ECHELLE, Gene("longueur", "entier", 2, 30))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    c = b["cloture"]
    p = ind.decaler(b, 1)
    etendue = b["haut"] - b["bas"]
    lignes = []
    for n in range(2, 31):
        etroite = ind.avant(etendue, 1) <= ind.avant(ind.plus_bas(etendue, n), 1)
        r = ind.volatilite(b, n)
        y = torch.where(c > p["haut"], ind.plafond((c - p["haut"]) / r),
                        torch.where(c < p["bas"], -ind.plafond((p["bas"] - c) / r), 0.0))
        lignes.append(ind.depuis(torch.where(etroite & (r > 0), y, 0.0), n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("longueur", 2)
CUDA = lecture_cuda(NOM, 1, 2)
