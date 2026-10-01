from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class InternalBarStrength(Rule):
    """Position de la cloture dans l'amplitude de la derniere barre, (cloture - plus bas) / amplitude, lue en
    retour a la moyenne : sous `lower` +1, au-dessus de `upper` -1, entre les deux s'abstient.
    Sans amplitude, s'abstient.

    Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou 1.
    """

    def __init__(self, weight: Decimal, lower: Decimal, upper: Decimal):
        self.name = f"InternalBarStrength({lower},{upper})"
        self.weight = weight
        self.warmup = 1
        self.lower = lower
        self.upper = upper

    def vote(self, view: View) -> Vote | None:
        bar = view.bars[-1]
        if bar.range == 0:
            return None
        strength = (bar.close - bar.low) / bar.range
        if strength < self.lower:
            return Vote(1, (self.lower - strength) / self.lower)
        if strength > self.upper:
            return Vote(-1, (strength - self.upper) / (1 - self.upper))
        return None
