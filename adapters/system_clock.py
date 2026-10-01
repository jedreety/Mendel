from datetime import UTC, datetime

from engine.base import Clock


class SystemClock(Clock):
    """Seul endroit du depot qui lit l'horloge systeme."""

    def now(self) -> datetime:
        return datetime.now(UTC)
