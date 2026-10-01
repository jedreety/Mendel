from decimal import Decimal

from engine.base import Aggregator
from engine.domain import Ballot, Tally


class QualifiedMajority(Aggregator):
    """Majorite qualifiee : une direction est retenue quand le poids qui la vote atteint
    `majority` du poids exprime, par exemple 2/3. L'intensite n'entre pas dans le decompte.

    quorum : fraction du poids inscrit qui doit s'exprimer.
    score : poids pour la hausse moins poids pour la baisse, sur le poids exprime.
    """

    def __init__(self, majority: Decimal, quorum: Decimal):
        self.majority = majority
        self.quorum = quorum

    def tally(self, ballots: tuple[Ballot, ...]) -> Tally:
        enrolled = sum((ballot.weight for ballot in ballots), Decimal(0))
        cast = [ballot for ballot in ballots if ballot.vote is not None]
        expressed = sum((ballot.weight for ballot in cast), Decimal(0))
        if expressed == 0 or expressed < self.quorum * enrolled:
            return Tally(0, Decimal(0), expressed, enrolled, "quorum non atteint")
        up = sum((b.weight for b in cast if b.vote.direction > 0), Decimal(0))
        down = sum((b.weight for b in cast if b.vote.direction < 0), Decimal(0))
        score = (up - down) / expressed
        if up >= self.majority * expressed:
            return Tally(1, score, expressed, enrolled, "majorite qualifiee")
        if down >= self.majority * expressed:
            return Tally(-1, score, expressed, enrolled, "majorite qualifiee")
        return Tally(0, score, expressed, enrolled, "pas de majorite qualifiee")
