"""Mouvement depuis l'ouverture d'une seance a heure fixe UTC (modules/rules/session_move.py) : le sens du
deplacement depuis l'ouverture de la bougie d'ouverture, momentum intraday. Intensite : deplacement rapporte a
l'amplitude de la seance. Toujours a l'echelle horaire ; la seance suit la convention de session_open.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import lecture_horaire, lecture_horaire_cuda
from evolution.modules.regles.session_open import FENETRE, depuis_ouverture

NOM = "regle_session_move"
GENES = (Gene("heure", "entier", 0, 23, circulaire=True),)
ORDONNES = ()


def calcul(b: dict, heures_cloture: torch.Tensor) -> torch.Tensor:
    t = torch.arange(b["cloture"].shape[0])
    lignes = []
    for heure in range(24):
        ecoulees = depuis_ouverture(heures_cloture, heure)
        mouvement = b["cloture"] - b["ouverture"][(t - ecoulees).clamp(min=0)]
        haut, bas = b["haut"].clone(), b["bas"].clone()
        for d in range(1, 24):
            dans = ecoulees >= d
            haut = torch.where(dans, torch.maximum(haut, ind.avant(b["haut"], d)), haut)
            bas = torch.where(dans, torch.minimum(bas, ind.avant(b["bas"], d)), bas)
        y = ind.vote(ind.signe(mouvement), mouvement.abs() / (haut - bas), mouvement != 0)
        lignes.append(torch.where(t >= FENETRE - 1, y, ind.NAN))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(lambda b: calcul(b, marche.heures_cloture), horaire=True)


signal = lecture_horaire("heure")
CUDA = lecture_horaire_cuda(NOM, "(int)g[0]")
