from collections import deque
from dataclasses import asdict, replace

from engine.base import Broker
from engine.domain import Bar, Decision, Execution, Order, Portfolio, View
from engine.journal import Journal
from engine.ledger import Ledger
from engine.policy import Policy


def _journaled(portfolio: Portfolio) -> dict:
    """Portefeuille tel qu'ecrit au journal, sans l'historique des trades : chaque trade y figure deja
    par ses executions, et le recopier a chaque barre ferait croitre le journal au carre.
    """
    state = asdict(replace(portfolio, trades=()))
    del state["trades"]
    return state


class Pipeline:
    """Passe par barre close, ecrite une fois pour le backtest et le temps reel.

    C'est la couche d'execution : la seule qui parle au courtier.
    """

    def __init__(self, name: str, symbol: str, policy: Policy, broker: Broker, ledger: Ledger, journal: Journal):
        self.name = name
        self.symbol = symbol
        self.policy = policy
        self.broker = broker
        self.ledger = ledger
        self.journal = journal
        self.bars: deque[Bar] = deque(maxlen=policy.lookback)

    def on_bar(self, bar: Bar) -> None:
        fills = self.broker.on_bar(bar)
        for fill in fills:
            self.ledger.apply(fill)
        self.ledger.age(bar)
        self.bars.append(bar)
        portfolio = self.ledger.portfolio()
        decision = self.policy.decide(View(self.symbol, tuple(self.bars)), portfolio)
        fills += self._execute(decision, bar)
        self.journal.write({
            "time": bar.time,
            "symbol": self.symbol,
            "portfolio": _journaled(portfolio),
            "decision": asdict(decision),
            "fills": [asdict(fill) for fill in fills],
        })

    def liquidate(self, reason: str) -> None:
        """Ferme la position restante au dernier cours connu, par exemple en fin de donnees."""
        if self.ledger.position is None:
            return
        portfolio = self.ledger.portfolio()
        fill = self._close(self.bars[-1], reason)
        self.journal.write({
            "time": fill.time,
            "symbol": self.symbol,
            "portfolio": _journaled(portfolio),
            "decision": None,
            "fills": [asdict(fill)],
        })

    def _execute(self, decision: Decision, bar: Bar) -> list[Execution]:
        if decision.action == "open":
            order = Order(self._order_id(bar, "open"), "buy", decision.quantity, decision.reason)
            fill = self.broker.submit(order)
            self.ledger.apply(fill)
            self.broker.protect(order.id, fill.quantity, decision.caps)  # dans la foulee de l'ouverture
            self.ledger.protect(decision.caps)
            return [fill]
        if decision.action == "protect":
            self.broker.protect(self._order_id(bar, "protect"), self.ledger.position.quantity, decision.caps)
            self.ledger.protect(decision.caps)
            return []
        if decision.action == "close":
            return [self._close(bar, decision.reason)]
        return []

    def _close(self, bar: Bar, reason: str) -> Execution:
        self.broker.unprotect()
        fill = self.broker.submit(Order(self._order_id(bar, "close"), "sell", self.ledger.position.quantity, reason))
        self.ledger.apply(fill)
        return fill

    def _order_id(self, bar: Bar, intent: str) -> str:
        """Deterministe : strategie, symbole, horodatage de la barre et intention."""
        return f"{self.name}-{self.symbol}-{bar.time:%Y%m%dT%H%M%S}-{intent}"
