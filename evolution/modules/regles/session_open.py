"""Bougie d'ouverture d'une seance a heure fixe UTC (modules/rules/session_open.py) : verte +1, rouge -1, sans corps
0. Intensite : part du corps dans l'amplitude de la bougie. Toujours a l'echelle horaire.

La bougie d'ouverture est la premiere qui clot apres l'heure de la seance ; son vote vaut jusqu'a l'ouverture
suivante. Sur des barres horaires, les minutes de la regle ne changent rien : seule l'heure est un gene.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import lecture_horaire, lecture_horaire_cuda

NOM = "regle_session_open"
GENES = (Gene("heure", "entier", 0, 23, circulaire=True),)
ORDONNES = ()
FENETRE = 25  # barres parcourues par la regle pour retrouver l'ouverture : toute une journee


def depuis_ouverture(heures_cloture: torch.Tensor, heure: int) -> torch.Tensor:
    """Barres ecoulees depuis la bougie d'ouverture de la seance, de 0 a 23 : l'ouverture est au plus tard
    l'heure qui precede strictement la cloture.
    """
    return (heures_cloture % 24 - heure - 1) % 24


def calcul(b: dict, heures_cloture: torch.Tensor) -> torch.Tensor:
    t = torch.arange(b["cloture"].shape[0])
    c, etendue = ind.corps(b), b["haut"] - b["bas"]
    lignes = []
    for heure in range(24):
        ouverture = t - depuis_ouverture(heures_cloture, heure)
        k = ouverture.clamp(min=0)
        y = ind.vote(ind.signe(c[k]), c[k].abs() / etendue[k], c[k] != 0)
        lignes.append(torch.where(t >= FENETRE - 1, y, ind.NAN))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(lambda b: calcul(b, marche.heures_cloture), horaire=True)


signal = lecture_horaire("heure")
CUDA = lecture_horaire_cuda(NOM, "(int)g[0]")
