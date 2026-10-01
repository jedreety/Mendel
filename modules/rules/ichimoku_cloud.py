from decimal import Decimal

from engine.base import Rule
from engine.domain import Bar, View, Vote


def _middle(bars: tuple[Bar, ...]) -> Decimal:
    return (max(bar.high for bar in bars) + min(bar.low for bar in bars)) / 2


class IchimokuCloud(Rule):
    """Nuage d'Ichimoku : cloture au-dessus du nuage +1, en dessous -1, dedans 0.

    Le nuage en vigueur a ete calcule `kijun` barres plus tot (projection classique) :
    senkou A = milieu de tenkan et kijun, senkou B = milieu des extremes sur `senkou` barres.
    Intensite : distance au nuage en unites de volatilite (periode tenkan), plafonnee a 1.
    """

    def __init__(self, weight: Decimal, tenkan: int, kijun: int, senkou: int):
        self.name = f"IchimokuCloud({tenkan},{kijun},{senkou})"
        self.weight = weight
        self.warmup = senkou + kijun
        self.tenkan = tenkan
        self.kijun = kijun
        self.senkou = senkou

    def vote(self, view: View) -> Vote | None:
        past = view.bars[:-self.kijun]
        span_a = (_middle(past[-self.tenkan:]) + _middle(past[-self.kijun:])) / 2
        span_b = _middle(past[-self.senkou:])
        top, bottom = max(span_a, span_b), min(span_a, span_b)
        close = view.bars[-1].close
        if bottom <= close <= top:
            return Vote(0, Decimal(0))
        r = view.volatility(self.tenkan)
        if r == 0:
            return None
        if close > top:
            return Vote(1, min(Decimal(1), (close - top) / r))
        return Vote(-1, min(Decimal(1), (bottom - close) / r))
