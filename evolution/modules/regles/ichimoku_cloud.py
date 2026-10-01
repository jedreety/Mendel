"""Nuage d'Ichimoku (modules/rules/ichimoku_cloud.py) : cloture au-dessus du nuage +1, en dessous -1, dedans 0.
Intensite : distance au nuage en unites de volatilite (periode tenkan), plafonnee a 1.

Le nuage en vigueur a ete calcule kijun barres plus tot : senkou A = milieu de tenkan et kijun, senkou B = milieu des
extremes sur senkou barres, le milieu d'une periode etant la moyenne de son plus haut et de son plus bas.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_ichimoku_cloud"
GENES = (ECHELLE, Gene("tenkan", "entier", 2, 50), Gene("kijun", "entier", 5, 100), Gene("senkou", "entier", 10, 200))
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    passe = torch.where(marche.valide(j, g["kijun"] + 1), j - g["kijun"], -1)
    milieu = lambda n: (marche.plus_haut(n, passe) + marche.plus_bas(n, passe)) * 0.5
    a, b = (milieu(g["tenkan"]) + milieu(g["kijun"])) * 0.5, milieu(g["senkou"])
    haut, bas = torch.maximum(a, b), torch.minimum(a, b)
    c, r = marche.cloture_en(j), marche.volatilite(g["tenkan"], j)
    y = torch.where(c > haut, ind.plafond((c - haut) / r), -ind.plafond((bas - c) / r))
    return torch.where((bas <= c) & (c <= haut), 0.0, torch.where(r > 0, y, ind.NAN))


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ __forceinline__ float milieu_ichimoku(const Marche& m, int n, int j) {
    return (plus_haut(m, n, j) + plus_bas(m, n, j)) * 0.5f;
}

__device__ float signal_regle_ichimoku_cloud(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int kijun = (int)g[2];
    const int passe = valide(m, j, kijun + 1) ? j - kijun : -1;
    const float a = (milieu_ichimoku(m, (int)g[1], passe) + milieu_ichimoku(m, kijun, passe)) * 0.5f;
    const float b = milieu_ichimoku(m, (int)g[3], passe);
    if (isnan(a) || isnan(b)) return nan_f();  // comme torch.maximum, qui propage NaN
    const float haut = fmaxf(a, b), bas = fminf(a, b);
    const float c = cloture_en(m, j), r = volatilite(m, (int)g[1], j);
    if (bas <= c && c <= haut) return 0.f;
    if (!(r > 0.f)) return nan_f();
    return c > haut ? plafond((c - haut) / r) : -plafond((bas - c) / r);
}
"""
