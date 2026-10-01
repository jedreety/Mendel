"""Bots de l'interface : leur nom et leur suppression.

Un bot est un run reel ; son run a blanc et sa recherche aleatoire, ses temoins, lui appartiennent. Les noms
vivent dans interface/etat/noms.json : l'interface n'ecrit rien dans un dossier de run. Supprimer un bot envoie
son dossier et ceux de ses temoins a la corbeille de Windows, d'ou ils se restaurent.
"""
import json
import os
import threading
from pathlib import Path

from interface import windows
from interface.lecture import Lecteur
from interface.taches import ErreurDemande, Taches

NOM_MAX = 60


class Bots:
    def __init__(self, racine: Path, taches: Taches, lecteur: Lecteur | None):
        self.taches, self.lecteur = taches, lecteur
        self.fichier = racine / "interface" / "etat" / "noms.json"
        self.verrou = threading.Lock()
        self.noms: dict[str, str] = json.loads(self.fichier.read_text(encoding="utf-8")) if self.fichier.exists() else {}

    def nom(self, run: str) -> str | None:
        with self.verrou:
            return self.noms.get(run)

    def nommer(self, run: str, nom: str) -> None:
        """Un nom vide rend au bot son nom par defaut."""
        propre = " ".join("".join(c if c.isprintable() else " " for c in str(nom)).split())[:NOM_MAX]
        with self.verrou:
            if propre:
                self.noms[run] = propre
            else:
                self.noms.pop(run, None)
            self._ecrire()

    def renommer(self, run: str, nom: str) -> dict:
        self.nommer(self.lecteur.dossier(run).name, nom)
        return {"run": run, "nom": self.nom(run)}

    def supprimer(self, run: str) -> dict:
        """Le bot et ses temoins, a la corbeille. Refuse tant qu'une tache ou un run les ecrit."""
        concernes = [self.lecteur.dossier(run).name, *self.lecteur.temoins(run)]
        tache = self.taches.vivante()
        if tache and (tache.get("run") in concernes or tache.get("source") in concernes):
            raise ErreurDemande("Une tâche travaille sur ce bot : arrêtez-la avant de le supprimer.")
        for nom in concernes:
            if self.lecteur.actif(nom, self.lecteur.dossier(nom)):
                raise ErreurDemande(f"{nom} a été écrit il y a moins de cinq minutes : attendez qu'il soit à l'arrêt.")
        try:
            windows.corbeille([self.lecteur.dossier(nom) for nom in concernes])
        except OSError as erreur:
            raise ErreurDemande(f"Windows a refusé la suppression : {erreur}") from erreur
        with self.verrou:
            for nom in concernes:
                self.noms.pop(nom, None)
            self._ecrire()
        return {"supprimes": concernes}

    def _ecrire(self) -> None:
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.fichier.with_name(self.fichier.name + ".tmp")
        provisoire.write_text(json.dumps(self.noms, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(provisoire, self.fichier)
