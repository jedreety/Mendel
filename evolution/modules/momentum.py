"""Momentum : tanh((C - C il y a N barres)/(ATR x racine de N))."""
import torch

from evolution.gene import ECHELLES, Gene

NOM = "momentum"
GENES = (
    Gene("echelle", "categoriel", categories=ECHELLES),
    Gene("n", "entier", 1, 500),
)
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    ecart = marche.cloture_en(j) - marche.cloture_avant(g["n"], j)
    return torch.tanh(marche.diviser(ecart, marche.atr_en(bot["periode_atr"], j) * g["n"].float().sqrt()))


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_momentum(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int n = (int)g[1];
    const float ecart = cloture_en(m, j) - cloture_avant(m, n, j);
    return tanhf(diviser(ecart, atr_en(m, periode_atr, j) * sqrtf((float)n)));
}
"""
