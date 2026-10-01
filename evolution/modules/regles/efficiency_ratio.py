"""Ratio d'efficacite de Kaufman sur n barres (modules/rules/efficiency_ratio.py) : deplacement net des clotures
rapporte a la somme de leurs deplacements. A partir du seuil, vote le sens du deplacement net ; en dessous, le
marche oscille et la regle s'abstient ; sans aucun deplacement aussi. Intensite : le ratio.

La table garde le signal avant le seuil, que le noyau applique.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_efficiency_ratio"
GENES = (ECHELLE, Gene("n", "entier", 2, 100), Gene("seuil", "reel", 0, 1))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    variation = torch.nan_to_num((b["cloture"] - ind.avant(b["cloture"], 1)).abs())
    lignes = []
    for n in range(2, 101):
        deplacement = b["cloture"] - ind.avant(b["cloture"], n)
        chemin = ind.somme(variation, n)
        y = ind.vote(ind.signe(deplacement), deplacement.abs() / chemin, ind.compte(variation > 0, n) > 0)
        lignes.append(ind.depuis(y, n))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul, bits=16)  # le signal saute au seuil : 16 bits pour le trancher


def signal(marche, table, i, g, bot):
    v = marche.lire8(table, g["n"] - 2, marche.indice(g["echelle"], i))
    return torch.where(v.abs() >= g["seuil"], v, 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_efficiency_ratio(const Marche& m, const float* g, int i, int periode_atr) {
    const float v = lire16(m, TABLE_REGLE_EFFICIENCY_RATIO, (int)g[1] - 2, indice(m, (int)g[0], i));
    return fabsf(v) >= g[2] ? v : 0.f;
}
"""
