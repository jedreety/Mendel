"""Jour de la semaine UTC (modules/rules/day_of_week.py) : 1 quand la prochaine barre commence le jour choisi,
0 sinon (0 = lundi). Le sens du vote de la regle est laisse au reseau, qui en apprend le poids.
"""
from evolution.gene import Gene

NOM = "regle_day_of_week"
GENES = (Gene("jour", "entier", 0, 6, circulaire=True),)
ORDONNES = ()


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    return (marche.jour.take(i).long() == g["jour"]).float()


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_day_of_week(const Marche& m, const float* g, int i, int periode_atr) {
    return (int)m.jour[i] == (int)g[0] ? 1.f : 0.f;
}
"""
