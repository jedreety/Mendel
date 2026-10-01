"""Moyennes mobiles exponentielles, courte contre longue (modules/rules/exponential_moving_average_cross.py) : +1 si
la courte est au-dessus, -1 si elle est en dessous. Intensite : ecart entre les deux moyennes en unites de
volatilite (periode longue), plafonne a 1.

Ecart avec le moteur : les moyennes sont celles du marche, sur tout l'historique, et non sur une fenetre de
3 x longue barres ; les deux se rejoignent des que l'amorce s'est effacee.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_exponential_moving_average_cross"
GENES = (ECHELLE, Gene("rapide", "entier", 2, 100), Gene("lente", "entier", 5, 200))
ORDONNES = (("rapide", "lente"),)


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    ecart = marche.ema_en(g["rapide"], j) - marche.ema_en(g["lente"], j)
    r = marche.volatilite(g["lente"], j)
    return torch.where(r > 0, ind.signe(ecart) * ind.plafond(ecart.abs() / r), ind.NAN)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_exponential_moving_average_cross(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const float ecart = ema_en(m, (int)g[1], j) - ema_en(m, (int)g[2], j);
    const float r = volatilite(m, (int)g[2], j);
    return r > 0.f ? signe(ecart) * plafond(fabsf(ecart) / r) : nan_f();
}
"""
