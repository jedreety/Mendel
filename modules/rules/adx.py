from decimal import Decimal

from engine.base import Rule
from engine.domain import View, Vote


class Adx(Rule):
    """ADX de Wilder, variante sans lissage exponentiel : vote le cote dominant de +DM contre -DM sur les
    `period` dernieres barres quand l'ADX atteint `threshold`, sinon s'abstient. 0 a egalite, s'abstient
    sans aucun mouvement.

    DX : |somme +DM - somme -DM| / (somme +DM + somme -DM) sur `period` barres, comme DirectionalMovement.
    ADX : moyenne des `period` derniers DX, sur 100. Seuil usuel : 25.
    Intensite : ADX sur 100.
    """

    def __init__(self, weight: Decimal, period: int, threshold: Decimal):
        self.name = f"Adx({period},{threshold})"
        self.weight = weight
        self.warmup = 2 * period
        self.period = period
        self.threshold = threshold

    def vote(self, view: View) -> Vote | None:
        bars = view.bars[-self.warmup:]
        plus, minus = [], []
        for prev, bar in zip(bars, bars[1:]):
            up = bar.high - prev.high
            down = prev.low - bar.low
            plus.append(up if up > down and up > 0 else Decimal(0))
            minus.append(down if down > up and down > 0 else Decimal(0))
        windows = [
            (sum(plus[end - self.period:end], Decimal(0)), sum(minus[end - self.period:end], Decimal(0)))
            for end in range(self.period, len(plus) + 1)
        ]
        adx = 100 * sum((abs(p - m) / (p + m) for p, m in windows if p + m > 0), Decimal(0)) / self.period
        if adx < self.threshold:
            return None
        p, m = windows[-1]
        if p + m == 0:
            return None
        if p == m:
            return Vote(0, Decimal(0))
        return Vote(1 if p > m else -1, adx / 100)
