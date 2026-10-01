from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class HeikinAshi(Rule):
    """Couleur de la derniere bougie Heikin-Ashi : verte +1, rouge -1, sans corps 0.

    Cloture HA : moyenne de l'ouverture, du plus haut, du plus bas et de la cloture. Ouverture HA : milieu du
    corps HA precedent. La serie part d'une fenetre fixe de 10 barres, amorcee au milieu du corps de la premiere :
    le vote ne depend pas de la taille de la vue, et l'amorce n'y pese plus que 1/512.
    Intensite : part du corps HA dans l'amplitude HA.
    """

    WINDOW = 10

    def __init__(self, weight: Decimal):
        self.name = "HeikinAshi"
        self.weight = weight
        self.warmup = self.WINDOW

    def vote(self, view: View) -> Vote | None:
        first, *rest = view.bars[-self.WINDOW:]
        ha_open = (first.open + first.close) / 2
        ha_close = (first.open + first.high + first.low + first.close) / 4
        for bar in rest:
            ha_open = (ha_open + ha_close) / 2
            ha_close = (bar.open + bar.high + bar.low + bar.close) / 4
        body = ha_close - ha_open
        if body == 0:
            return Vote(0, Decimal(0))
        bar = view.bars[-1]
        span = max(bar.high, ha_open) - min(bar.low, ha_open)
        return Vote(1 if body > 0 else -1, abs(body) / span)
