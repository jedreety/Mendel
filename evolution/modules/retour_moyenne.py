"""Retour a la moyenne : -tanh((C - MM sur N)/ecart-type sur N). 0 si l'ecart-type est nul."""
import torch

from evolution.gene import ECHELLES, Gene

NOM = "retour_moyenne"
GENES = (
    Gene("echelle", "categoriel", categories=ECHELLES),
    Gene("n", "entier", 5, 500),
)
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    ecart_type = marche.ecart_type(g["n"], j)
    ecart = marche.cloture_en(j) - marche.moyenne_simple(g["n"], j)
    return torch.where(ecart_type == 0, 0.0, -torch.tanh(marche.diviser(ecart, ecart_type)))


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_retour_moyenne(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int n = (int)g[1];
    const float s = ecart_type(m, n, j);
    const float ecart = cloture_en(m, j) - moyenne_simple(m, n, j);
    return s == 0.f ? 0.f : -tanhf(diviser(ecart, s));
}
"""
