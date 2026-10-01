"""Cassure de l'amplitude de la veille UTC (modules/rules/previous_day_range.py) : cloture au-dessus de son plus
haut +1, sous son plus bas -1, entre les deux s'abstient. Veille sans amplitude : s'abstient. Intensite :
depassement rapporte a l'amplitude de la veille, plafonne a 1. Toujours a l'echelle horaire.

La veille est le jour UTC qui precede celui ou commence la prochaine barre : ses 24 barres closent apres son
debut et au plus tard a minuit.
"""
import torch

from evolution import indicateurs as ind
from evolution.modules.regles.commun import lecture_horaire, lecture_horaire_cuda

NOM = "regle_previous_day_range"
GENES = ()
ORDONNES = ()


def veille(b: dict, heures_cloture: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Plus haut, plus bas et derniere cloture de la veille, a chaque barre ; NaN sans veille complete."""
    t = torch.arange(b["cloture"].shape[0])
    fin = t - heures_cloture % 24  # la barre qui clot a minuit
    k = fin.clamp(min=0)
    complete = fin >= 23
    haut = torch.where(complete, ind.plus_haut(b["haut"], 24)[k], ind.NAN)
    bas = torch.where(complete, ind.plus_bas(b["bas"], 24)[k], ind.NAN)
    return haut, bas, torch.where(complete, b["cloture"][k], ind.NAN)


def calcul(b: dict, heures_cloture: torch.Tensor) -> torch.Tensor:
    haut, bas, _ = veille(b, heures_cloture)
    c, etendue = b["cloture"], haut - bas
    y = torch.where(c > haut, ind.plafond((c - haut) / etendue),
                    torch.where(c < bas, -ind.plafond((bas - c) / etendue), 0.0))
    return torch.where(etendue > 0, y, 0.0)


def preparer(marche):
    return marche.table8(lambda b: calcul(b, marche.heures_cloture), horaire=True)


signal = lecture_horaire()
CUDA = lecture_horaire_cuda(NOM, "0")
