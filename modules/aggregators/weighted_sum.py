from decimal import Decimal

from engine.base import Aggregator
from engine.domain import Ballot, Tally


class WeightedSum(Aggregator):
    """Somme ponderee avec seuil et quorum.

    score = somme(poids x direction x intensite) / poids exprime, entre -1 et +1.
    quorum : fraction du poids inscrit qui doit s'exprimer.
    """

    def __init__(self, threshold: Decimal, quorum: Decimal):
        self.threshold = threshold
        self.quorum = quorum

    def tally(self, ballots: tuple[Ballot, ...]) -> Tally:
        enrolled = sum((ballot.weight for ballot in ballots), Decimal(0))
        cast = [ballot for ballot in ballots if ballot.vote is not None]
        expressed = sum((ballot.weight for ballot in cast), Decimal(0))
        if expressed == 0 or expressed < self.quorum * enrolled:
            return Tally(0, Decimal(0), expressed, enrolled, "quorum non atteint")
        score = sum((b.weight * b.vote.direction * b.vote.intensity for b in cast), Decimal(0)) / expressed
        if abs(score) < self.threshold:
            return Tally(0, score, expressed, enrolled, "score sous le seuil")
        return Tally(1 if score > 0 else -1, score, expressed, enrolled, "seuil franchi")
