"""RSI stochastique de Chande et Kroll (modules/rules/stochastic_rsi.py) : position du dernier RSI de Cutler
(periode_rsi variations) dans l'amplitude des `periode` derniers RSI, lue en retour a la moyenne : sous bas +1,
au-dessus de haut -1, entre les deux s'abstient. Un RSI indefini dans la fenetre, ou des RSI tous egaux :
s'abstient. Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.

La table garde le %K de chaque couple de periodes ; le noyau applique les seuils.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, SEUIL_BAS, SEUIL_HAUT, lire_oscillateur, oscillateur, seuils
from evolution.modules.regles.rsi import rsi_cutler

NOM = "regle_stochastic_rsi"
GENES = (ECHELLE, Gene("periode_rsi", "entier", 2, 20), Gene("periode", "entier", 2, 20), SEUIL_BAS, SEUIL_HAUT)
ORDONNES = ()
PERIODES = int(GENES[2].haut) - int(GENES[2].bas) + 1


def calcul(b: dict) -> torch.Tensor:
    lignes = []
    for periode_rsi in range(2, 21):
        rsi = rsi_cutler(b["cloture"], periode_rsi)
        for periode in range(2, 21):
            fenetre = ind.fenetres(rsi, periode)
            haut, bas = fenetre.amax(1), fenetre.amin(1)
            k = torch.where(haut > bas, 100 * (rsi - bas) / (haut - bas), ind.NAN)
            lignes.append(oscillateur(k))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul, indefini=True)


def signal(marche, table, i, g, bot):
    ligne = (g["periode_rsi"] - 2) * PERIODES + g["periode"] - 2
    return seuils(lire_oscillateur(marche, table, ligne, marche.indice(g["echelle"], i)), g["bas"], g["haut"])


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = rf"""
__device__ float signal_regle_stochastic_rsi(const Marche& m, const float* g, int i, int periode_atr) {{
    const int ligne = ((int)g[1] - 2) * {PERIODES} + (int)g[2] - 2;
    return seuils(lire_oscillateur(m, TABLE_REGLE_STOCHASTIC_RSI, ligne, indice(m, (int)g[0], i)), g[3], g[4]);
}}
"""
