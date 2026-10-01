"""Force Index d'Elder sur n barres, sans moyenne exponentielle (modules/rules/force_index.py) : somme des variations
de cloture multipliees par le volume. Vote le signe, 0 a l'equilibre, s'abstient sans volume. Intensite : somme
signee rapportee a la somme des valeurs absolues.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_force_index"
GENES = (ECHELLE, Gene("n", "entier", 1, 100))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    forces = torch.nan_to_num((b["cloture"] - ind.avant(b["cloture"], 1)) * b["volume"])
    lignes = []
    for n in range(1, 101):
        y = ind.vote(1.0, ind.somme(forces, n) / ind.somme(forces.abs(), n), ind.compte(forces != 0, n) > 0)
        lignes.append(ind.depuis(torch.where(ind.compte(b["volume"] > 0, n) > 0, y, ind.NAN), n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 1)
CUDA = lecture_cuda(NOM, 1, 1)
