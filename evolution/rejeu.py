"""Rejeu exact : le flux d'ordres d'un bot, trace par le simulateur GPU, rejoue dans le grand
livre du moteur, en decimal exact, par le courtier simule existant.

Le rejeu verifie la comptabilite du simulateur barre par barre : tresorerie et position doivent etre egales
a l'unite comptable pres. Les decisions, elles, sont reprises telles quelles : le reseau n'est pas recalcule.
"""
import csv
import ctypes
import json
import os
import signal
from dataclasses import astuple, dataclass, fields
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import torch

from adapters.sim_broker import SimBroker
from engine.domain import Bar, Caps, Decision, Trade, Venue
from engine.journal import Journal
from engine.ledger import Ledger
from engine.pipeline import Pipeline
from evolution.config import Config
from evolution.data import HEURE, Fenetre, Historique
from evolution.genome import MODULES
from evolution.simulator import DECISIONS, ETAT, FERMETURE, OUVERTURE, PROTECTION, RAISONS, SORTIES_RESEAU

MILLION = Decimal(1_000_000)


class PolitiqueRejouee:
    """Tient le role de Policy pour la passe par barre : renvoie la decision tracee a chaque barre."""

    lookback = 1

    def __init__(self, decisions: dict[datetime, Decision]):
        self.decisions = decisions

    def decide(self, view, portfolio) -> Decision:
        return self.decisions[view.bars[-1].time]


@dataclass
class Rejeu:
    conforme: bool
    ecart_max: Decimal  # plus grand ecart de tresorerie entre le simulateur et le grand livre, en monnaie
    barre_ecart: int | None  # premiere barre ou tresorerie ou position different
    capital_final: Decimal
    capital_final_gpu: Decimal
    trades: tuple[Trade, ...]
    capitaux_ouverture: list[Decimal]  # capital total a l'ouverture de chaque trade


def lieu(config: Config, fenetre: Fenetre) -> Venue:
    return Venue(config.pas_de_prix, config.pas_de_quantite, config.notionnel_minimum,
                 Decimal(fenetre.frais) / MILLION, Decimal(fenetre.glissement) / MILLION)


def barres(hist: Historique, fenetre: Fenetre) -> list[Bar]:
    pas = hist.pas_de_prix
    a, b = fenetre.debut, fenetre.fin
    colonnes = [t[a:b].tolist() for t in (hist.ouverture, hist.haut, hist.bas, hist.cloture)]
    volumes = hist.volume[a:b].tolist()
    return [
        Bar(hist.ouverture_de(a + k) + HEURE, *(Decimal(colonne[k]) * pas for colonne in colonnes),
            Decimal(repr(volumes[k])))
        for k in range(b - a)
    ]


def rejouer(hist: Historique, fenetre: Fenetre, trace: dict[str, torch.Tensor], config: Config, nom: str,
            symbole: str, journal: Path | None = None) -> Rejeu:
    """Rejoue un couloir. trace : series (pas,) d'un bot sur cette fenetre, telles que le simulateur les ecrit.

    journal : chemin du journal du moteur, ou None pour n'en garder aucun (verification d'admission).
    """
    venue = lieu(config, fenetre)
    pas_prix, pas_qte = config.pas_de_prix, config.pas_de_quantite
    unite = pas_prix * pas_qte / MILLION
    liste = barres(hist, fenetre)
    t = {nom_serie: serie.tolist() for nom_serie, serie in trace.items()
         if nom_serie in ("decision", "stop", "cible", "quantite", "raison", "cash", "quantite_tenue")}
    decisions = {}
    for k, barre in enumerate(liste):
        code = t["decision"][k]
        caps = Caps(Decimal(t["stop"][k]) * pas_prix, Decimal(t["cible"][k]) * pas_prix)
        if code == OUVERTURE:
            decision = Decision("open", "reseau : achat", quantity=Decimal(t["quantite"][k]) * pas_qte, caps=caps)
        elif code == PROTECTION:
            decision = Decision("protect", "position conservee", caps=caps)
        elif code == FERMETURE:
            decision = Decision("close", RAISONS[t["raison"][k]])
        else:
            decision = Decision("none", "prechauffage" if k < fenetre.prechauffage else "rien")
        decisions[barre.time] = decision
    capital = config.capital_initial
    ledger = Ledger(capital)
    sortie = journal if journal is not None else Path(os.devnull)
    registre = Journal(sortie)
    pipeline = Pipeline(nom, symbole, PolitiqueRejouee(decisions), SimBroker(venue), ledger, registre)
    ecart_max, barre_ecart, ouvertures = Decimal(0), None, []
    try:
        for k, barre in enumerate(liste):
            avant = ledger.cash if ledger.position is None else None
            pipeline.on_bar(barre)
            if avant is not None and ledger.position is not None:
                ouvertures.append(avant)
            cash_gpu = Decimal(t["cash"][k]) * unite
            qte_ledger = ledger.position.quantity if ledger.position is not None else Decimal(0)
            ecart = abs(ledger.cash - cash_gpu)
            ecart_max = max(ecart_max, ecart)
            meme_position = qte_ledger == Decimal(t["quantite_tenue"][k]) * pas_qte
            if barre_ecart is None and (ecart != 0 or not meme_position):
                barre_ecart = k
        pipeline.liquidate("fin des donnees")
    finally:
        registre.close()
    final_gpu = Decimal(t["cash"][len(liste) - 1]) * unite
    tolerance = config.tolerance_rejeu * capital
    conforme = abs(ledger.cash - final_gpu) <= tolerance and ecart_max <= tolerance
    return Rejeu(conforme, ecart_max, barre_ecart, ledger.cash, final_gpu, ledger.trades, ouvertures)


# --- Rejeux dans des processus a part : le grand livre est du Python pur, que le GIL empecherait de
# paralleliser dans des fils. Chaque processus recoit une fois l'historique et la configuration. ---

_CONTEXTE: dict = {}
SOUS_LA_NORMALE = 0x4000  # BELOW_NORMAL_PRIORITY_CLASS de Windows


def initialiser(hist: Historique, config: Config, symbole: str) -> None:
    """Le processus passe en priorite basse : les rejeux ne prennent au fil qui pilote la GPU que le temps
    qu'il laisse. Il ignore Ctrl+C, que Windows envoie a tous les processus de la console : c'est au processus
    principal d'arreter le run, a la fin de la generation, et le rejeu en cours doit pouvoir finir."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if hasattr(os, "nice"):
        os.nice(10)
    else:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p  # un HANDLE a la taille d'un pointeur
        kernel32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        if not kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), SOUS_LA_NORMALE):
            raise ctypes.WinError()
    _CONTEXTE.update(hist=hist, config=config, symbole=symbole)


def verifier(fenetre: Fenetre, trace: dict[str, torch.Tensor], nom: str) -> dict:
    """Rejeu d'admission d'un couloir, dans un processus de rejeu : son resume et sa conformite."""
    r = rejouer(_CONTEXTE["hist"], fenetre, trace, _CONTEXTE["config"], nom, _CONTEXTE["symbole"])
    return {"trimestre": fenetre.nom, "conforme": r.conforme, "ecart_max": str(r.ecart_max),
            "barre_ecart": r.barre_ecart, "trades": len(r.trades)}


def consigner_a_part(fenetre: Fenetre, trace: dict[str, torch.Tensor], nom: str, dossier: Path) -> None:
    """consigner, dans un processus de rejeu."""
    consigner(_CONTEXTE["hist"], fenetre, trace, _CONTEXTE["config"], nom, _CONTEXTE["symbole"], dossier)


def consigner(hist: Historique, fenetre: Fenetre, trace: dict[str, torch.Tensor], config: Config, nom: str,
              symbole: str, dossier: Path) -> Rejeu:
    """Rejoue un couloir et l'ecrit comme un run du moteur : journal.jsonl, trades.csv, summary.json.

    reseau.jsonl y ajoute, barre par barre, les entrees du reseau, ses sorties, sa decision et le capital.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    r = rejouer(hist, fenetre, trace, config, nom, symbole, dossier / "journal.jsonl")
    with (dossier / "trades.csv").open("w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(champ.name for champ in fields(Trade))
        ecrivain.writerows(astuple(trade) for trade in r.trades)
    net = sum((trade.net for trade in r.trades), Decimal(0))
    resume = {
        "capital_initial": config.capital_initial,
        "capital_final": r.capital_final,
        "resultats_nets": net,
        "frais": sum((trade.fees for trade in r.trades), Decimal(0)),
        "trades": len(r.trades),
        "identite": r.capital_final == config.capital_initial + net,
        "capital_final_gpu": r.capital_final_gpu,
        "ecart_max_gpu": r.ecart_max,
        "conforme": r.conforme,
    }
    (dossier / "summary.json").write_text(json.dumps(resume, indent=2, default=str) + "\n", encoding="utf-8")
    noms = [module.NOM for module in MODULES] + list(ETAT)
    unite = config.pas_de_prix * config.pas_de_quantite / MILLION
    series = {nom_serie: trace[nom_serie].tolist() for nom_serie in ("entrees", "probas", "sorties", "decision", "capital")}
    with (dossier / "reseau.jsonl").open("w", encoding="utf-8") as fichier:
        for k in range(fenetre.prechauffage + fenetre.longueur):
            ligne = {
                "time": (hist.ouverture_de(fenetre.debut + k) + HEURE).isoformat(),
                "entrees": dict(zip(noms, series["entrees"][k])),
                "probas": dict(zip(("acheter", "vendre", "conserver"), series["probas"][k])),
                "sorties": dict(zip(SORTIES_RESEAU, series["sorties"][k])),
                "decision": DECISIONS[series["decision"][k]],
                "capital": str(Decimal(series["capital"][k]) * unite),
            }
            fichier.write(json.dumps(ligne) + "\n")
    return r
