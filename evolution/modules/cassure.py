"""Cassure : 2 (C - plus bas sur N)/(plus haut sur N - plus bas sur N) - 1.

Le canal inclut la barre courante : le signal reste dans [-1, 1]. 0 si le canal est plat.
"""
import torch

from evolution.gene import ECHELLES, Gene

NOM = "cassure"
GENES = (
    Gene("echelle", "categoriel", categories=ECHELLES),
    Gene("n", "entier", 5, 500),
)
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    haut, bas = marche.plus_haut(g["n"], j), marche.plus_bas(g["n"], j)
    etendue = haut - bas
    return torch.where(etendue == 0, 0.0, 2 * marche.diviser(marche.cloture_en(j) - bas, etendue) - 1)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_cassure(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int n = (int)g[1];
    const float haut = plus_haut(m, n, j), bas = plus_bas(m, n, j);
    const float etendue = haut - bas;
    return etendue == 0.f ? 0.f : 2.f * diviser(cloture_en(m, j) - bas, etendue) - 1.f;
}
"""
