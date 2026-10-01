"""Mesure d'une echelle de temps : mouvement median d'une barre, compare au cout d'un aller-retour.

    python -m scripts.measure_timeframes data/prepared/BTCUSDT-5m.csv data/prepared/BTCUSDT-1h.csv

Mesure prudente : |cloture / ouverture - 1|, sans les meches.
"""
import argparse
from decimal import Decimal
from pathlib import Path
from statistics import median

from adapters.csv_source import CsvSource


def main() -> None:
    parser = argparse.ArgumentParser(description="Mouvement median par barre contre cout d'un aller-retour.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--fee", type=Decimal, default=Decimal("0.001"), help="frais par cote")
    args = parser.parse_args()

    round_trip = 2 * args.fee
    for path in args.files:
        moves = [abs(bar.close / bar.open - 1) for bar in CsvSource(path).bars()]
        move = median(moves)
        print(f"{path.name}: {len(moves)} barres, mouvement median {move:.4%}, "
              f"{move / round_trip:.2f} fois l'aller-retour de {round_trip:.2%}")


if __name__ == "__main__":
    main()
