"""Money Flow Index sur n barres (modules/rules/money_flow_index.py), RSI du prix typique pondere par le volume, lu
en retour a la moyenne : sous bas +1, au-dessus de haut -1, entre les deux s'abstient ; sans flux, s'abstient.
Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.

La table garde le MFI de chaque periode ; le noyau applique les seuils.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, SEUIL_BAS, SEUIL_HAUT, lire_oscillateur, oscillateur, seuils

NOM = "regle_money_flow_index"
GENES = (ECHELLE, Gene("n", "entier", 2, 100), SEUIL_BAS, SEUIL_HAUT)
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    typique = (b["haut"] + b["bas"] + b["cloture"]) / 3
    veille = ind.avant(typique, 1)
    flux = typique * b["volume"]
    positif = torch.where(typique > veille, flux, 0.0)
    negatif = torch.where(typique < veille, flux, 0.0)
    compte_flux = (typique != veille) & (b["volume"] > 0) & ~torch.isnan(veille)
    lignes = []
    for n in range(2, 101):
        p, m = ind.somme(positif, n), ind.somme(negatif, n)
        mfi = torch.where(ind.compte(compte_flux, n) > 0, 100 * p / (p + m), ind.NAN)
        lignes.append(oscillateur(ind.depuis(mfi, n)))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul, indefini=True)


def signal(marche, table, i, g, bot):
    return seuils(lire_oscillateur(marche, table, g["n"] - 2, marche.indice(g["echelle"], i)), g["bas"], g["haut"])


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_money_flow_index(const Marche& m, const float* g, int i, int periode_atr) {
    return seuils(lire_oscillateur(m, TABLE_REGLE_MONEY_FLOW_INDEX, (int)g[1] - 2, indice(m, (int)g[0], i)), g[2], g[3]);
}
"""
