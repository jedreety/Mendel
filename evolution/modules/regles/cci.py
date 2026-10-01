"""Commodity Channel Index de Lambert sur n barres (modules/rules/cci.py), lu en suivi de tendance : au-dessus de
+100 +1, sous -100 -1, entre les deux s'abstient ; sans ecart moyen, s'abstient. Intensite : depassement au-dela de
100, sur 100, plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, lecture, lecture_cuda

NOM = "regle_cci"
GENES = (ECHELLE, Gene("n", "entier", 5, 100))
ORDONNES = ()
CONSTANTE = 0.015


def calcul(b: dict) -> torch.Tensor:
    typique = (b["haut"] + b["bas"] + b["cloture"]) / 3
    lignes = []
    for n in range(5, 101):
        fenetre = ind.fenetres(typique, n)
        moyenne = fenetre.mean(1)
        ecart = (fenetre - moyenne[:, None]).abs().mean(1)
        cci = (typique - moyenne) / (CONSTANTE * ecart)
        y = torch.where(cci > 100, ind.plafond((cci - 100) / 100),
                        torch.where(cci < -100, -ind.plafond((-cci - 100) / 100), 0.0))
        lignes.append(torch.where(ecart > 0, y, 0.0))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul)


signal = lecture("n", 5)
CUDA = lecture_cuda(NOM, 1, 5)
