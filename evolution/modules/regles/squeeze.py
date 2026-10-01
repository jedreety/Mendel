"""Sortie de compression, d'apres le TTM Squeeze de Carter (modules/rules/squeeze.py) : sur l'avant-derniere barre,
les bandes de Bollinger (bollinger ecarts-types) tenaient dans le canal de Keltner (keltner unites de volatilite) ;
sur la derniere, elles en sortent. Vote alors le sens de la cloture par rapport a la moyenne des clotures, sinon
s'abstient. Bandes et canal portent sur n barres. Intensite : ecart en unites de volatilite, plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_squeeze"
GENES = (ECHELLE, Gene("n", "entier", 5, 100), Gene("bollinger", "reel", 1, 3), Gene("keltner", "reel", 0.5, 3))
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    n, bollinger, keltner = g["n"], g["bollinger"], g["keltner"]
    dedans = lambda k: bollinger * marche.ecart_type(n, k) < keltner * marche.volatilite(n, k)
    veille = torch.where(marche.valide(j, 2), j - 1, -1)
    ecart = marche.cloture_en(j) - marche.moyenne_simple(n, j)
    r = marche.volatilite(n, j)
    y = torch.where(r > 0, ind.signe(ecart) * ind.plafond(ecart.abs() / r), ind.NAN)
    return torch.where(~dedans(j) & dedans(veille), y, 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ __forceinline__ bool dedans_squeeze(const Marche& m, int n, float bollinger, float keltner, int j) {
    return bollinger * ecart_type(m, n, j) < keltner * volatilite(m, n, j);
}

__device__ float signal_regle_squeeze(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int n = (int)g[1];
    const int veille = valide(m, j, 2) ? j - 1 : -1;
    if (dedans_squeeze(m, n, g[2], g[3], j) || !dedans_squeeze(m, n, g[2], g[3], veille)) return 0.f;
    const float ecart = cloture_en(m, j) - moyenne_simple(m, n, j);
    const float r = volatilite(m, n, j);
    return r > 0.f ? signe(ecart) * plafond(fabsf(ecart) / r) : nan_f();
}
"""
