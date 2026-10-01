"""Calculs vectorises sur les barres d'une echelle, en float64 sur le processeur.

Les modules de signal y calculent leurs tables, une fois par run, pour toute la serie a la fois. Une valeur qui
manque d'historique vaut NaN. Les sommes glissantes passent par des sommes cumulees : elles supposent des series
sans NaN, et les tests d'egalite a zero qu'elles ne garantissent pas passent par des comptes exacts.

Les barres d'une echelle forment un dictionnaire de tenseurs : ouverture, haut, bas, cloture, volume.
"""
import math

import torch

NAN = math.nan
REF = 10  # barres de la volatilite R des motifs de bougies, comme dans les regles du moteur


def avant(x: torch.Tensor, k: int) -> torch.Tensor:
    """x[t - k] a la place t, NaN tant que t < k."""
    if k <= 0:
        return x
    decale = torch.full_like(x, NAN)
    decale[k:] = x[:-k]
    return decale


def depuis(x: torch.Tensor, n: int) -> torch.Tensor:
    """x, NaN aux n premieres places : la ou l'historique ne suffit pas."""
    x = x.clone()
    x[:n] = NAN
    return x


def somme(x: torch.Tensor, n: int) -> torch.Tensor:
    """Somme des n dernieres valeurs, NaN tant que t < n - 1. x sans NaN."""
    cumul = torch.cat((torch.zeros(1, dtype=x.dtype), x.cumsum(0)))
    resultat = torch.full_like(x, NAN)
    resultat[n - 1:] = cumul[n:] - cumul[:-n]
    return resultat


def compte(masque: torch.Tensor, n: int) -> torch.Tensor:
    """Nombre de places vraies parmi les n dernieres : exact, en entiers."""
    cumul = torch.cat((torch.zeros(1, dtype=torch.int64), masque.long().cumsum(0)))
    resultat = torch.full(masque.shape, -1, dtype=torch.int64)
    resultat[n - 1:] = cumul[n:] - cumul[:-n]
    return resultat


def fenetres(x: torch.Tensor, n: int) -> torch.Tensor:
    """(T, n) : les n dernieres valeurs a chaque place, la plus ancienne d'abord ; NaN avant le debut."""
    return torch.cat((torch.full((n - 1,), NAN, dtype=x.dtype), x)).unfold(0, n, 1)


def plus_haut(x: torch.Tensor, n: int) -> torch.Tensor:
    return fenetres(x, n).amax(1)


def plus_bas(x: torch.Tensor, n: int) -> torch.Tensor:
    return fenetres(x, n).amin(1)


def etendue_vraie(b: dict) -> torch.Tensor:
    """Etendue vraie, de la cloture precedente aux extremes ; la premiere barre n'a que son etendue."""
    veille = torch.cat((b["cloture"][:1], b["cloture"][:-1]))
    return torch.maximum(b["haut"], veille) - torch.minimum(b["bas"], veille)


def volatilite(b: dict, n: int) -> torch.Tensor:
    """R : moyenne de l'etendue vraie des n dernieres barres, comme View.volatility du moteur, qui exige n + 1
    barres. 0 exactement si aucune n'a d'etendue.
    """
    tr = etendue_vraie(b)
    r = torch.where(compte(tr > 0, n) == 0, 0.0, somme(tr, n) / n)
    return depuis(r, n)


def corps(b: dict) -> torch.Tensor:
    return b["cloture"] - b["ouverture"]


def meche_haute(b: dict) -> torch.Tensor:
    return b["haut"] - torch.maximum(b["ouverture"], b["cloture"])


def meche_basse(b: dict) -> torch.Tensor:
    return torch.minimum(b["ouverture"], b["cloture"]) - b["bas"]


def decaler(b: dict, k: int) -> dict:
    """Les barres k places plus tot : la barre t - k a la place t."""
    return {cle: avant(serie, k) for cle, serie in b.items()}


def vote(direction: torch.Tensor, intensite: torch.Tensor, condition: torch.Tensor) -> torch.Tensor:
    """Signal d'une regle : sens x intensite quand la condition tient, 0 sinon (la regle s'abstient)."""
    return torch.where(condition, direction * intensite, 0.0)


def plafond(x: torch.Tensor) -> torch.Tensor:
    """min(1, x), NaN compris."""
    return torch.where(x > 1, 1.0, x)


def signe(x: torch.Tensor) -> torch.Tensor:
    return torch.sign(x)
