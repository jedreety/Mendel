from decimal import ROUND_DOWN, Decimal
from functools import partial

from engine.domain import Ballot, Decision, Portfolio, Position, Venue, View
from engine.strategy import Strategy


class Policy:
    """Fonction de decision pure : vue figee et portefeuille en entree, decision en sortie.

    Aucune entree/sortie, aucune horloge, aucun etat cache. La sortie passe avant l'entree.
    """

    def __init__(self, strategy: Strategy, venue: Venue):
        self.strategy = strategy
        self.venue = venue
        self.warmup = max(strategy.bedrock.warmup, strategy.sizer.warmup, *(rule.warmup for rule in strategy.risk))
        self.lookback = max(
            self.warmup,
            *(rule.warmup for rule in strategy.rules),
            *(module.warmup for module in strategy.hard.modules),
        )

    def decide(self, view: View, portfolio: Portfolio) -> Decision:
        if portfolio.position is not None:
            return self._exit(view, portfolio.position)
        if portfolio.last_exit == view.bars[-1].time:
            return Decision("none", "sortie sur cette barre")  # une sortie consomme la barre
        return self._entry(view, portfolio)

    def _exit(self, view: View, position: Position) -> Decision:
        hit = self.strategy.bedrock.check(view, position)
        if hit is not None:
            return Decision("close", f"socle:{hit}")
        hit = self.strategy.hard.first(view, position)
        if hit is not None:
            return Decision("close", f"constats:{hit}")
        return Decision("protect", "position conservee", caps=self.strategy.bedrock.caps(view, position.entry_price))

    def _entry(self, view: View, portfolio: Portfolio) -> Decision:
        strategy = self.strategy
        ballots = tuple(
            Ballot(rule.name, rule.weight, rule.vote(view) if len(view.bars) >= rule.warmup else None)
            for rule in strategy.rules
        )
        tally = strategy.aggregator.tally(ballots)
        record = partial(Decision, ballots=ballots, tally=tally)
        if tally.direction == 0:
            return record("none", tally.reason)
        if tally.direction < 0:
            return record("none", "vente a decouvert impossible au comptant")
        if len(view.bars) < self.warmup:
            return record("none", "socle en chauffe")

        verdicts = []
        factor = Decimal(1)
        for rule in strategy.risk:
            verdict = rule.check(view, portfolio)
            verdicts.append(verdict)
            factor *= verdict.factor
            if verdict.factor == 0:
                return record("none", f"risque:{verdict.name}", risk=tuple(verdicts))

        venue = self.venue
        price = venue.fill_price(view.bars[-1].close, "buy")
        wanted = strategy.sizer.size(view, portfolio, price, tally) * factor
        affordable = portfolio.cash / (price * (1 + venue.fee_rate))
        quantity = (min(wanted, affordable) / venue.qty_step).to_integral_value(rounding=ROUND_DOWN) * venue.qty_step
        if quantity * price < venue.min_notional:
            return record("none", "notionnel sous le minimum", risk=tuple(verdicts))
        caps = strategy.bedrock.caps(view, price)
        return record("open", tally.reason, quantity=quantity, caps=caps, risk=tuple(verdicts))
