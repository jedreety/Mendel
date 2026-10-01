"""Ultimate Oscillator de Larry Williams (modules/rules/ultimate_oscillator.py), lu en retour a la moyenne : sous bas
+1, au-dessus de haut -1, entre les deux s'abstient ; sans amplitude sur un des trois horizons, s'abstient.

Pression d'achat d'une barre : cloture moins le plus bas entre son plus bas et la cloture precedente. Moyenne sur n
barres : somme des pressions sur somme des etendues vraies. UO = 100 x (4 x court + 2 x moyen + long) / 7.
Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 100.
"""
import torch

from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE, SEUIL_BAS, SEUIL_HAUT, seuils

NOM = "regle_ultimate_oscillator"
GENES = (ECHELLE, Gene("court", "entier", 2, 20), Gene("moyen", "entier", 5, 50), Gene("long", "entier", 10, 100),
         SEUIL_BAS, SEUIL_HAUT)
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    moyennes, etendues = [], []
    for nom in ("court", "moyen", "long"):
        n = g[nom]
        etendue = n.float() * marche.volatilite(n, j)
        moyennes.append(marche.somme_pression_en(n, j).float() / etendue)
        etendues.append(etendue)
    court, moyen, long_ = moyennes
    uo = (4 * court + 2 * moyen + long_) * (100 / 7)
    amplitude = (etendues[0] > 0) & (etendues[1] > 0) & (etendues[2] > 0)
    return torch.where(amplitude, seuils(uo, g["bas"], g["haut"]), 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES. Arrondis explicites : pas de FMA.
CUDA = r"""
__device__ __forceinline__ float moyenne_uo(const Marche& m, int n, int j, bool* amplitude) {
    const float etendue = (float)n * volatilite(m, n, j);
    *amplitude = *amplitude && etendue > 0.f;
    const float pression = valide(m, j, n + 1) ? (float)fenetre64(m, m.somme_pression, n, j) : nan_f();
    return pression / etendue;
}

__device__ float signal_regle_ultimate_oscillator(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    bool amplitude = true;
    const float court = moyenne_uo(m, (int)g[1], j, &amplitude);
    const float moyen = moyenne_uo(m, (int)g[2], j, &amplitude);
    const float long_ = moyenne_uo(m, (int)g[3], j, &amplitude);
    if (!amplitude) return 0.f;
    const float somme = __fadd_rn(__fadd_rn(__fmul_rn(4.f, court), __fmul_rn(2.f, moyen)), long_);
    return seuils(__fmul_rn(somme, (float)(100.0 / 7.0)), g[4], g[5]);
}
"""
