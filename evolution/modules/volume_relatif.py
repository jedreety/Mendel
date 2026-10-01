"""Volume relatif : tanh(V/moyenne du volume sur N - 1). 0 si la moyenne est nulle."""
import torch

from evolution.gene import ECHELLES, Gene

NOM = "volume_relatif"
GENES = (
    Gene("echelle", "categoriel", categories=ECHELLES),
    Gene("n", "entier", 5, 500),
)
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    return torch.tanh(marche.diviser(marche.volume_en(j), marche.volume_moyen(g["n"], j)) - 1)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_volume_relatif(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    return tanhf(diviser(volume_en(m, j), volume_moyen(m, (int)g[1], j)) - 1.f);
}
"""
