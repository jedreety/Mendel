"""Plage horaire UTC (modules/rules/hour_of_day.py) : 1 quand la prochaine barre commence dans [debut, fin), la
plage pouvant passer minuit, 0 sinon. Le sens du vote de la regle est laisse au reseau, qui en apprend le poids.
"""
import torch

from evolution.gene import Gene

NOM = "regle_hour_of_day"
GENES = (Gene("debut", "entier", 0, 23, circulaire=True), Gene("fin", "entier", 0, 23, circulaire=True))
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    heure = marche.heure.take(i).long()
    debut, fin = g["debut"], g["fin"]
    dedans = torch.where(debut <= fin, (debut <= heure) & (heure < fin), (heure >= debut) | (heure < fin))
    return dedans.float()


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_hour_of_day(const Marche& m, const float* g, int i, int periode_atr) {
    const int heure = m.heure[i], debut = (int)g[0], fin = (int)g[1];
    const bool dedans = debut <= fin ? (debut <= heure && heure < fin) : (heure >= debut || heure < fin);
    return dedans ? 1.f : 0.f;
}
"""
