"""Lanceur : assemble strategie, moteur et adaptateurs, ecrit le run dans runs/.

    python run.py input/trend.py data/prepared/BTCUSDT-1h.csv --patience 1
"""
import argparse
import csv
import hashlib
import importlib
import json
import subprocess
from dataclasses import asdict, astuple, fields
from decimal import Decimal
from pathlib import Path

from adapters.csv_source import CsvSource
from adapters.sim_broker import SimBroker
from adapters.system_clock import SystemClock
from engine.backtest import backtest
from engine.domain import Trade, Venue
from engine.journal import Journal
from engine.ledger import Ledger
from engine.pipeline import Pipeline
from engine.policy import Policy

ROOT = Path(__file__).resolve().parent

# Binance spot BTCUSDT : pas de prix, pas de quantite, notionnel minimum, frais taker sans remise.
# A relire pour un autre symbole ou un autre lieu.
VENUE = Venue(
    tick_size=Decimal("0.01"),
    qty_step=Decimal("0.00001"),
    min_notional=Decimal("5"),
    fee_rate=Decimal("0.001"),
    slippage=Decimal("0.0005"),
)


def revision() -> str:
    """Revision git du code, marquee si l'arbre de travail differe du commit."""
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, encoding="utf-8")
    if head.returncode != 0:
        return "aucune"
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, encoding="utf-8")
    return head.stdout.strip() + ("+modifie" if status.stdout.strip() else "")


def write_json(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest d'une strategie de input/.")
    parser.add_argument("strategy", type=Path, help="fichier de input/, par exemple input/trend.py")
    parser.add_argument("data", type=Path, help="fichier de data/prepared/, nomme SYMBOLE-ECHELLE.csv")
    parser.add_argument("--patience", type=Decimal, default=Decimal("1"))
    parser.add_argument("--capital", type=Decimal, default=Decimal("1000"))
    args = parser.parse_args()

    name = args.strategy.stem
    symbol = args.data.stem.split("-")[0]
    strategy = importlib.import_module(f"input.{name}").build(patience=args.patience)

    started = SystemClock().now()
    run_dir = ROOT / "runs" / f"{started:%Y%m%dT%H%M%SZ}-{name}"
    run_dir.mkdir()
    with args.data.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    write_json(run_dir / "manifest.json", {
        "strategie": args.strategy.as_posix(),
        "parametres": {"patience": args.patience},
        "donnees": args.data.as_posix(),
        "empreinte_donnees": digest,
        "symbole": symbol,
        "date": started,
        "revision": revision(),
        "capital_initial": args.capital,
        "lieu": asdict(VENUE),
    })

    ledger = Ledger(args.capital)
    journal = Journal(run_dir / "journal.jsonl")
    try:
        backtest(CsvSource(args.data), Pipeline(name, symbol, Policy(strategy, VENUE), SimBroker(VENUE), ledger, journal))
    finally:
        journal.close()

    with (run_dir / "trades.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(field.name for field in fields(Trade))
        writer.writerows(astuple(trade) for trade in ledger.trades)

    net = sum((trade.net for trade in ledger.trades), Decimal(0))
    summary = {
        "capital_initial": ledger.initial,
        "capital_final": ledger.cash,
        "resultats_nets": net,
        "frais": sum((trade.fees for trade in ledger.trades), Decimal(0)),
        "trades": len(ledger.trades),
        "identite": ledger.cash == ledger.initial + net,
    }
    write_json(run_dir / "summary.json", summary)
    print(run_dir)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
