from decimal import Decimal

from engine.base import Aggregator
from engine.domain import Ballot, Tally


class Unanimity(Aggregator):
    """Unanimite stricte : une direction n'est retenue que si toutes les regles qui votent
    pointent dans le meme sens. Un vote 0 ou un vote oppose suffit a bloquer.

    quorum : fraction du poids inscrit qui doit s'exprimer. score : somme ponderee, pour le journal.
    """

    def __init__(self, quorum: Decimal):
        self.quorum = quorum

    def tally(self, ballots: tuple[Ballot, ...]) -> Tally:
        enrolled = sum((ballot.weight for ballot in ballots), Decimal(0))
        cast = [ballot for ballot in ballots if ballot.vote is not None]
        expressed = sum((ballot.weight for ballot in cast), Decimal(0))
        if expressed == 0 or expressed < self.quorum * enrolled:
            return Tally(0, Decimal(0), expressed, enrolled, "quorum non atteint")
        score = sum((b.weight * b.vote.direction * b.vote.intensity for b in cast), Decimal(0)) / expressed
        directions = {ballot.vote.direction for ballot in cast}
        if directions == {1} or directions == {-1}:
            return Tally(directions.pop(), score, expressed, enrolled, "unanimite")
        return Tally(0, score, expressed, enrolled, "pas d'unanimite")
