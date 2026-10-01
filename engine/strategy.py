from dataclasses import dataclass

from engine.base import Aggregator, Bedrock, RiskRule, Rule, Sizer
from engine.hard_tier import HardTier


@dataclass(frozen=True)
class Strategy:
    """Ce que renvoie un fichier de input/.

    Le socle est un champ a part : il ne peut ni etre retire, ni etre range parmi les constats.
    """

    rules: tuple[Rule, ...]
    aggregator: Aggregator
    risk: tuple[RiskRule, ...]
    sizer: Sizer
    bedrock: Bedrock
    hard: HardTier
