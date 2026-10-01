"""Bandes de Bollinger (modules/rules/bollinger_bands.py), lues en retour a la moyenne : cloture sous la bande basse
+1, au-dessus de la bande haute -1, entre les deux s'abstient ; sans ecart-type, s'abstient. Bandes : moyenne des
clotures sur n barres, plus ou moins `largeur` ecarts-types (population). Intensite : depassement au-dela de la
bande en ecarts-types, rapporte a la largeur, plafonne a 1. La lecture en cassure est le poids negatif du reseau.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_bollinger_bands"
GENES = (ECHELLE, Gene("n", "entier", 2, 100), Gene("largeur", "reel", 0.5, 4))
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    ecart_type, largeur = marche.ecart_type(g["n"], j), g["largeur"]
    z = (marche.cloture_en(j) - marche.moyenne_simple(g["n"], j)) / ecart_type
    y = torch.where(z < -largeur, ind.plafond((-z - largeur) / largeur),
                    torch.where(z > largeur, -ind.plafond((z - largeur) / largeur), 0.0))
    return torch.where(ecart_type > 0, y, 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_bollinger_bands(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int n = (int)g[1];
    const float s = ecart_type(m, n, j), largeur = g[2];
    if (!(s > 0.f)) return 0.f;
    const float z = (cloture_en(m, j) - moyenne_simple(m, n, j)) / s;
    if (z < -largeur) return plafond((-z - largeur) / largeur);
    if (z > largeur) return -plafond((z - largeur) / largeur);
    return 0.f;
}
"""
