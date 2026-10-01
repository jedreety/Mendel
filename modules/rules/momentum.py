from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Momentum(Rule):
    """Sens de la variation de cloture sur `lookback` barres.

    Intensite : variation en unites de volatilite, ramenee a l'horizon par racine de lookback, plafonnee a 1.
    """

    def __init__(self, weight: Decimal, lookback: int):
        self.name = f"Momentum({lookback})"
        self.weight = weight
        self.warmup = lookback + 1
        self.lookback = lookback

    def vote(self, view: View) -> Vote | None:
        change = view.bars[-1].close - view.bars[-1 - self.lookback].close
        if change == 0:
            return Vote(0, Decimal(0))
        scale = view.volatility(self.lookback) * Decimal(self.lookback).sqrt()
        return Vote(1 if change > 0 else -1, min(Decimal(1), abs(change) / scale))
