"""Premiere bougie : tanh(max(dh, 0)) - tanh(max(db, 0)), toujours a l'echelle horaire.

dh = (C - H1)/ATR - seuil et db = (B1 - C)/ATR - seuil, ou H1 et B1 sont le plus haut et le plus bas de la
premiere bougie de la session. 0 tant que cette bougie n'est pas close.
"""
import math

import torch

from evolution.gene import Gene

NOM = "premiere_bougie"
GENES = (
    Gene("heure", "entier", 0, 23, circulaire=True),
    Gene("duree", "entier", 1, 4),
    Gene("seuil", "reel", 0, 3),
)
ORDONNES = ()
DUREE_MAX = 4


def preparer(marche):
    """H1 et B1 pour chaque heure de session et chaque duree de bougie : une ligne par couple."""
    barres = marche.barres[0]
    ouvertures = marche.heures_cloture - 1
    i = torch.arange(marche.n1, dtype=torch.int64)
    hauts, bas = [], []
    for heure in range(24):
        depuis = (ouvertures - heure) % 24  # heures ecoulees depuis le debut de la session en cours
        debut = i - depuis
        for duree in range(1, DUREE_MAX + 1):
            close = (depuis >= duree - 1) & (debut >= 0)
            lignes = [(debut + m).clamp(0, marche.n1 - 1) for m in range(duree)]
            haut = torch.stack([barres["haut"][ligne] for ligne in lignes]).amax(0)
            bas_ = torch.stack([barres["bas"][ligne] for ligne in lignes]).amin(0)
            hauts.append(torch.where(close, haut, math.nan))
            bas.append(torch.where(close, bas_, math.nan))
    return marche._gpu(torch.stack(hauts).float()), marche._gpu(torch.stack(bas).float())


def signal(marche, tables, i, g, bot):
    hauts, bas = tables
    ligne = (g["heure"] * DUREE_MAX + g["duree"] - 1) * marche.n1 + i
    c = marche.cloture_en(i)
    atr = marche.atr_en(bot["periode_atr"], i)
    dh = marche.diviser(c - hauts.take(ligne), atr) - g["seuil"]
    db = marche.diviser(bas.take(ligne) - c, atr) - g["seuil"]
    return torch.tanh(dh.clamp(min=0)) - torch.tanh(db.clamp(min=0))


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_premiere_bougie(const Marche& m, const float* g, int i, int periode_atr) {
    const i64 ligne = (i64)((int)g[0] * 4 + (int)g[1] - 1) * m.n1 + i;
    const float* hauts = m.tables[TABLE_PREMIERE_BOUGIE];
    const float* bas = m.tables[TABLE_PREMIERE_BOUGIE + 1];
    const float c = cloture_en(m, i);
    const float atr = atr_en(m, periode_atr, i);
    const float dh = diviser(c - hauts[ligne], atr) - g[2];
    const float db = diviser(bas[ligne] - c, atr) - g[2];
    return tanhf(positif(dh)) - tanhf(positif(db));
}
"""
