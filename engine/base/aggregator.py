from abc import ABC, abstractmethod

from engine.domain import Ballot, Tally


class Aggregator(ABC):
    """Interpreteur : agrege les bulletins en une direction, avec seuil et quorum."""

    @abstractmethod
    def tally(self, ballots: tuple[Ballot, ...]) -> Tally:
        """Les abstentions sortent du denominateur, les votes 0 y restent."""
