from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from engine.domain import Bar, Caps, Execution, Portfolio, Position, Trade


class Ledger:
    """Grand livre : tresorerie, position, trades clos et frais, en decimal exact."""

    def __init__(self, cash: Decimal):
        self.initial = cash
        self.cash = cash
        self.position: Position | None = None
        self.last_exit: datetime | None = None
        self.trades: tuple[Trade, ...] = ()

    def apply(self, fill: Execution) -> None:
        if fill.side == "buy":
            self.cash -= fill.quantity * fill.price + fill.fee
            self.position = Position(fill.quantity, fill.price, fill.time, fill.fee, 0, None, fill.price, 0)
            return
        entry = self.position
        self.cash += fill.quantity * fill.price - fill.fee
        fees = entry.entry_fee + fill.fee
        net = (fill.price - entry.entry_price) * fill.quantity - fees
        self.trades += (
            Trade(entry.entry_time, fill.time, fill.quantity, entry.entry_price, fill.price, fees, net, fill.reason),
        )
        self.position = None
        self.last_exit = fill.time

    def age(self, bar: Bar) -> None:
        """Une barre close de plus pour la position ouverte : duree et extreme favorable."""
        position = self.position
        if position is None:
            return
        advance = 1 if bar.high > position.peak else 0
        self.position = replace(
            position,
            bars_held=position.bars_held + 1,
            peak=max(position.peak, bar.high),
            advances=position.advances + advance,
        )

    def protect(self, caps: Caps) -> None:
        self.position = replace(self.position, caps=caps)

    def portfolio(self) -> Portfolio:
        return Portfolio(self.cash, self.position, self.last_exit, self.trades)
