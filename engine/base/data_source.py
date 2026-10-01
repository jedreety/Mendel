from abc import ABC, abstractmethod
from collections.abc import Iterator

from engine.domain import Bar


class DataSource(ABC):
    """Source de barres."""

    @abstractmethod
    def bars(self) -> Iterator[Bar]:
        """Barres closes, dans l'ordre chronologique strict."""
