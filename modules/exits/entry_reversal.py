from engine.base import Aggregator, ExitModule, Rule
from engine.domain import Ballot, Position, View, Vote


class EntryReversal(ExitModule):
    """Inversion du signal d'entree : le vote d'entree est rejoue sur la barre. S'il pointe
    a la baisse, le module vote la fermeture ; a la hausse, il retient la position ; sans direction, il
    s'abstient. Intensite : la force du nouveau score.

    Regles et interpreteur sont ceux de l'entree, declares une fois dans le fichier de strategie.
    Chauffe : celle de la regle la plus longue ; avant, le module ne se prononce pas.
    """

    def __init__(self, rules: tuple[Rule, ...], aggregator: Aggregator):
        self.name = "EntryReversal"
        self.warmup = max(rule.warmup for rule in rules)
        self.rules = rules
        self.aggregator = aggregator

    def vote(self, view: View, position: Position) -> Vote | None:
        tally = self.aggregator.tally(tuple(Ballot(rule.name, rule.weight, rule.vote(view)) for rule in self.rules))
        if tally.direction == 0:
            return None
        return Vote(-tally.direction, abs(tally.score))
