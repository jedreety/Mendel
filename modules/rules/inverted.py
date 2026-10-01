from engine.base import Rule
from engine.domain import View, Vote


class Inverted(Rule):
    """Inverse le sens d'une regle : une lecture en retour a la moyenne devient une lecture en cassure,
    et reciproquement. Poids, chauffe et intensite sont ceux de la regle enveloppee.
    """

    def __init__(self, rule: Rule):
        self.name = f"Inverted({rule.name})"
        self.weight = rule.weight
        self.warmup = rule.warmup
        self.rule = rule

    def vote(self, view: View) -> Vote | None:
        vote = self.rule.vote(view)
        if vote is None:
            return None
        return Vote(-vote.direction, vote.intensity)
