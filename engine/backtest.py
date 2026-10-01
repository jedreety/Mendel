from engine.base import DataSource
from engine.pipeline import Pipeline


def backtest(source: DataSource, pipeline: Pipeline) -> None:
    """Boucle de backtest : fournit chaque barre close a la passe, puis solde la position restante."""
    for bar in source.bars():
        pipeline.on_bar(bar)
    pipeline.liquidate("fin des donnees")
