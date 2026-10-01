"""Pantheon : les meilleures notes de validation du run, deux a deux distinctes."""
from dataclasses import dataclass

import torch

from evolution.selection import distincts


@dataclass
class Membre:
    """Un bot evalue en validation. serie : sa fraction engagee a chaque barre notee des trimestres."""

    id: str
    generation: int
    genome: torch.Tensor
    note: float
    serie: torch.Tensor
    detail: dict


def mettre_a_jour(membres: list[Membre], candidats: list[Membre], nombre: int, seuil: float) -> list[Membre]:
    """Nouveau Pantheon : les meilleures notes parmi les membres et les candidats, deux a deux distinctes.

    Un candidat deja membre, meme identifiant, est le meme bot : il n'est pas compte deux fois.
    """
    connus = {m.id for m in membres}
    reserve = membres + [c for c in candidats if c.id not in connus]
    reserve.sort(key=lambda m: (-m.note, m.generation, m.id))
    retenus = distincts(torch.stack([m.serie for m in reserve]), nombre, seuil)
    return sorted((reserve[i] for i in retenus), key=lambda m: (-m.note, m.generation, m.id))
