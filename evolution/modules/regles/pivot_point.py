"""Point pivot classique de la veille UTC (modules/rules/pivot_point.py), (plus haut + plus bas + cloture) / 3 :
cloture au-dessus +1, en dessous -1, dessus 0. Veille sans amplitude : s'abstient. Intensite : distance au pivot
rapportee a sa distance a la premiere resistance (2P - plus bas) ou au premier support (2P - plus haut), plafonnee
a 1. Toujours a l'echelle horaire ; la veille est celle de previous_day_range.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import lecture_horaire, lecture_horaire_cuda
from evolution.modules.regles.previous_day_range import veille

NOM = "regle_pivot_point"
GENES = ()
ORDONNES = ()


def calcul(b: dict, heures_cloture: torch.Tensor) -> torch.Tensor:
    haut, bas, derniere = veille(b, heures_cloture)
    pivot = (haut + bas + derniere) / 3
    c = b["cloture"]
    y = torch.where(c > pivot, ind.plafond((c - pivot) / (pivot - bas)),
                    torch.where(c < pivot, -ind.plafond((pivot - c) / (haut - pivot)), 0.0))
    return torch.where(haut - bas > 0, y, 0.0)


def preparer(marche):
    return marche.table8(lambda b: calcul(b, marche.heures_cloture), horaire=True)


signal = lecture_horaire()
CUDA = lecture_horaire_cuda(NOM, "0")
