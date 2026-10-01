from decimal import Decimal

from engine.base import Broker
from engine.domain import Bar, Caps, Execution, Order, Venue


class SimBroker(Broker):
    """Courtier simule, hypotheses defavorables.

    Un ordre au marche est rempli a la cloture de la barre de decision, glissement defavorable compris.
    Les ordres de protection sont testes sur les barres suivantes, contre le plus bas et le plus haut.
    Si les deux caps sont dans la meme barre, le cap negatif est retenu. Un stop franchi en ouverture
    est rempli a l'ouverture. Frais au taux du lieu a chaque execution.
    """

    def __init__(self, venue: Venue):
        self.venue = venue
        self.bar: Bar | None = None
        self.protection: tuple[str, Decimal, Caps] | None = None

    def on_bar(self, bar: Bar) -> list[Execution]:
        self.bar = bar
        if self.protection is None:
            return []
        order_id, quantity, caps = self.protection
        if bar.low <= caps.stop:
            price, reason = min(caps.stop, bar.open), "socle:stop"
        elif bar.high >= caps.target:
            price, reason = caps.target, "socle:target"
        else:
            return []
        self.protection = None
        return [self._fill(order_id, "sell", quantity, price, reason)]

    def submit(self, order: Order) -> Execution:
        return self._fill(order.id, order.side, order.quantity, self.bar.close, order.reason)

    def protect(self, order_id: str, quantity: Decimal, caps: Caps) -> None:
        self.protection = (order_id, quantity, caps)

    def unprotect(self) -> None:
        self.protection = None

    def _fill(self, order_id: str, side: str, quantity: Decimal, price: Decimal, reason: str) -> Execution:
        price = self.venue.fill_price(price, side)
        fee = quantity * price * self.venue.fee_rate
        return Execution(order_id, self.bar.time, side, quantity, price, fee, reason)
