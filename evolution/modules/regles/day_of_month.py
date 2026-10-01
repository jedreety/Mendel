"""Jour du mois UTC (modules/rules/day_of_month.py) : 1 quand la prochaine barre commence le jour choisi, compte
depuis le debut du mois (1 a 28) ou depuis la fin (-1 : le dernier jour), 0 sinon. Le sens du vote de la regle
est laisse au reseau, qui en apprend le poids.
"""
import calendar
from datetime import UTC, datetime

import torch

from evolution.gene import Gene
from evolution.modules.regles.commun import lecture_horaire, lecture_horaire_cuda

NOM = "regle_day_of_month"
JOURS = (*range(1, 29), *range(-7, 0))
GENES = (Gene("jour", "categoriel", categories=JOURS),)
ORDONNES = ()


def calcul(heures_cloture: torch.Tensor) -> torch.Tensor:
    quantiemes, depuis_fin = [], []
    for heures in heures_cloture.tolist():
        instant = datetime.fromtimestamp(heures * 3600, UTC)
        quantiemes.append(instant.day)
        depuis_fin.append(instant.day - calendar.monthrange(instant.year, instant.month)[1] - 1)
    quantieme, fin = torch.tensor(quantiemes), torch.tensor(depuis_fin)
    return torch.stack([((quantieme == jour) | (fin == jour)).double() for jour in JOURS])


def preparer(marche):
    return marche.table8(lambda b: calcul(marche.heures_cloture), horaire=True)


signal = lecture_horaire("jour")
CUDA = lecture_horaire_cuda(NOM, "(int)g[0]")
