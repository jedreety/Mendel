import json
from pathlib import Path


class Journal:
    """Journal : une ligne JSON par barre, y compris quand rien n'est fait.

    Chaque ligne est ecrite sur disque aussitot : c'est un livre de comptes, pas du logging.
    """

    def __init__(self, path: Path):
        self.file = path.open("w", encoding="utf-8")

    def write(self, entry: dict) -> None:
        self.file.write(json.dumps(entry, default=str) + "\n")
        self.file.flush()

    def close(self) -> None:
        self.file.close()
