"""RSI de Wilder : (RSI - 50)/50."""
import math

import torch

from evolution.gene import ECHELLES, Gene
from evolution.marche import lisser

NOM = "rsi"
GENES = (
    Gene("echelle", "categoriel", categories=ECHELLES),
    Gene("periode", "entier", 2, 100),
)
ORDONNES = ()
PREMIERE = int(GENES[1].bas)


def preparer(marche):
    """RSI de toutes les periodes utiles. Sans hausse ni baisse sur la periode, il vaut 50."""
    periodes = torch.arange(PREMIERE, int(GENES[1].haut) + 1, dtype=torch.int64)
    alpha = 1.0 / periodes.double()
    lignes = []
    for b in marche.barres:
        ecart = torch.cat((torch.zeros(1, dtype=torch.float64), b["cloture"].diff()))
        hausse = lisser(ecart.clamp(min=0), periodes, alpha, 1)
        baisse = lisser((-ecart).clamp(min=0), periodes, alpha, 1)
        total = hausse + baisse
        lignes.append(torch.where(total > 0, 100 * hausse / total, torch.where(total == 0, 50.0, math.nan)))
    return marche.table(lignes)


def signal(marche, table, i, g, bot):
    j = marche.indice(g["echelle"], i)
    rsi = torch.where(j >= 0, table.take((g["periode"] - PREMIERE) * marche.ncomb + j.clamp(min=0)), math.nan)
    return (rsi - 50) / 50


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES. PyTorch divise un tenseur par un
# scalaire en le multipliant par l'inverse arrondi en simple : 0.02f.
CUDA = r"""
__device__ float signal_rsi(const Marche& m, const float* g, int i, int periode_atr) {
    const int j = indice(m, (int)g[0], i);
    const float rsi = j >= 0 ? m.tables[TABLE_RSI][(i64)((int)g[1] - 2) * m.ncomb + j] : nan_f();
    return (rsi - 50.f) * 0.02f;
}
"""
