from engine.base import ExitModule, Rule
from engine.domain import Position, View, Vote


class RuleExit(ExitModule):
    """Branche une regle d'entree en sortie : elle vote la fermeture quand la regle pointe contre la position
    longue (-1), et retient la position quand elle pointe dans son sens (+1). Un vote 0 reste 0, une
    abstention reste une abstention. Chauffe et intensite sont celles de la regle ; son poids ne sert pas ici.

    Exemples : RuleExit(Macd(...)) ferme quand le momentum s'essouffle ;
    RuleExit(DonchianBreakout(...)) ferme sur la cassure du bas du canal.
    """

    def __init__(self, rule: Rule):
        self.name = f"RuleExit({rule.name})"
        self.warmup = rule.warmup
        self.rule = rule

    def vote(self, view: View, position: Position) -> Vote | None:
        vote = self.rule.vote(view)
        if vote is None:
            return None
        return Vote(-vote.direction, vote.intensity)
