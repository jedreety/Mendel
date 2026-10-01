from abc import ABC, abstractmethod

from engine.domain import Position, View, Vote


class ExitModule(ABC):
    """Module de sortie. Repond a "faut-il fermer", ne passe jamais d'ordre.

    L'etage ou il est branche decide si son vote est un verdict ou une voix parmi d'autres.
    """

    name: str
    warmup: int

    @abstractmethod
    def vote(self, view: View, position: Position) -> Vote | None:
        """+1 pour fermer, -1 pour garder, None pour s'abstenir."""
