"""MACD (modules/rules/macd.py) : histogramme, ligne MACD moins sa ligne de signal, positif +1, negatif -1.
Intensite : histogramme en unites de volatilite (periode lente), plafonne a 1.

Ligne MACD : moyenne exponentielle rapide moins lente. Ligne de signal : sa moyenne exponentielle de periode s.
Une moyenne exponentielle de coefficient a d'une autre, de coefficient b, se lit sans calcul recursif :
[b (1 - a) EMA_a - a (1 - b) EMA_b] / (b - a), des moyennes du marche. Une periode de signal egale a la rapide ou a la
lente, qui annulerait b - a, est avancee d'une barre.

Ecart avec le moteur : les moyennes portent sur tout l'historique, et non sur une fenetre de 3 x lente + signal
barres ; les deux se rejoignent des que l'amorce s'est effacee.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_macd"
GENES = (ECHELLE, Gene("rapide", "entier", 2, 50), Gene("lente", "entier", 5, 200), Gene("signal", "entier", 2, 50))
ORDONNES = (("rapide", "lente"),)


def preparer(marche):
    return None


def signal(marche, tables, i, g, bot):
    j = marche.indice(g["echelle"], i)
    f, s, n = g["rapide"], g["lente"], g["signal"]
    n = torch.where(n == f, n + 1, n)
    n = torch.where(n == s, n + 1, n)
    n = torch.where(n == f, n + 1, n)
    ef, es, en = marche.ema_en(f, j), marche.ema_en(s, j), marche.ema_en(n, j)
    a = 2 / (n.float() + 1)

    def lissee(periode, ema):
        """EMA de coefficient a de l'EMA donnee, de periode `periode`."""
        b = 2 / (periode.float() + 1)
        return (b * (1 - a) * en - a * (1 - b) * ema) / (b - a)

    histogramme = (ef - es) - (lissee(f, ef) - lissee(s, es))
    r = marche.volatilite(s, j)
    return torch.where(r > 0, ind.signe(histogramme) * ind.plafond(histogramme.abs() / r), ind.NAN)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES. Arrondis explicites : pas de FMA.
CUDA = r"""
__device__ __forceinline__ float lissee_macd(float a, int periode, float en, float ema) {
    const float b = 2.f / ((float)periode + 1.f);
    const float gauche = __fmul_rn(__fmul_rn(b, __fsub_rn(1.f, a)), en);
    const float droite = __fmul_rn(__fmul_rn(a, __fsub_rn(1.f, b)), ema);
    return __fsub_rn(gauche, droite) / __fsub_rn(b, a);
}

__device__ float signal_regle_macd(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const int f = (int)g[1], s = (int)g[2];
    int n = (int)g[3];
    if (n == f) ++n;
    if (n == s) ++n;
    if (n == f) ++n;
    const float ef = ema_en(m, f, j), es = ema_en(m, s, j), en = ema_en(m, n, j);
    const float a = 2.f / ((float)n + 1.f);
    const float histogramme = __fsub_rn(__fsub_rn(ef, es), __fsub_rn(lissee_macd(a, f, en, ef), lissee_macd(a, s, en, es)));
    const float r = volatilite(m, s, j);
    return r > 0.f ? signe(histogramme) * plafond(fabsf(histogramme) / r) : nan_f();
}
"""
