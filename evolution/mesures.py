"""Mesures de performance : ratio de Sharpe, Probabilistic et Deflated Sharpe Ratio.

Le Sharpe se calcule sur les rendements horaires du capital. Le PSR et le DSR suivent Bailey et Lopez de
Prado (2012, 2014) ; le Sharpe maximal attendu sous le hasard suit Bailey, Borwein, Lopez de Prado et Zhu.
"""
import math
from statistics import NormalDist

EULER = 0.5772156649015329
HEURES_PAR_AN = 8760
NORMALE = NormalDist()


def moments(sommes: list[float], n: int) -> tuple[float, float, float, float]:
    """Moyenne, ecart-type, asymetrie et kurtosis (non centree sur 3) a partir des sommes des puissances."""
    m1, m2, m3, m4 = (s / n for s in sommes)
    variance = max(m2 - m1 * m1, 0.0)
    ecart = math.sqrt(variance)
    if ecart == 0:
        return m1, 0.0, 0.0, 3.0
    c3 = m3 - 3 * m1 * m2 + 2 * m1**3
    c4 = m4 - 4 * m1 * m3 + 6 * m1 * m1 * m2 - 3 * m1**4
    return m1, ecart, c3 / ecart**3, c4 / variance**2


def sharpe(moyenne: float, ecart: float) -> float:
    """Ratio de Sharpe par periode ; 0 pour une serie constante."""
    return moyenne / ecart if ecart > 0 else 0.0


def sharpe_annualise(moyenne: float, ecart: float) -> float:
    return sharpe(moyenne, ecart) * math.sqrt(HEURES_PAR_AN)


def psr(sr: float, n: int, asymetrie: float, kurtosis: float, sr_reference: float = 0.0) -> float:
    """Probabilite que le vrai Sharpe depasse sr_reference, Sharpe et reference par periode."""
    denominateur = 1 - asymetrie * sr + (kurtosis - 1) / 4 * sr * sr
    if n < 2 or denominateur <= 0:
        return math.nan
    return NORMALE.cdf((sr - sr_reference) * math.sqrt(n - 1) / math.sqrt(denominateur))


def sharpe_maximal_attendu(sharpes_essais: list[float]) -> float:
    """Sharpe maximal attendu parmi les essais si aucun n'avait d'avantage."""
    essais = len(sharpes_essais)
    if essais < 2:
        return 0.0
    moyenne = sum(sharpes_essais) / essais
    variance = sum((s - moyenne) ** 2 for s in sharpes_essais) / (essais - 1)
    return math.sqrt(variance) * ((1 - EULER) * NORMALE.inv_cdf(1 - 1 / essais)
                                  + EULER * NORMALE.inv_cdf(1 - 1 / (essais * math.e)))


def dsr(sr: float, n: int, asymetrie: float, kurtosis: float, sharpes_essais: list[float]) -> float:
    """Deflated Sharpe Ratio : le PSR contre le Sharpe maximal attendu des essais."""
    return psr(sr, n, asymetrie, kurtosis, sharpe_maximal_attendu(sharpes_essais))
