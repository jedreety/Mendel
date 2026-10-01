"""Force interne de la barre (modules/rules/internal_bar_strength.py) : position de la cloture dans l'amplitude de la
derniere barre, (cloture - plus bas) / amplitude, lue en retour a la moyenne : sous bas +1, au-dessus de haut -1,
entre les deux s'abstient ; sans amplitude, s'abstient. Intensite : profondeur au-dela du seuil, rapportee a la marge
jusqu'a 0 ou 1.
"""
import torch

from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_internal_bar_strength"
GENES = (ECHELLE, Gene("bas", "reel", 0, 0.5), Gene("haut", "reel", 0.5, 1))
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    haut, bas = marche.en(marche.haut, j), marche.en(marche.bas, j)
    force = (marche.en(marche.cloture, j) - bas) / (haut - bas)
    y = torch.where(force < g["bas"], (g["bas"] - force) / g["bas"],
                    torch.where(force > g["haut"], -((force - g["haut"]) / (1 - g["haut"])), 0.0))
    return torch.where(haut > bas, y, 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_internal_bar_strength(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const float haut = en(m.haut_c, j), bas = en(m.bas_c, j);
    if (!(haut > bas)) return 0.f;
    const float force = (en(m.cloture, j) - bas) / (haut - bas);
    if (force < g[1]) return (g[1] - force) / g[1];
    if (force > g[2]) return -((force - g[2]) / (1.f - g[2]));
    return 0.f;
}
"""
