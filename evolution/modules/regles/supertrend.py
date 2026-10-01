"""Supertrend (modules/rules/supertrend.py) : bandes a `multiplicateur` unites de volatilite (periode barres)
autour du milieu de barre, qui ne reculent pas tant que la cloture precedente les respecte. La tendance devient
baissiere quand la cloture passe sous la bande basse precedente, haussiere au-dessus de la bande haute
precedente. Haussiere +1, baissiere -1. Intensite : distance entre la cloture et la bande active, en unites de
volatilite, plafonnee a 1.

Comme dans le moteur, la serie porte sur une fenetre fixe de 3 x periode + 1 barres et part dans le sens de la
cloture par rapport au milieu de sa premiere barre. Le multiplicateur prend une des valeurs usuelles.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_supertrend"
MULTIPLICATEURS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
GENES = (ECHELLE, Gene("periode", "entier", 5, 30), Gene("multiplicateur", "categoriel", categories=MULTIPLICATEURS))
ORDONNES = ()
PERIODE_MIN, PERIODE_MAX = int(GENES[1].bas), int(GENES[1].haut)


def tendance(b: dict, periode: int) -> torch.Tensor:
    """(multiplicateurs, barres) : le signal de chaque multiplicateur, pour une periode."""
    multiplicateur = torch.tensor(MULTIPLICATEURS, dtype=torch.float64)[:, None]
    r = ind.volatilite(b, periode)
    fenetre = 3 * periode + 1
    haute = basse = montante = None
    for i in range(periode, fenetre):
        d = fenetre - 1 - i  # barres entre celle-ci et la derniere
        barre, veille = ind.decaler(b, d), ind.avant(b["cloture"], d + 1)
        milieu = (barre["haut"] + barre["bas"]) / 2
        vol = ind.avant(r, d)
        haute_brute, basse_brute = milieu + multiplicateur * vol, milieu - multiplicateur * vol
        if montante is None:
            haute, basse = haute_brute, basse_brute
            montante = (barre["cloture"] >= milieu).expand_as(haute).clone()
            continue
        montante = torch.where(montante & (barre["cloture"] < basse), False,
                               torch.where(~montante & (barre["cloture"] > haute), True, montante))
        haute = torch.where((haute_brute < haute) | (veille > haute), haute_brute, haute)
        basse = torch.where((basse_brute > basse) | (veille < basse), basse_brute, basse)
    bande = torch.where(montante, basse, haute)
    y = ind.vote(torch.where(montante, 1.0, -1.0), ind.plafond((b["cloture"] - bande).abs() / r), r > 0)
    y[:, :fenetre - 1] = ind.NAN
    return y


def calcul(b: dict) -> torch.Tensor:
    return torch.cat([tendance(b, p) for p in range(PERIODE_MIN, PERIODE_MAX + 1)])


def preparer(marche):
    return marche.table8(calcul)


def signal(marche, table, i, g, bot):
    ligne = (g["periode"] - PERIODE_MIN) * len(MULTIPLICATEURS) + g["multiplicateur"]
    return marche.lire8(table, ligne, marche.indice(g["echelle"], i))


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = rf"""
__device__ float signal_regle_supertrend(const Marche& m, const float* g, int i, int periode_atr) {{
    const int ligne = ((int)g[1] - {PERIODE_MIN}) * {len(MULTIPLICATEURS)} + (int)g[2];
    return lire8(m, TABLE_REGLE_SUPERTREND, ligne, indice(m, (int)g[0], i));
}}
"""
