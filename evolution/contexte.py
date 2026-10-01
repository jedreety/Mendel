"""Ce que l'entrainement et le benchmark partagent : donnees, marche, genome, evaluateur, population de
reference, et le manifeste d'un dossier de run.
"""
import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import torch

from adapters.system_clock import SystemClock
from evolution import noyau, philox
from evolution.config import Config
from evolution.data import Fenetre, Historique, charger, minuit, permuter
from evolution.evaluation import Evaluateur
from evolution.fitness import composantes, noter
from evolution.genome import MODULES, Disposition
from evolution.marche import LISSER, Marche

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Contexte:
    config: Config
    hist: Historique
    disposition: Disposition
    evaluateur: Evaluateur
    symbole: str

    @property
    def capital0(self) -> int:
        """Capital initial en unites comptables du simulateur."""
        return self.evaluateur.principal.capital0


def preparer(config: Config, appareil: torch.device, test: bool, a_blanc: bool = False,
             taille_paquet: int | None = None) -> Contexte:
    """test : seul le benchmark final passe True. Sinon, l'historique s'arrete avant le bloc de test."""
    chemin = ROOT / config.donnees
    hist = charger(chemin, config.pas_de_prix, None if test else minuit(config.debut_test))
    if a_blanc:
        hist = permuter(hist, config)
    marche = Marche(hist, appareil)
    tables = [module.preparer(marche) for module in MODULES]
    disposition = Disposition(config.taille_cachee, config.canaux_modules).vers(appareil)
    evaluateur = Evaluateur(marche, tables, disposition, config, taille_paquet)
    return Contexte(config, hist, disposition, evaluateur, chemin.stem.split("-")[0])


def reference(ctx: Contexte, fenetres: list[Fenetre]) -> torch.Tensor:
    """Notes de la population de reference : des bots tires comme la generation 0, avec leur propre usage de
    la graine maitresse. Elles situent la note de test du champion parmi celles du hasard.
    """
    config, disposition = ctx.config, ctx.disposition
    n = config.population_reference
    indices = torch.arange(n, device=disposition.appareil)
    k0, k1, _ = philox.cles_t(config.graine_maitresse, philox.REFERENCE, 0, indices)
    source = lambda i: disposition.generation0(k0[i], k1[i], config.sigma_initial_reseau, config.sigma_initial_autres)
    res = ctx.evaluateur.evaluer(source, n, fenetres).resultats
    return noter(composantes(res, ctx.capital0), config)[0]


def empreinte_noyaux(ctx: Contexte) -> str:
    """Empreinte des textes des noyaux CUDA qui calculent un run : simulateur, genomes, moyennes recursives.

    Un run repris avec d'autres noyaux ne redonne pas un run continu.
    """
    ev = ctx.evaluateur
    textes = (noyau.source(ctx.disposition, ev.fenetres, ev.tables, ev.principal.constantes),
              ctx.disposition.texte_noyaux, LISSER)
    return hashlib.sha256("\n".join(textes).encode("utf-8")).hexdigest()[:16]


def revision() -> str:
    """Revision git du code, marquee si l'arbre de travail differe du commit."""
    tete = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, encoding="utf-8")
    if tete.returncode != 0:
        return "aucune"
    etat = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, encoding="utf-8")
    return tete.stdout.strip() + ("+modifie" if etat.stdout.strip() else "")


def maintenant() -> datetime:
    return SystemClock().now()


def manifeste(ctx: Contexte, mode: str, source: str | None) -> dict:
    proprietes = torch.cuda.get_device_properties(0)
    return {
        "mode": mode,
        "source": source,
        "date": maintenant(),
        "revision": revision(),
        "noyaux": empreinte_noyaux(ctx),
        "donnees": ctx.config.donnees,
        "empreinte_donnees": ctx.hist.empreinte,
        "barres": len(ctx.hist),
        "barres_comblees": [t.isoformat() for t in ctx.hist.comblees],
        "gpu": proprietes.name,
        "memoire_gpu_mo": proprietes.total_memory // 2**20,
        "torch": torch.__version__,
        "taille_paquet": ctx.evaluateur.taille_paquet,
    }
