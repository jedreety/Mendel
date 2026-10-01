from engine.base import ExitModule
from engine.domain import Position, View


class HardTier:
    """Etage des constats : ordre declare, le premier module qui vote la fermeture l'emporte."""

    def __init__(self, *modules: ExitModule):
        self.modules = modules

    def first(self, view: View, position: Position) -> str | None:
        """Nom du premier module qui vote la fermeture, sinon None."""
        for module in self.modules:
            if len(view.bars) < module.warmup:
                continue
            vote = module.vote(view, position)
            if vote is not None and vote.direction > 0:
                return module.name
        return None
