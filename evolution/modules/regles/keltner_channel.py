"""Canal de Keltner (modules/rules/keltner_channel.py), lu en retour a la moyenne : cloture sous la bande basse +1,
au-dessus de la bande haute -1, entre les deux s'abstient ; sans amplitude, s'abstient. Centre : moyenne simple du
prix typique sur n barres. Bandes : plus ou moins `largeur` unites de volatilite. Intensite : depassement au-dela de
la bande, rapporte a la demi-largeur du canal, plafonne a 1.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_keltner_channel"
GENES = (ECHELLE, Gene("n", "entier", 2, 100), Gene("largeur", "reel", 0.5, 4))
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    n = g["n"]
    centre = (marche.somme_typique_en(n, j) / n).float()
    bande = g["largeur"] * marche.volatilite(n, j)
    c = marche.cloture_en(j)
    y = torch.where(c < centre - bande, ind.plafond((centre - bande - c) / bande),
                    torch.where(c > centre + bande, -ind.plafond((c - centre - bande) / bande), 0.0))
    return torch.where(bande > 0, y, 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_keltner_channel(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int n = (int)g[1];
    const float bande = g[2] * volatilite(m, n, j);
    if (!(bande > 0.f) || !valide(m, j, n)) return 0.f;
    const float centre = (float)(fenetre64(m, m.somme_typique, n, j) / (double)n);
    const float c = cloture_en(m, j);
    if (c < centre - bande) return plafond((centre - bande - c) / bande);
    if (c > centre + bande) return -plafond((c - centre - bande) / bande);
    return 0.f;
}
"""
