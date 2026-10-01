import csv
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from engine.base import DataSource
from engine.domain import Bar


class CsvSource(DataSource):
    """Lit un fichier de data/prepared/.

    En-tete : time,open,high,low,close,volume. time : instant de cloture, ISO 8601 en UTC.
    """

    def __init__(self, path: Path):
        self.path = path

    def bars(self) -> Iterator[Bar]:
        previous = None
        with self.path.open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                bar = Bar(
                    datetime.fromisoformat(row["time"]),
                    Decimal(row["open"]),
                    Decimal(row["high"]),
                    Decimal(row["low"]),
                    Decimal(row["close"]),
                    Decimal(row["volume"]),
                )
                if previous is not None and bar.time <= previous:
                    raise ValueError(f"{self.path}: barre hors ordre a {bar.time}")  # la vue ne doit jamais voir le futur
                previous = bar.time
                yield bar
