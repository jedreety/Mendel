"""SAR parabolique de Wilder (modules/rules/parabolic_sar.py) : tendance haussiere +1, baissiere -1. Intensite :
distance entre la cloture et le SAR en unites de volatilite (10 barres), plafonnee a 1.

Pas d'acceleration et plafond prennent une des valeurs usuelles (0,02 et 0,2 chez Wilder). Le SAR ne depasse jamais
les extremes des deux barres precedentes, ni, au retournement, ceux de la barre courante et de la precedente. Comme
dans le moteur, la serie part d'une fenetre fixe de 50 barres, dans le sens de la variation de cloture des deux
premieres.
"""
import torch

from evolution import indicateurs as ind
from evolution.gene import Gene
from evolution.modules.regles.commun import ECHELLE

NOM = "regle_parabolic_sar"
PAS = (0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05)
MAXIMUMS = (0.1, 0.15, 0.2, 0.25, 0.3, 0.4)
GENES = (ECHELLE, Gene("pas", "categoriel", categories=PAS), Gene("maximum", "categoriel", categories=MAXIMUMS))
ORDONNES = ()
FENETRE = 50


def sar(b: dict) -> torch.Tensor:
    """(combinaisons, barres) : le signal de chaque couple (pas, maximum), dans l'ordre des pas puis des maximums."""
    pas = torch.tensor([p for p in PAS for _ in MAXIMUMS], dtype=torch.float64)[:, None]
    maximum = torch.tensor([m for _ in PAS for m in MAXIMUMS], dtype=torch.float64)[:, None]
    barre = lambda i: ind.decaler(b, FENETRE - 1 - i)  # la barre i de la fenetre
    b0, b1 = barre(0), barre(1)
    montante = (b1["cloture"] >= b0["cloture"]).expand(pas.shape[0], -1)
    niveau = torch.where(montante, b0["bas"], b0["haut"])
    extreme = torch.where(montante, b0["haut"], b0["bas"])
    acceleration = pas.expand_as(niveau)
    for i in range(1, FENETRE):
        x, veille = barre(i), barre(i - 1)
        avant_veille = barre(i - 2) if i >= 2 else veille
        niveau = niveau + acceleration * (extreme - niveau)
        # Hausse : le SAR ne depasse pas les plus bas des deux barres precedentes.
        n_haut = torch.minimum(niveau, torch.minimum(avant_veille["bas"], veille["bas"]))
        retourne_bas = x["bas"] <= n_haut
        record_haut = ~retourne_bas & (x["haut"] > extreme)
        # Baisse : le SAR ne passe pas sous leurs plus hauts.
        n_bas = torch.maximum(niveau, torch.maximum(avant_veille["haut"], veille["haut"]))
        retourne_haut = x["haut"] >= n_bas
        record_bas = ~retourne_haut & (x["bas"] < extreme)
        plus_haut_ = torch.maximum(extreme, torch.maximum(x["haut"], veille["haut"]))
        plus_bas_ = torch.minimum(extreme, torch.minimum(x["bas"], veille["bas"]))
        accelere = torch.clamp(acceleration + pas, max=maximum)
        niveau, extreme, acceleration, montante = (
            torch.where(montante, torch.where(retourne_bas, plus_haut_, n_haut),
                        torch.where(retourne_haut, plus_bas_, n_bas)),
            torch.where(montante, torch.where(retourne_bas, x["bas"], torch.where(record_haut, x["haut"], extreme)),
                        torch.where(retourne_haut, x["haut"], torch.where(record_bas, x["bas"], extreme))),
            torch.where(montante, torch.where(retourne_bas, pas, torch.where(record_haut, accelere, acceleration)),
                        torch.where(retourne_haut, pas, torch.where(record_bas, accelere, acceleration))),
            torch.where(montante, ~retourne_bas, retourne_haut),
        )
    r = ind.volatilite(b, 10)
    y = ind.vote(torch.where(montante, 1.0, -1.0), ind.plafond((b["cloture"] - niveau).abs() / r), r > 0)
    y[:, :FENETRE - 1] = ind.NAN
    return y


def calcul(b: dict) -> torch.Tensor:
    return sar(b)


def preparer(marche):
    return marche.table8(calcul)


def signal(marche, table, i, g, bot):
    return marche.lire8(table, g["pas"] * len(MAXIMUMS) + g["maximum"], marche.indice(g["echelle"], i))


# Meme calcul dans le noyau (evolution/noyau.cu) ; g suit l'ordre de GENES.
CUDA = rf"""
__device__ float signal_regle_parabolic_sar(const Marche& m, const float* g, int i, int periode_atr) {{
    return lire8(m, TABLE_REGLE_PARABOLIC_SAR, (int)g[1] * {len(MAXIMUMS)} + (int)g[2], indice(m, (int)g[0], i));
}}
"""
