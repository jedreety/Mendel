"""Selection : parents deux a deux distincts, enfants tires parmi eux selon leur rang."""
import math
from itertools import accumulate

import torch

from evolution import philox


def correlations(series: torch.Tensor) -> torch.Tensor:
    """Correlations de Pearson entre series de positions, en float64.

    Deux series constantes sont identiques ; une serie constante est distincte de toute autre.
    """
    x = series.double()
    x = x - x.mean(1, keepdim=True)
    norme = x.norm(dim=1)
    constante = norme == 0
    corr = (x @ x.T) / (norme[:, None] * norme[None, :]).clamp(min=1e-300)
    corr = torch.where(constante[:, None] | constante[None, :], 0.0, corr)
    return torch.where(constante[:, None] & constante[None, :], 1.0, corr)


def distincts(series: torch.Tensor, nombre: int, seuil: float) -> list[int]:
    """Rangs retenus parmi des candidats deja classes du meilleur au moins bon.

    Un candidat est ecarte si sa correlation avec un retenu depasse le seuil. S'il manque des places, elles
    reviennent aux meilleurs candidats non retenus.
    """
    corr = correlations(series)
    retenus: list[int] = []
    for candidat in range(series.shape[0]):
        if len(retenus) == nombre:
            break
        if all(corr[candidat, autre] <= seuil for autre in retenus):
            retenus.append(candidat)
    for candidat in range(series.shape[0]):
        if len(retenus) == nombre:
            break
        if candidat not in retenus:
            retenus.append(candidat)
    return retenus


def parts_des_parents(nb_parents: int) -> list[float]:
    """Part des enfants de chaque parent, du meilleur au moins bon : ln(p + 1/2) - ln(r), normalisee.

    Ce sont les poids de recombinaison de Hansen (CMA-ES) : le meilleur parent a le plus d'enfants, le dernier
    en garde quelques-uns. Avec 5 parents : 46 %, 27 %, 16 %, 8 % et 2,5 %.
    """
    brutes = [math.log(nb_parents + 0.5) - math.log(r) for r in range(1, nb_parents + 1)]
    return [b / sum(brutes) for b in brutes]


def enfants(maitresse: int, usage: int, generation: int, indices: torch.Tensor,
            nb_parents: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Cle Philox et parent de chaque enfant : le parent de rang r est tire avec la part de parts_des_parents,
    par comparaison d'un mot de 32 bits aux parts cumulees.
    """
    k0, k1, tirage = philox.cles_t(maitresse, usage, generation, indices)
    cumuls = list(accumulate(parts_des_parents(nb_parents)))[:-1]
    seuils = torch.tensor([int(c * 2**32) for c in cumuls], dtype=torch.int64, device=tirage.device)
    return k0, k1, (tirage[:, None] >= seuils[None, :]).sum(1)
