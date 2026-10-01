"""Catalogue : tous les modules du depot, reglages classiques, poids egaux. Declarations uniquement.

Sert a mesurer les regles (scripts/measure_rules.py) et a verifier la plomberie. Ce n'est pas une
strategie a juger : ses poids et seuils n'ont ete fixes par aucune conviction.
Fenetres pensees pour des barres d'une heure.
"""
from decimal import Decimal

from engine.hard_tier import HardTier
from engine.strategy import Strategy
from modules.aggregators.weighted_sum import WeightedSum
from modules.exits.break_even import BreakEven
from modules.exits.entry_reversal import EntryReversal
from modules.exits.progress_then_pullback import ProgressThenPullback
from modules.exits.risk_bedrock import RiskBedrock
from modules.exits.rule_exit import RuleExit
from modules.exits.stagnation import Stagnation
from modules.exits.time_exit import TimeExit
from modules.exits.trailing_stop import TrailingStop
from modules.exits.volatility_budget import VolatilityBudget
from modules.exits.volume_dry_up import VolumeDryUp
from modules.risk.choppiness import Choppiness
from modules.risk.cooldown import Cooldown
from modules.risk.cost_cover import CostCover
from modules.risk.daily_gain_lock import DailyGainLock
from modules.risk.daily_loss_limit import DailyLossLimit
from modules.risk.daily_trade_limit import DailyTradeLimit
from modules.risk.drawdown_limit import DrawdownLimit
from modules.risk.losing_streak import LosingStreak
from modules.risk.loss_cooldown import LossCooldown
from modules.risk.trend_filter import TrendFilter
from modules.risk.volatility_band import VolatilityBand
from modules.risk.volume_filter import VolumeFilter
from modules.rules.adx import Adx
from modules.rules.aroon import Aroon
from modules.rules.autocorrelation import Autocorrelation
from modules.rules.balance_of_power import BalanceOfPower
from modules.rules.bollinger_bands import BollingerBands
from modules.rules.candle_color import CandleColor
from modules.rules.candle_streak import CandleStreak
from modules.rules.cci import Cci
from modules.rules.chaikin_money_flow import ChaikinMoneyFlow
from modules.rules.dark_cloud_cover import DarkCloudCover
from modules.rules.day_of_month import DayOfMonth
from modules.rules.day_of_week import DayOfWeek
from modules.rules.directional_movement import DirectionalMovement
from modules.rules.doji import Doji
from modules.rules.donchian_breakout import DonchianBreakout
from modules.rules.dragonfly_doji import DragonflyDoji
from modules.rules.ease_of_movement import EaseOfMovement
from modules.rules.efficiency_ratio import EfficiencyRatio
from modules.rules.engulfing import Engulfing
from modules.rules.evening_star import EveningStar
from modules.rules.exponential_moving_average import ExponentialMovingAverage
from modules.rules.exponential_moving_average_cross import ExponentialMovingAverageCross
from modules.rules.force_index import ForceIndex
from modules.rules.fractal_breakout import FractalBreakout
from modules.rules.gravestone_doji import GravestoneDoji
from modules.rules.hammer import Hammer
from modules.rules.hanging_man import HangingMan
from modules.rules.harami import Harami
from modules.rules.heikin_ashi import HeikinAshi
from modules.rules.hour_of_day import HourOfDay
from modules.rules.ichimoku_cloud import IchimokuCloud
from modules.rules.inside_bar import InsideBar
from modules.rules.internal_bar_strength import InternalBarStrength
from modules.rules.inverted import Inverted
from modules.rules.inverted_hammer import InvertedHammer
from modules.rules.keltner_channel import KeltnerChannel
from modules.rules.linear_regression_slope import LinearRegressionSlope
from modules.rules.macd import Macd
from modules.rules.market_structure import MarketStructure
from modules.rules.marubozu import Marubozu
from modules.rules.momentum import Momentum
from modules.rules.money_flow_index import MoneyFlowIndex
from modules.rules.morning_star import MorningStar
from modules.rules.moving_average import MovingAverage
from modules.rules.moving_average_cross import MovingAverageCross
from modules.rules.narrow_range import NarrowRange
from modules.rules.on_balance_volume import OnBalanceVolume
from modules.rules.opening_range_breakout import OpeningRangeBreakout
from modules.rules.outside_bar import OutsideBar
from modules.rules.parabolic_sar import ParabolicSar
from modules.rules.piercing_line import PiercingLine
from modules.rules.pivot_point import PivotPoint
from modules.rules.previous_day_range import PreviousDayRange
from modules.rules.rsi import Rsi
from modules.rules.session_move import SessionMove
from modules.rules.session_open import SessionOpen
from modules.rules.shooting_star import ShootingStar
from modules.rules.spinning_top import SpinningTop
from modules.rules.squeeze import Squeeze
from modules.rules.stochastic import Stochastic
from modules.rules.stochastic_rsi import StochasticRsi
from modules.rules.supertrend import Supertrend
from modules.rules.three_black_crows import ThreeBlackCrows
from modules.rules.three_inside import ThreeInside
from modules.rules.three_methods import ThreeMethods
from modules.rules.three_outside import ThreeOutside
from modules.rules.three_white_soldiers import ThreeWhiteSoldiers
from modules.rules.tweezer import Tweezer
from modules.rules.ultimate_oscillator import UltimateOscillator
from modules.rules.volatility_breakout import VolatilityBreakout
from modules.rules.volume_surge import VolumeSurge
from modules.rules.vortex import Vortex
from modules.rules.vwap import Vwap
from modules.sizing.fixed_risk import FixedRisk


def build(patience: Decimal = Decimal("1")) -> Strategy:
    one = Decimal("1")
    budget = VolatilityBudget(
        stop_vol=Decimal("2"),
        target_ratio=Decimal("2"),
        max_hold_bars=48,
        patience=patience,
        vol_period=14,
    )
    bedrock = RiskBedrock(budget)
    rules = (
        # Bougies
        CandleColor(one, offset=1),
        CandleColor(one, offset=2),
        CandleStreak(one, length=3),
        Doji(one),
        DragonflyDoji(one),
        GravestoneDoji(one),
        Hammer(one),
        HangingMan(one),
        InvertedHammer(one),
        ShootingStar(one),
        Marubozu(one),
        SpinningTop(one),
        Engulfing(one),
        Harami(one),
        PiercingLine(one),
        DarkCloudCover(one),
        Tweezer(one),
        InsideBar(one),
        OutsideBar(one),
        MorningStar(one),
        EveningStar(one),
        ThreeWhiteSoldiers(one),
        ThreeBlackCrows(one),
        ThreeInside(one),
        ThreeOutside(one),
        ThreeMethods(one),
        HeikinAshi(one),
        # Seances et calendrier
        SessionOpen(one, hour=0, minute=0, window=25),
        SessionOpen(one, hour=13, minute=30, window=25),
        SessionMove(one, hour=0, minute=0, window=25),
        OpeningRangeBreakout(one, hour=0, minute=0, length=1, window=25),
        OpeningRangeBreakout(one, hour=13, minute=30, length=1, window=25),
        PreviousDayRange(one, window=48),
        PivotPoint(one, window=48),
        HourOfDay(one, start=21, end=23, direction=1),
        DayOfWeek(one, days=(0,), direction=1),
        DayOfMonth(one, days=(-1, 1, 2, 3), direction=1),
        # Tendance et momentum
        Momentum(one, lookback=24),
        MovingAverage(one, period=48),
        MovingAverageCross(one, fast=20, slow=50),
        ExponentialMovingAverage(one, period=48),
        ExponentialMovingAverageCross(one, fast=20, slow=50),
        Macd(one, fast=12, slow=26, signal=9),
        LinearRegressionSlope(one, period=24),
        DirectionalMovement(one, period=14),
        Adx(one, period=14, threshold=Decimal("25")),
        Vortex(one, period=14),
        Aroon(one, period=25),
        Cci(one, period=20),
        IchimokuCloud(one, tenkan=9, kijun=26, senkou=52),
        Supertrend(one, period=10, multiplier=Decimal("3")),
        ParabolicSar(one, step=Decimal("0.02"), maximum=Decimal("0.2")),
        EfficiencyRatio(one, period=10, threshold=Decimal("0.3")),
        Autocorrelation(one, period=24),
        MarketStructure(one, length=3),
        DonchianBreakout(one, period=20),
        FractalBreakout(one, window=20),
        NarrowRange(one, length=7),
        Squeeze(one, period=20, bollinger=Decimal("2"), keltner=Decimal("1.5")),
        VolatilityBreakout(one, k=Decimal("0.5")),
        # Retour a la moyenne
        Rsi(one, period=14, lower=Decimal("30"), upper=Decimal("70")),
        StochasticRsi(one, rsi_period=14, period=14, lower=Decimal("20"), upper=Decimal("80")),
        Stochastic(one, period=14, lower=Decimal("20"), upper=Decimal("80")),
        UltimateOscillator(one, short=7, medium=14, long=28, lower=Decimal("30"), upper=Decimal("70")),
        InternalBarStrength(one, lower=Decimal("0.2"), upper=Decimal("0.8")),
        BollingerBands(one, period=20, width=Decimal("2")),
        Inverted(BollingerBands(one, period=20, width=Decimal("2"))),
        KeltnerChannel(one, period=20, width=Decimal("2")),
        # Volume
        VolumeSurge(one, period=20, ratio=Decimal("2")),
        OnBalanceVolume(one, period=20),
        ForceIndex(one, period=13),
        MoneyFlowIndex(one, period=14, lower=Decimal("20"), upper=Decimal("80")),
        ChaikinMoneyFlow(one, period=20),
        EaseOfMovement(one, period=14),
        BalanceOfPower(one, period=14),
        Vwap(one, period=24),
    )
    aggregator = WeightedSum(threshold=Decimal("0.30"), quorum=Decimal("0.2"))
    return Strategy(
        rules=rules,
        aggregator=aggregator,
        risk=(
            Cooldown(hours=2),
            LossCooldown(hours=4),
            VolatilityBand(period=14, minimum=Decimal("0.002"), maximum=Decimal("0.05")),
            Choppiness(period=14, maximum=Decimal("61.8")),
            TrendFilter(period=200),
            VolumeFilter(period=20, minimum=Decimal("0.5")),
            CostCover(bedrock, cost=Decimal("0.003"), multiple=Decimal("2")),
            DailyLossLimit(limit=Decimal("0.02")),
            DailyGainLock(limit=Decimal("0.03")),
            DailyTradeLimit(count=4),
            LosingStreak(length=3, factor=Decimal("0.5")),
            DrawdownLimit(limit=Decimal("0.1"), factor=Decimal("0.5")),
        ),
        sizer=FixedRisk(budget, fraction=Decimal("0.01")),
        bedrock=bedrock,
        hard=HardTier(
            TrailingStop(distance=Decimal("3"), period=14),
            ProgressThenPullback(advances=3, pullback=Decimal("0.01")),
            BreakEven(trigger=Decimal("1")),
            Stagnation(bars=24, progress=Decimal("0.5")),
            VolumeDryUp(length=3, period=20, ratio=Decimal("0.5")),
            RuleExit(Macd(one, fast=12, slow=26, signal=9)),
            EntryReversal(rules, aggregator),
            TimeExit(budget),
        ),
    )
