"""Croisement de moyennes : tanh((MM rapide - MM lente)/ATR), simples ou exponentielles."""
import torch

from evolution.gene import ECHELLES, Gene

NOM = "croisement"
GENES = (
    Gene("echelle", "categoriel", categories=ECHELLES),
    Gene("rapide", "entier", 2, 100),
    Gene("lente", "entier", 10, 400),
    Gene("type", "categoriel", categories=("simple", "exponentielle")),
)
ORDONNES = (("rapide", "lente"),)


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)

    def moyenne(n):
        return torch.where(g["type"] == 1, marche.ema_en(n, j), marche.moyenne_simple(n, j))

    atr = marche.atr_en(bot["periode_atr"], j)
    return torch.tanh(marche.diviser(moyenne(g["rapide"]) - moyenne(g["lente"]), atr))


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float moyenne_croisement(const Marche& m, int type, int n, int j) {
    return type == 1 ? ema_en(m, n, j) : moyenne_simple(m, n, j);
}

__device__ float signal_croisement(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int type = (int)g[3];
    const float ecart = moyenne_croisement(m, type, (int)g[1], j) - moyenne_croisement(m, type, (int)g[2], j);
    return tanhf(diviser(ecart, atr_en(m, periode_atr, j)));
}
"""
