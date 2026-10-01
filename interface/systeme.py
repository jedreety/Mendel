"""Mesures du poste pour l'interface : GPU par nvidia-smi, processeur, memoire et disque par l'API Windows,
et les processus d'une tache (le bot et ses processus de rejeu).

Un echantillon toutes les deux secondes, tant que quelqu'un regarde ou qu'une tache tourne ; trente minutes
gardees en memoire. Les instants viennent de l'adaptateur d'horloge.
"""
import collections
import os
import shutil
import subprocess
import threading
from pathlib import Path

from adapters.system_clock import SystemClock
from interface import windows

PERIODE_S = 2.0
HISTORIQUE = 900  # echantillons : trente minutes de mesure continue
HISTORIQUE_S = 1800  # et jamais plus vieux que trente minutes, meme apres une interruption
# Le nom en dernier : c'est le seul champ qui pourrait contenir une virgule.
CHAMPS_GPU = ("utilisation", "utilisation_memoire", "memoire_utilisee", "memoire_totale", "temperature",
              "puissance", "puissance_max", "frequence", "frequence_max", "ventilateur", "etat")
REQUETE_GPU = ("utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,"
               "power.limit,clocks.sm,clocks.max.sm,fan.speed,pstate,name")


def gpu() -> dict | None:
    try:
        sortie = subprocess.run(["nvidia-smi", f"--query-gpu={REQUETE_GPU}", "--format=csv,noheader,nounits"],
                                capture_output=True, encoding="utf-8", errors="replace", timeout=5,
                                creationflags=windows.SANS_FENETRE)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lignes = sortie.stdout.strip().splitlines()
    if sortie.returncode != 0 or not lignes:
        return None
    valeurs = [v.strip() for v in lignes[0].split(",")]
    mesures = {"nom": ", ".join(valeurs[len(CHAMPS_GPU):])}
    for cle, valeur in zip(CHAMPS_GPU, valeurs):
        if cle == "etat":
            mesures[cle] = valeur
            continue
        try:
            mesures[cle] = float(valeur)
        except ValueError:  # [N/A] ou [Not Supported]
            mesures[cle] = None
    return mesures


class Echantillonneur:
    """Fil de mesure. besoin() dit s'il faut mesurer ; pid() donne le processus de la tache en cours."""

    def __init__(self, racine: Path, besoin, pid, publier):
        self.racine, self.besoin, self.pid, self.publier = racine, besoin, pid, publier
        self.historique: collections.deque = collections.deque(maxlen=HISTORIQUE)
        self.verrou = threading.Lock()
        self.precedent_systeme = windows.temps_systeme()
        self.precedent_calcul: dict[int, int] = {}
        self.arret = threading.Event()
        self.fil = threading.Thread(target=self._boucle, name="echantillonneur", daemon=True)

    def demarrer(self) -> None:
        self.fil.start()

    def echantillons(self) -> list[dict]:
        with self.verrou:
            return list(self.historique)

    def _boucle(self) -> None:
        while not self.arret.wait(PERIODE_S):
            if not self.besoin():
                continue
            echantillon = self.mesurer()
            with self.verrou:
                self.historique.append(echantillon)
                while self.historique[0]["t"] < echantillon["t"] - HISTORIQUE_S:
                    self.historique.popleft()
            self.publier("systeme", echantillon)

    def mesurer(self) -> dict:
        systeme = windows.temps_systeme()
        ecart_total = None
        cpu = None
        if systeme and self.precedent_systeme:
            inactif = systeme[0] - self.precedent_systeme[0]
            ecart_total = systeme[1] - self.precedent_systeme[1]
            cpu = round(100 * (1 - inactif / ecart_total), 1) if ecart_total > 0 else None
        self.precedent_systeme = systeme
        utilisee, totale = windows.memoire()
        disque = shutil.disk_usage(self.racine)
        return {
            "t": SystemClock().now().timestamp(),
            "gpu": gpu(),
            "cpu": cpu,
            "coeurs": os.cpu_count(),
            "memoire": {"utilisee": utilisee, "totale": totale},
            "disque": {"libre": disque.free, "total": disque.total},
            "bot": self._bot(ecart_total),
        }

    def _bot(self, ecart_total: int | None) -> dict | None:
        """Processus de la tache en cours : calcul en part de toute la machine, memoire de travail."""
        pid = self.pid()
        if pid is None:
            self.precedent_calcul = {}
            return None
        calcul, memoire, vivants = {}, 0, 0
        for p in windows.descendants(pid):
            etat = windows.processus(p)
            if etat is None or not etat["vivant"]:
                continue
            vivants += 1
            calcul[p] = etat["calcul"]
            memoire += etat["memoire"]
        cpu = None
        if ecart_total:
            ecart = sum(c - self.precedent_calcul[p] for p, c in calcul.items() if p in self.precedent_calcul)
            cpu = round(100 * ecart / ecart_total, 1)
        self.precedent_calcul = calcul
        return {"pid": pid, "processus": vivants, "cpu": cpu, "memoire": memoire}
