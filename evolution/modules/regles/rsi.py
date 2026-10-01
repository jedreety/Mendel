"""RSI de Cutler (modules/rules/rsi.py) : moyennes simples des hausses et des baisses sur n variations, lu en retour a
la moyenne : sous bas +1, au-dessus de haut -1, entre les deux s'abstient ; sans aucune variation, s'abstient.
Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.

La table garde le RSI de chaque periode ; le noyau applique les seuils.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, SEUIL_BAS, SEUIL_HAUT, lire_oscillateur, oscillateur, seuils

NOM = "regle_rsi"
GENES = (ECHELLE, Gene("n", "entier", 2, 100), SEUIL_BAS, SEUIL_HAUT)
ORDONNES = ()


def rsi_cutler(cloture: torch.Tensor, n: int) -> torch.Tensor:
    """RSI des n dernieres variations, NaN sans aucune variation ou sans historique suffisant."""
    variation = torch.nan_to_num(cloture - ind.avant(cloture, 1))
    hausses, baisses = ind.somme(variation.clamp(min=0), n), ind.somme((-variation).clamp(min=0), n)
    rsi = torch.where(ind.compte(variation != 0, n) > 0, 100 * hausses / (hausses + baisses), ind.NAN)
    return ind.depuis(rsi, n)


def calcul(b: dict) -> torch.Tensor:
    return torch.stack([oscillateur(rsi_cutler(b["cloture"], n)) for n in range(2, 101)])


def preparer(marche):
    return marche.table8(calcul, indefini=True)


def signal(marche, table, i, g, bot):
    return seuils(lire_oscillateur(marche, table, g["n"] - 2, marche.indice(g["echelle"], i)), g["bas"], g["haut"])


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_rsi(const Marche& m, const float* g, int i, int periode_atr) {
    return seuils(lire_oscillateur(m, TABLE_REGLE_RSI, (int)g[1] - 2, indice(m, (int)g[0], i)), g[2], g[3]);
}
"""
