from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Horloge : la seule facon de lire l'heure."""

    @abstractmethod
    def now(self) -> datetime:
        """Instant courant, en UTC."""
