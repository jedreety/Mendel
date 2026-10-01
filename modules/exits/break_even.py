from decimal import Decimal

from engine.base import ExitModule
from engine.domain import Position, View, Vote


class BreakEven(ExitModule):
    """Constat : une fois que le plus haut depuis l'entree a progresse d'au moins `trigger` fois
    la distance de stop, ferme si la cloture revient au point mort.

    Distance de stop : prix d'entree moins cap negatif en vigueur, tel que le budget l'a calcule.
    Point mort : prix d'entree plus deux fois les frais d'entree par unite ; les frais de sortie sont supposes
    egaux a ceux d'entree, le glissement n'est pas compte.
    Evalue a la cloture ; le socle reste le seul stop intrabar.
    """

    def __init__(self, trigger: Decimal):
        self.name = f"BreakEven({trigger})"
        self.warmup = 1
        self.trigger = trigger

    def vote(self, view: View, position: Position) -> Vote | None:
        distance = position.entry_price - position.caps.stop
        breakeven = position.entry_price + 2 * position.entry_fee / position.quantity
        if position.peak - position.entry_price >= self.trigger * distance and view.bars[-1].close <= breakeven:
            return Vote(1, Decimal(1))
        return None
