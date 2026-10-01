"""Cassure du range d'ouverture (modules/rules/opening_range_breakout.py) : cloture au-dessus du plus haut des
`longueur` premieres barres d'une seance a heure fixe UTC +1, sous leur plus bas -1, entre les deux s'abstient.

Pendant le range, et pour un range sans amplitude, s'abstient. Intensite : depassement rapporte a l'amplitude du
range, plafonne a 1. Toujours a l'echelle horaire ; la seance suit la convention de session_open.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import lecture_horaire_cuda
from evolution.modules.regles.session_open import FENETRE, depuis_ouverture

NOM = "regle_opening_range_breakout"
GENES = (Gene("heure", "entier", 0, 23, circulaire=True), Gene("longueur", "entier", 1, 8))
ORDONNES = ()
LONGUEUR_MAX = int(GENES[1].haut)


def calcul(b: dict, heures_cloture: torch.Tensor) -> torch.Tensor:
    t = torch.arange(b["cloture"].shape[0])
    c = b["cloture"]
    lignes = []
    for heure in range(24):
        ecoulees = depuis_ouverture(heures_cloture, heure)
        for longueur in range(1, LONGUEUR_MAX + 1):
            fin = (t - ecoulees + longueur - 1).clamp(min=0, max=t.shape[0] - 1)
            haut = ind.plus_haut(b["haut"], longueur)[fin]
            bas = ind.plus_bas(b["bas"], longueur)[fin]
            etendue = haut - bas
            apres = (ecoulees >= longueur) & (etendue > 0) & (t >= FENETRE - 1)
            y = torch.where(c > haut, ind.plafond((c - haut) / etendue),
                            torch.where(c < bas, -ind.plafond((bas - c) / etendue), 0.0))
            lignes.append(torch.where(apres, y, 0.0))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(lambda b: calcul(b, marche.heures_cloture), horaire=True)


def signal(marche, table, i, g, bot):
    return marche.lire8_horaire(table, g["heure"] * LONGUEUR_MAX + g["longueur"] - 1, i)


CUDA = lecture_horaire_cuda(NOM, f"(int)g[0] * {LONGUEUR_MAX} + (int)g[1] - 1")
