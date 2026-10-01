"""Volatilite relative : tanh(ATR court/ATR long - 1)."""
import torch

from evolution.gene import ECHELLES, Gene

NOM = "volatilite_relative"
GENES = (
    Gene("echelle", "categoriel", categories=ECHELLES),
    Gene("courte", "entier", 2, 50),
    Gene("longue", "entier", 20, 500),
)
ORDONNES = (("courte", "longue"),)


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    return torch.tanh(marche.diviser(marche.atr_en(g["courte"], j), marche.atr_en(g["longue"], j)) - 1)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_volatilite_relative(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    return tanhf(diviser(atr_en(m, (int)g[1], j), atr_en(m, (int)g[2], j)) - 1.f);
}
"""
