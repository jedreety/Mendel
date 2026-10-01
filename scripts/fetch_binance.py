"""Telecharge les klines spot mensuelles de data.binance.vision et prepare un fichier pour run.py.

    python -m scripts.fetch_binance BTCUSDT 1h 2024-01 2024-12

Archives brutes dans data/raw/binance/, fichier prepare dans data/prepared/SYMBOLE-ECHELLE.csv.
Seuls des mois complets existent : le mois en cours n'est pas encore publie.
"""
import argparse
import csv
import io
import urllib.request
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://data.binance.vision/data/spot/monthly/klines/{symbol}/{interval}/{name}.zip"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
UNITS = {"m": "minutes", "h": "hours", "d": "days"}


def months(start: str, end: str) -> Iterator[str]:
    year, month = map(int, start.split("-"))
    while f"{year:04d}-{month:02d}" <= end:
        yield f"{year:04d}-{month:02d}"
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def close_time(raw_open: str, width: timedelta) -> datetime:
    """Cloture nominale : l'ouverture ramenee sur la grille de l'echelle, plus la duree d'une barre.

    Binance donne l'ouverture en millisecondes, puis en microsecondes depuis 2025. Sa colonne de cloture
    est fausse pour les barres coupees par un arret de l'exchange, et des ouvertures de fevrier 2018 sont
    decalees de 28 minutes : seule l'ouverture est fiable.
    """
    stamp = int(raw_open)
    opened = EPOCH + timedelta(microseconds=stamp if stamp >= 10**14 else stamp * 1000)
    return opened - (opened - EPOCH) % width + width


def main() -> None:
    parser = argparse.ArgumentParser(description="Telecharge et prepare des klines Binance spot.")
    parser.add_argument("symbol", help="par exemple BTCUSDT")
    parser.add_argument("interval", help="par exemple 5m, 1h, 4h")
    parser.add_argument("start", help="premier mois, AAAA-MM")
    parser.add_argument("end", help="dernier mois, AAAA-MM")
    args = parser.parse_args()

    raw_dir = ROOT / "data" / "raw" / "binance"
    raw_dir.mkdir(exist_ok=True)
    target = ROOT / "data" / "prepared" / f"{args.symbol}-{args.interval}.csv"
    draft = target.with_suffix(".part")  # renomme une fois complet : jamais de fichier tronque pris pour un marche
    width = timedelta(**{UNITS[args.interval[-1]]: int(args.interval[:-1])})
    previous = None
    with draft.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["time", "open", "high", "low", "close", "volume"])
        for month in months(args.start, args.end):
            name = f"{args.symbol}-{args.interval}-{month}"
            archive = raw_dir / f"{name}.zip"
            if not archive.exists():
                partial = archive.with_suffix(".part")
                urllib.request.urlretrieve(URL.format(symbol=args.symbol, interval=args.interval, name=name), partial)
                partial.rename(archive)
            with zipfile.ZipFile(archive) as bundle, bundle.open(f"{name}.csv") as member:
                for row in csv.reader(io.TextIOWrapper(member, encoding="utf-8")):
                    if not row[0].isdigit():
                        continue  # ligne d'en-tete
                    time = close_time(row[0], width)
                    if previous is not None and time <= previous:
                        raise ValueError(f"{name}: deux barres pour la cloture {time}")
                    previous = time
                    writer.writerow([time.isoformat(), *row[1:6]])
    draft.replace(target)
    print(target)


if __name__ == "__main__":
    main()
