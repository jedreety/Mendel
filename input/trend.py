"""Strategie de tendance. Declarations uniquement.

Regles, poids et reglages sont des valeurs de depart. Ils se fixent avant le premier backtest
honnete, pas apres.
"""
from decimal import Decimal

from engine.hard_tier import HardTier
from engine.strategy import Strategy
from modules.aggregators.weighted_sum import WeightedSum
from modules.exits.risk_bedrock import RiskBedrock
from modules.exits.time_exit import TimeExit
from modules.exits.volatility_budget import VolatilityBudget
from modules.rules.momentum import Momentum
from modules.rules.moving_average import MovingAverage
from modules.sizing.fixed_risk import FixedRisk


def build(patience: Decimal = Decimal("1")) -> Strategy:
    budget = VolatilityBudget(
        stop_vol=Decimal("2"),
        target_ratio=Decimal("2"),
        max_hold_bars=48,
        patience=patience,
        vol_period=14,
    )
    return Strategy(
        rules=(
            Momentum(weight=Decimal("1"), lookback=24),
            MovingAverage(weight=Decimal("1"), period=48),
        ),
        aggregator=WeightedSum(threshold=Decimal("0.30"), quorum=Decimal("0.5")),
        risk=(),
        sizer=FixedRisk(budget, fraction=Decimal("0.01")),
        bedrock=RiskBedrock(budget),
        hard=HardTier(TimeExit(budget)),
    )
