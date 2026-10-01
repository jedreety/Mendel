"""Chaque regle portee face a la regle du moteur, avec les reglages du catalogue (input/catalog.py).

Sert au verificateur (python -m evolution.verifier) : sur des barres horaires tirees au hasard, le signal du module
doit redonner le vote de la regle, sens x intensite, 0 quand elle s'abstient, 1 pour un motif present dont la regle
vote 0. Deux regles portees s'en ecartent a dessein : leurs moyennes exponentielles portent sur tout l'historique,
et non sur la fenetre courte du moteur.
"""
import random
from datetime import timedelta
from decimal import Decimal

import torch

from engine.domain.bar import Bar
from engine.domain.view import View
from evolution.data import Historique
from evolution.modules.regles import REGLES
from evolution.modules.regles.day_of_month import JOURS
from evolution.modules.regles.parabolic_sar import MAXIMUMS, PAS
from evolution.modules.regles.supertrend import MULTIPLICATEURS
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

UN, D = Decimal(1), Decimal
PRESENCE = {"regle_doji", "regle_spinning_top", "regle_inside_bar"}  # la regle vote 0 : le signal est la presence
APPROCHEES = {"regle_exponential_moving_average_cross", "regle_macd"}  # moyennes sur tout l'historique
TOLERANCE = 0.01  # ecart admis, arrondis des tables a 8 bits compris
HISTORIQUE = 700  # barres passees a chaque regle : plus que la plus longue de leurs fenetres

# Pour chaque module, la regle du moteur et les genes qui lui correspondent (l'echelle est l'heure).
CAS = {
    "regle_candle_color": [(CandleColor(UN, offset=1), {"decalage": 1}), (CandleColor(UN, offset=2), {"decalage": 2})],
    "regle_candle_streak": [(CandleStreak(UN, length=3), {"longueur": 3})],
    "regle_doji": [(Doji(UN), {})],
    "regle_dragonfly_doji": [(DragonflyDoji(UN), {})],
    "regle_gravestone_doji": [(GravestoneDoji(UN), {})],
    "regle_hammer": [(Hammer(UN), {})],
    "regle_hanging_man": [(HangingMan(UN), {})],
    "regle_inverted_hammer": [(InvertedHammer(UN), {})],
    "regle_shooting_star": [(ShootingStar(UN), {})],
    "regle_marubozu": [(Marubozu(UN), {})],
    "regle_spinning_top": [(SpinningTop(UN), {})],
    "regle_engulfing": [(Engulfing(UN), {})],
    "regle_harami": [(Harami(UN), {})],
    "regle_piercing_line": [(PiercingLine(UN), {})],
    "regle_dark_cloud_cover": [(DarkCloudCover(UN), {})],
    "regle_tweezer": [(Tweezer(UN), {})],
    "regle_inside_bar": [(InsideBar(UN), {})],
    "regle_outside_bar": [(OutsideBar(UN), {})],
    "regle_morning_star": [(MorningStar(UN), {})],
    "regle_evening_star": [(EveningStar(UN), {})],
    "regle_three_white_soldiers": [(ThreeWhiteSoldiers(UN), {})],
    "regle_three_black_crows": [(ThreeBlackCrows(UN), {})],
    "regle_three_inside": [(ThreeInside(UN), {})],
    "regle_three_outside": [(ThreeOutside(UN), {})],
    "regle_three_methods": [(ThreeMethods(UN), {})],
    "regle_heikin_ashi": [(HeikinAshi(UN), {})],
    "regle_session_open": [(SessionOpen(UN, hour=0, minute=0, window=25), {"heure": 0}),
                           (SessionOpen(UN, hour=13, minute=0, window=25), {"heure": 13})],
    "regle_session_move": [(SessionMove(UN, hour=0, minute=0, window=25), {"heure": 0}),
                           (SessionMove(UN, hour=13, minute=0, window=25), {"heure": 13})],
    "regle_opening_range_breakout": [
        (OpeningRangeBreakout(UN, hour=0, minute=0, length=1, window=25), {"heure": 0, "longueur": 1}),
        (OpeningRangeBreakout(UN, hour=13, minute=0, length=3, window=25), {"heure": 13, "longueur": 3})],
    "regle_previous_day_range": [(PreviousDayRange(UN, window=48), {})],
    "regle_pivot_point": [(PivotPoint(UN, window=48), {})],
    "regle_hour_of_day": [(HourOfDay(UN, start=21, end=23, direction=1), {"debut": 21, "fin": 23}),
                          (HourOfDay(UN, start=22, end=2, direction=1), {"debut": 22, "fin": 2})],
    "regle_day_of_week": [(DayOfWeek(UN, days=(0,), direction=1), {"jour": 0})],
    "regle_day_of_month": [(DayOfMonth(UN, days=(1,), direction=1), {"jour": JOURS.index(1)}),
                           (DayOfMonth(UN, days=(-1,), direction=1), {"jour": JOURS.index(-1)})],
    "regle_momentum": [(Momentum(UN, lookback=24), {"n": 24})],
    "regle_moving_average": [(MovingAverage(UN, period=48), {"n": 48})],
    "regle_moving_average_cross": [(MovingAverageCross(UN, fast=20, slow=50), {"rapide": 20, "lente": 50})],
    "regle_exponential_moving_average": [(ExponentialMovingAverage(UN, period=48), {"n": 48})],
    "regle_exponential_moving_average_cross": [(ExponentialMovingAverageCross(UN, fast=20, slow=50),
                                                {"rapide": 20, "lente": 50})],
    "regle_macd": [(Macd(UN, fast=12, slow=26, signal=9), {"rapide": 12, "lente": 26, "signal": 9})],
    "regle_linear_regression_slope": [(LinearRegressionSlope(UN, period=24), {"n": 24})],
    "regle_directional_movement": [(DirectionalMovement(UN, period=14), {"n": 14})],
    "regle_adx": [(Adx(UN, period=14, threshold=D("25")), {"n": 14, "seuil": 25.0})],
    "regle_vortex": [(Vortex(UN, period=14), {"n": 14})],
    "regle_aroon": [(Aroon(UN, period=25), {"n": 25})],
    "regle_cci": [(Cci(UN, period=20), {"n": 20})],
    "regle_ichimoku_cloud": [(IchimokuCloud(UN, tenkan=9, kijun=26, senkou=52), {"tenkan": 9, "kijun": 26, "senkou": 52})],
    "regle_supertrend": [(Supertrend(UN, period=10, multiplier=D("3")),
                          {"periode": 10, "multiplicateur": MULTIPLICATEURS.index(3.0)})],
    "regle_parabolic_sar": [(ParabolicSar(UN, step=D("0.02"), maximum=D("0.2")),
                             {"pas": PAS.index(0.02), "maximum": MAXIMUMS.index(0.2)})],
    "regle_efficiency_ratio": [(EfficiencyRatio(UN, period=10, threshold=D("0.3")), {"n": 10, "seuil": 0.3})],
    "regle_autocorrelation": [(Autocorrelation(UN, period=24), {"n": 24})],
    "regle_market_structure": [(MarketStructure(UN, length=3), {"longueur": 3})],
    "regle_donchian_breakout": [(DonchianBreakout(UN, period=20), {"n": 20})],
    "regle_fractal_breakout": [(FractalBreakout(UN, window=20), {"fenetre": 20})],
    "regle_narrow_range": [(NarrowRange(UN, length=7), {"longueur": 7})],
    "regle_squeeze": [(Squeeze(UN, period=20, bollinger=D("2"), keltner=D("1.5")),
                       {"n": 20, "bollinger": 2.0, "keltner": 1.5})],
    "regle_volatility_breakout": [(VolatilityBreakout(UN, k=D("0.5")), {"k": 0.5})],
    "regle_rsi": [(Rsi(UN, period=14, lower=D("30"), upper=D("70")), {"n": 14, "bas": 30.0, "haut": 70.0})],
    "regle_stochastic_rsi": [(StochasticRsi(UN, rsi_period=14, period=14, lower=D("20"), upper=D("80")),
                              {"periode_rsi": 14, "periode": 14, "bas": 20.0, "haut": 80.0})],
    "regle_stochastic": [(Stochastic(UN, period=14, lower=D("20"), upper=D("80")), {"n": 14, "bas": 20.0, "haut": 80.0})],
    "regle_ultimate_oscillator": [(UltimateOscillator(UN, short=7, medium=14, long=28, lower=D("30"), upper=D("70")),
                                   {"court": 7, "moyen": 14, "long": 28, "bas": 30.0, "haut": 70.0})],
    "regle_internal_bar_strength": [(InternalBarStrength(UN, lower=D("0.2"), upper=D("0.8")), {"bas": 0.2, "haut": 0.8})],
    "regle_bollinger_bands": [(BollingerBands(UN, period=20, width=D("2")), {"n": 20, "largeur": 2.0})],
    "regle_keltner_channel": [(KeltnerChannel(UN, period=20, width=D("2")), {"n": 20, "largeur": 2.0})],
    "regle_volume_surge": [(VolumeSurge(UN, period=20, ratio=D("2")), {"n": 20, "ratio": 2.0})],
    "regle_on_balance_volume": [(OnBalanceVolume(UN, period=20), {"n": 20})],
    "regle_force_index": [(ForceIndex(UN, period=13), {"n": 13})],
    "regle_money_flow_index": [(MoneyFlowIndex(UN, period=14, lower=D("20"), upper=D("80")),
                                {"n": 14, "bas": 20.0, "haut": 80.0})],
    "regle_chaikin_money_flow": [(ChaikinMoneyFlow(UN, period=20), {"n": 20})],
    "regle_ease_of_movement": [(EaseOfMovement(UN, period=14), {"n": 14})],
    "regle_balance_of_power": [(BalanceOfPower(UN, period=14), {"n": 14})],
    "regle_vwap": [(Vwap(UN, period=24), {"n": 24})],
}


def barres(hist: Historique) -> list[Bar]:
    """Les barres horaires de l'historique, comme le moteur les voit : decimaux, instant de cloture."""
    pas = hist.pas_de_prix
    return [Bar(hist.ouverture_de(i) + timedelta(hours=1), D(o) * pas, D(h) * pas, D(b) * pas, D(c) * pas, D(repr(v)))
            for i, (o, h, b, c, v) in enumerate(zip(hist.ouverture.tolist(), hist.haut.tolist(), hist.bas.tolist(),
                                                     hist.cloture.tolist(), hist.volume.tolist()))]


def comparer(hist: Historique, marche, echantillons: int, graine: int) -> list[tuple[str, str, float, int]]:
    """Pour chaque cas : module, regle, part des barres ou le signal redonne le vote, votes non nuls de la regle."""
    if set(CAS) != {module.NOM for module in REGLES}:
        raise ValueError("chaque regle portee doit avoir son cas, et lui seul")
    moteur = barres(hist)
    hasard = random.Random(graine)
    indices = sorted(hasard.randrange(HISTORIQUE, len(hist)) for _ in range(echantillons))
    i = torch.tensor(indices, device=marche.appareil)
    resultats = []
    for module in REGLES:
        tables = module.preparer(marche)
        for regle, genes in CAS[module.NOM]:
            g = {gene.nom: torch.tensor([0 if gene.nom == "echelle" else genes[gene.nom]], device=marche.appareil,
                                        dtype=torch.float32 if gene.type == "reel" else torch.int64)
                 for gene in module.GENES}
            signaux = torch.nan_to_num(module.signal(marche, tables, i, g, {}), nan=0.0).tolist()
            votes = []
            for k in indices:
                vote = regle.vote(View("BTCUSDT", tuple(moteur[k - HISTORIQUE + 1:k + 1])))
                votes.append(0.0 if vote is None else 1.0 if module.NOM in PRESENCE
                             else float(vote.direction * vote.intensity))
            accord = sum(abs(s - v) <= TOLERANCE for s, v in zip(signaux, votes)) / len(indices)
            resultats.append((module.NOM, regle.name, accord, sum(v != 0 for v in votes)))
    return resultats
