"""Mesure les regles d'une strategie sur l'historique, sans backtest.

    python -m scripts.measure_rules input/catalog.py data/prepared/BTCUSDT-1h.csv

Frequence de chaque regle, en part des barres evaluees (apres sa chauffe).
Paires de regles dont les directions sont correlees au-dela du seuil.
Une abstention et un vote 0 comptent tous deux comme 0 dans la correlation.
"""
import argparse
import importlib
from collections import deque
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from statistics import StatisticsError, correlation

from adapters.csv_source import CsvSource
from engine.domain import View


def main() -> None:
    parser = argparse.ArgumentParser(description="Frequence et correlation des regles d'une strategie.")
    parser.add_argument("strategy", type=Path, help="fichier de input/")
    parser.add_argument("data", type=Path, help="fichier de data/prepared/")
    parser.add_argument("--threshold", type=float, default=0.7, help="seuil de correlation")
    args = parser.parse_args()

    rules = importlib.import_module(f"input.{args.strategy.stem}").build().rules
    symbol = args.data.stem.split("-")[0]
    window = deque(maxlen=max(rule.warmup for rule in rules))
    directions = {rule.name: [] for rule in rules}
    counts = {rule.name: {"barres": 0, "hausse": 0, "baisse": 0, "zero": 0} for rule in rules}

    for bar in CsvSource(args.data).bars():
        window.append(bar)
        view = View(symbol, tuple(window))
        for rule in rules:
            if len(window) < rule.warmup:
                directions[rule.name].append(0)
                continue
            vote = rule.vote(view)
            count = counts[rule.name]
            count["barres"] += 1
            direction = 0 if vote is None else vote.direction
            directions[rule.name].append(direction)
            if vote is None:
                continue
            count["hausse" if direction > 0 else "baisse" if direction < 0 else "zero"] += 1

    print(f"{'regle':<44} {'barres':>7} {'vote':>7} {'hausse':>7} {'baisse':>7} {'zero':>7}")
    for rule in rules:
        c = counts[rule.name]
        share = lambda n: f"{Decimal(100 * n) / c['barres']:.1f}%" if c["barres"] else "-"
        print(f"{rule.name:<44} {c['barres']:>7} {share(c['hausse'] + c['baisse']):>7} "
              f"{share(c['hausse']):>7} {share(c['baisse']):>7} {share(c['zero']):>7}")

    print(f"\nPaires correlees au-dela de {args.threshold} :")
    for a, b in combinations(directions, 2):
        try:
            r = correlation(directions[a], directions[b])
        except StatisticsError:
            continue  # regle constante sur l'echantillon
        if abs(r) >= args.threshold:
            print(f"  {r:+.2f}  {a}  /  {b}")


if __name__ == "__main__":
    main()
