from decimal import Decimal

from engine.base import ExitModule
from engine.domain import Position, View, Vote


class Stagnation(ExitModule):
    """Constat : apres `bars` barres de detention, ferme si le plus haut depuis l'entree n'a pas
    progresse d'au moins `progress` fois la distance de stop. L'idee ne s'est pas realisee : inutile
    d'attendre la duree maximale.

    Distance de stop : prix d'entree moins cap negatif en vigueur, tel que le budget l'a calcule.
    """

    def __init__(self, bars: int, progress: Decimal):
        self.name = f"Stagnation({bars},{progress})"
        self.warmup = 1
        self.bars = bars
        self.progress = progress

    def vote(self, view: View, position: Position) -> Vote | None:
        distance = position.entry_price - position.caps.stop
        if position.bars_held >= self.bars and position.peak - position.entry_price < self.progress * distance:
            return Vote(1, Decimal(1))
        return None
