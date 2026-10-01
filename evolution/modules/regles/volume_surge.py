"""Pic de volume (modules/rules/volume_surge.py) : volume de la derniere bougie d'au moins `ratio` fois la moyenne des
n precedentes. Vote alors la couleur de la bougie, 0 sans corps, sinon s'abstient. Intensite : part du corps dans
l'amplitude de la bougie.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_volume_surge"
GENES = (ECHELLE, Gene("n", "entier", 2, 100), Gene("ratio", "reel", 1, 5))
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    n = g["n"]
    moyenne = marche.volume_moyen(n, torch.where(marche.valide(j, n + 1), j - 1, -1))
    pic = (moyenne > 0) & (marche.en(marche.volume, j) >= g["ratio"] * moyenne)
    corps = marche.en(marche.cloture, j) - marche.en(marche.ouverture, j)
    y = ind.signe(corps) * (corps.abs() / (marche.en(marche.haut, j) - marche.en(marche.bas, j)))
    return torch.where(pic & (corps != 0), y, 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_volume_surge(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int n = (int)g[1];
    const float moyenne = volume_moyen(m, n, valide(m, j, n + 1) ? j - 1 : -1);
    if (!(moyenne > 0.f && en(m.volume, j) >= g[2] * moyenne)) return 0.f;
    const float corps = en(m.cloture, j) - en(m.ouverture_c, j);
    if (corps == 0.f) return 0.f;
    return signe(corps) * (fabsf(corps) / (en(m.haut_c, j) - en(m.bas_c, j)));
}
"""
