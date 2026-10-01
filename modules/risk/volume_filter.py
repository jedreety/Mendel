from decimal import Decimal

from engine.base import RiskRule
from engine.domain import Portfolio, RiskVerdict, View


class VolumeFilter(RiskRule):
    """Refuse l'entree quand le volume de la derniere barre est nul, ou inferieur a `minimum` fois la moyenne
    des `period` barres precedentes : sans liquidite, le glissement modelise n'est plus credible.
    """

    def __init__(self, period: int, minimum: Decimal):
        self.name = f"VolumeFilter({period},{minimum})"
        self.warmup = period + 1
        self.period = period
        self.minimum = minimum

    def check(self, view: View, portfolio: Portfolio) -> RiskVerdict:
        volume = view.bars[-1].volume
        average = sum((bar.volume for bar in view.bars[-self.period - 1:-1]), Decimal(0)) / self.period
        if volume == 0 or volume < self.minimum * average:
            return RiskVerdict(self.name, Decimal(0), "volume trop faible")
        return RiskVerdict(self.name, Decimal(1), "volume suffisant")
