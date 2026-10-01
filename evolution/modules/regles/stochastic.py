"""Stochastique %K sur n barres (modules/rules/stochastic.py), lu en retour a la moyenne : sous bas +1, au-dessus de
haut -1, entre les deux s'abstient ; sans amplitude, s'abstient. Intensite : profondeur au-dela du seuil, rapportee
a la marge jusqu'a 0 ou 100.

La table garde le %K de chaque periode ; le noyau applique les seuils.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, SEUIL_BAS, SEUIL_HAUT, lire_oscillateur, oscillateur, seuils

NOM = "regle_stochastic"
GENES = (ECHELLE, Gene("n", "entier", 2, 100), SEUIL_BAS, SEUIL_HAUT)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    lignes = []
    for n in range(2, 101):
        haut, bas = ind.plus_haut(b["haut"], n), ind.plus_bas(b["bas"], n)
        k = torch.where(haut > bas, 100 * (b["cloture"] - bas) / (haut - bas), ind.NAN)
        lignes.append(oscillateur(k))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul, indefini=True)


def signal(marche, table, i, g, bot):
    return seuils(lire_oscillateur(marche, table, g["n"] - 2, marche.indice(g["echelle"], i)), g["bas"], g["haut"])


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_stochastic(const Marche& m, const float* g, int i, int periode_atr) {
    return seuils(lire_oscillateur(m, TABLE_REGLE_STOCHASTIC, (int)g[1] - 2, indice(m, (int)g[0], i)), g[2], g[3]);
}
"""
