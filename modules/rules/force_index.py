from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class ForceIndex(Rule):
    """Force Index d'Elder sur `period` barres, variante sans moyenne exponentielle : somme des variations de
    cloture multipliees par le volume. Vote le signe, 0 a l'equilibre, s'abstient sans volume.

    Proche d'OnBalanceVolume, qui ne compte que le signe de la variation ; ici son ampleur pese aussi.
    Intensite : somme signee rapportee a la somme des valeurs absolues, entre 0 et 1.
    """

    def __init__(self, weight: Decimal, period: int):
        self.name = f"ForceIndex({period})"
        self.weight = weight
        self.warmup = period + 1
        self.period = period

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.period - 1:]
        if all(bar.volume == 0 for bar in bars[1:]):
            return None
        forces = [(bar.close - prev.close) * bar.volume for prev, bar in zip(bars, bars[1:])]
        total = sum(forces, Decimal(0))
        if total == 0:
            return Vote(0, Decimal(0))
        return Vote(1 if total > 0 else -1, abs(total) / sum((abs(force) for force in forces), Decimal(0)))
