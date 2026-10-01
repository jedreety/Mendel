from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskVerdict:
    """Verdict d'une regle de risque. factor : 0 refuse, entre 0 et 1 reduit, 1 laisse passer."""

    name: str
    factor: Decimal
    reason: str
