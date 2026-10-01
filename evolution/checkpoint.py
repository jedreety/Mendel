"""Points de sauvegarde : fichiers JSON lisibles sans PyTorch, ecrits de facon atomique.

Le processus peut mourir a tout instant : un fichier est ecrit a cote, puis remplace d'un
coup. Les genomes sont des listes de nombres : un float32 converti en float Python se relit a l'identique.
"""
import json
import math
import os
from pathlib import Path

import torch


def propre(contenu):
    """Remplace les nombres non finis par null : un JSON strict, que l'interface a venir pourra lire."""
    if isinstance(contenu, float):
        return contenu if math.isfinite(contenu) else None
    if isinstance(contenu, dict):
        return {cle: propre(valeur) for cle, valeur in contenu.items()}
    if isinstance(contenu, (list, tuple)):
        return [propre(valeur) for valeur in contenu]
    return contenu


def texte(contenu) -> str:
    return json.dumps(propre(contenu), ensure_ascii=False, default=str, allow_nan=False)


def ecrire(chemin: Path, contenu) -> None:
    provisoire = chemin.with_name(chemin.name + ".tmp")
    provisoire.write_text(texte(contenu) + "\n", encoding="utf-8")
    os.replace(provisoire, chemin)


def lire(chemin: Path):
    return json.loads(chemin.read_text(encoding="utf-8"))


def liste(tenseur: torch.Tensor) -> list[float]:
    return tenseur.detach().float().cpu().tolist()


def tenseur(valeurs: list[float]) -> torch.Tensor:
    return torch.tensor(valeurs, dtype=torch.float32)
