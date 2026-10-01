"""Cassure de volatilite de Larry Williams (modules/rules/volatility_breakout.py) : la bougie clot a plus de k fois
l'amplitude de la precedente au-dessus de son ouverture +1, en dessous -1, sinon s'abstient. Intensite : part du
corps dans l'amplitude de la bougie.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_volatility_breakout"
GENES = (ECHELLE, Gene("k", "reel", 0, 2))
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    seuil = g["k"] * (marche.precedente(marche.haut, j) - marche.precedente(marche.bas, j))
    corps = marche.en(marche.cloture, j) - marche.en(marche.ouverture, j)
    y = ind.signe(corps) * (corps.abs() / (marche.en(marche.haut, j) - marche.en(marche.bas, j)))
    return torch.where((corps > seuil) | (corps < -seuil), y, 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_volatility_breakout(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const float seuil = g[1] * (precedente(m, m.haut_c, j) - precedente(m, m.bas_c, j));
    const float corps = en(m.cloture, j) - en(m.ouverture_c, j);
    if (!(corps > seuil || corps < -seuil)) return 0.f;
    return signe(corps) * (fabsf(corps) / (en(m.haut_c, j) - en(m.bas_c, j)));
}
"""
