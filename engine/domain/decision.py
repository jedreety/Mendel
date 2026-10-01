from dataclasses import dataclass
from decimal import Decimal

from engine.domain.ballot import Ballot
from engine.domain.caps import Caps
from engine.domain.risk_verdict import RiskVerdict
from engine.domain.tally import Tally


@dataclass(frozen=True)
class Decision:
    """Ce que renvoie Policy.decide, ecrit tel quel au journal, y compris quand rien n'est fait.

    action : "open", "close", "protect" (position gardee, caps a jour) ou "none".
    reason : pourquoi, y compris la raison de l'inaction.
    """

    action: str
    reason: str
    quantity: Decimal = Decimal(0)
    caps: Caps | None = None
    ballots: tuple[Ballot, ...] = ()
    tally: Tally | None = None
    risk: tuple[RiskVerdict, ...] = ()
