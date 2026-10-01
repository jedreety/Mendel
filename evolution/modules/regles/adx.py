"""ADX de Wilder sans lissage exponentiel (modules/rules/adx.py) : vote le cote dominant de +DM contre -DM sur les
n dernieres barres quand l'ADX atteint le seuil, sinon s'abstient ; 0 a egalite, s'abstient sans mouvement.

DX : |somme +DM - somme -DM| / (somme +DM + somme -DM) sur n barres. ADX : moyenne des n derniers DX, sur 100.
Intensite : ADX sur 100. La table garde le signal avant le seuil, que le noyau applique.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE
from evolution.modules.regles.directional_movement import mouvements

NOM = "regle_adx"
GENES = (ECHELLE, Gene("n", "entier", 2, 100), Gene("seuil", "reel", 0, 60))
ORDONNES = ()


def calcul(b: dict) -> torch.Tensor:
    plus, moins = mouvements(b)
    lignes = []
    for n in range(2, 101):
        p, m = ind.somme(plus, n), ind.somme(moins, n)
        mouvement = ind.compte((plus > 0) | (moins > 0), n) > 0
        dx = torch.where(mouvement, (p - m).abs() / (p + m), 0.0)
        adx = ind.somme(torch.nan_to_num(dx), n) / n
        y = ind.vote(ind.signe(p - m), adx, mouvement)
        lignes.append(ind.depuis(y, 2 * n - 1))
    return torch.stack(lignes)


def preparer(marche):
    return marche.table8(calcul, bits=16)  # le signal saute au seuil : 16 bits pour le trancher


def signal(marche, table, i, g, bot):
    v = marche.lire8(table, g["n"] - 2, marche.indice(g["echelle"], i))
    return torch.where(v.abs() * 100 >= g["seuil"], v, 0.0)


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = r"""
__device__ float signal_regle_adx(const Marche& m, const float* g, int i, int periode_atr) {
    const float v = lire16(m, TABLE_REGLE_ADX, (int)g[1] - 2, indice(m, (int)g[0], i));
    return fabsf(v) * 100.f >= g[2] ? v : 0.f;
}
"""
