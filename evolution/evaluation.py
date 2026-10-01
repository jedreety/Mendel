"""Evaluation de populations sur la GPU : paquets, calibrage de la memoire, genomes produits a la volee.

Un genome n'existe sur la GPU que le temps d'etre decode dans un paquet : une population entiere ne tient
pas en memoire, ses cles Philox si.
"""
from collections.abc import Callable
from dataclasses import dataclass

import torch

from evolution.config import Config
from evolution.data import Fenetre
from evolution.genome import GROUPES, Disposition
from evolution.marche import Marche
from evolution.simulator import Resultats, Simulateur

Source = Callable[[torch.Tensor], torch.Tensor]  # genomes des bots d'indices donnes, sur la GPU
TRIMESTRES = 4  # trimestres de la validation et du test
BLOC_GENOMES = 2048  # genomes produits d'un coup
# Au-dela, le noyau ne gagne plus rien : une RTX 3050 Ti fait avancer 120 bots ensemble (6 par SM, 20 SM), un
# paquet de 16 384 bots en fait plus de 130 vagues. Et sous Windows, deborder de la memoire de la carte vers la
# memoire partagee triple le cout.
PAQUET_MAX = 16384
POSITIONS_MAX = 512  # lignes du paquet des candidats : chacun y passe sur le lot, la confirmation et la validation
COMPLETS_MAX = 8  # bots d'un paquet trace en entier


@dataclass
class Evaluation:
    resultats: Resultats
    sigma_moyen: dict[str, float]


class Evaluateur:
    def __init__(self, marche: Marche, tables: list, disposition: Disposition, config: Config,
                 taille_paquet: int | None = None):
        """taille_paquet : None pour la calibrer sur la memoire de la GPU, ou la valeur d'un run repris."""
        self.marche, self.tables, self.disposition, self.config = marche, tables, disposition, config
        self.fenetres = max(config.fenetres_par_lot, TRIMESTRES)
        self.pas_max = 24 * (max(config.duree_fenetre_jours, 92) + config.prechauffage_jours)
        simulateur = lambda bots, trace=None, gardes=None: Simulateur(
            marche, disposition, tables, config, bots, self.fenetres, self.pas_max, trace, gardes)
        self.positions = simulateur(POSITIONS_MAX, "positions")
        self.complet = simulateur(COMPLETS_MAX, "complet")
        self._simulateur = simulateur
        self.taille_paquet = taille_paquet or self._calibrer()
        self.principal = simulateur(self.taille_paquet)

    def _calibrer(self) -> int:
        """Plus grand paquet qui tient dans la part de memoire allouee, par pas de 256 bots.

        Le pic de memoire est mesure sur deux paquets : leur ecart donne le cout d'un bot de plus, sans les
        couts fixes. Le resultat ne depend que de la GPU et de la configuration :
        deux runs sur la meme machine ont le meme paquet.
        """
        pics = {}
        for essai in (2048, 4096):
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            avant = torch.cuda.memory_allocated()
            torch.cuda.reset_peak_memory_stats()
            sim = self._simulateur(essai)
            self._remplir(sim, lambda i: self.disposition.generation0(i, i, 0.005, 0.05), 0, essai, None)
            sim.completer(essai, [])
            sim.executer(1)
            torch.cuda.synchronize()
            pics[essai] = torch.cuda.max_memory_allocated() - avant
            del sim
        torch.cuda.empty_cache()
        par_bot = (pics[4096] - pics[2048]) / 2048
        fixe = pics[2048] - 2048 * par_bot
        total = torch.cuda.get_device_properties(0).total_memory
        disponible = self.config.memoire_gpu_max * total - torch.cuda.memory_allocated() - fixe
        paquet = min(int(disponible / (par_bot * 1.1)) // 256 * 256, PAQUET_MAX)
        if paquet < 256:
            raise MemoryError("la GPU n'a pas la memoire d'un paquet de 256 bots")
        paquets = -(-self.config.population // paquet)  # des paquets egaux plutot qu'un dernier presque vide
        return -(-self.config.population // paquets // 256) * 256

    def _remplir(self, sim: Simulateur, source: Source, debut: int, fin: int, sommes: torch.Tensor | None):
        for a in range(debut, fin, BLOC_GENOMES):
            b = min(a + BLOC_GENOMES, fin)
            genomes = source(torch.arange(a, b, device=self.marche.appareil))
            if sommes is not None:
                sommes += genomes[:, :len(GROUPES)].double().sum(0)
            sim.ecrire(a - debut, self.disposition.decoder(genomes))

    def evaluer(self, source: Source, n: int, fenetres: list[Fenetre]) -> Evaluation:
        """Comptes de fin de fenetre de n bots, par paquets du simulateur principal."""
        pas = max(f.prechauffage + f.longueur for f in fenetres)
        sommes = torch.zeros(len(GROUPES), dtype=torch.float64, device=self.marche.appareil)
        morceaux = []
        for debut in range(0, n, self.taille_paquet):
            fin = min(debut + self.taille_paquet, n)
            self._remplir(self.principal, source, debut, fin, sommes)
            self.principal.completer(fin - debut, fenetres)
            morceaux.append(_tronquer(self.principal.executer(pas), len(fenetres)))
        sigma = dict(zip(GROUPES, (sommes / n).tolist()))
        return Evaluation(_concatener(morceaux), sigma)

    def candidats(self, genomes: torch.Tensor, lot: list[Fenetre], revues: list[Fenetre],
                  trimestres: list[Fenetre]) -> tuple[torch.Tensor, Resultats, Resultats]:
        """Les candidats au role de parent, en un seul paquet. Chacun y figure sur le lot, pour
        sa serie de positions, sur les fenetres de confirmation s'il y en a, et sur les trimestres de validation.

        Renvoie les series de positions sur le lot ; les comptes sur le lot puis sur les fenetres de
        confirmation, bout a bout ; et les resultats traces en validation.
        """
        listes = [lot] + ([revues] if revues else []) + [trimestres]
        pas = max(f.prechauffage + f.longueur for liste in listes for f in liste)
        part = POSITIONS_MAX // len(listes)
        series, revus, validations = [], [], []
        for debut in range(0, genomes.shape[0], part):
            morceau = genomes[debut:debut + part].to(self.marche.appareil)
            m = morceau.shape[0]
            parametres = self.disposition.decoder(morceau)
            for rang in range(len(listes)):
                self.positions.ecrire(rang * m, parametres)
            self.positions.completer(len(listes) * m, [liste for liste in listes for _ in range(m)])
            res = self.positions.executer(pas)
            parties = [_tronquer(_lignes(res, rang * m, (rang + 1) * m), len(liste)) for rang, liste in enumerate(listes)]
            series.append(_notees(parties[0].trace["fraction"], lot))
            revus.append(_bout_a_bout(parties[:-1]))
            validations.append(parties[-1])
        return torch.cat(series), _concatener(revus), _concatener(validations, garder_trace=True)

    def traces(self, genomes: torch.Tensor, fenetres: list[Fenetre]) -> list[Resultats]:
        """Evaluation tracee en entier de chaque genome, pour la validation, le rejeu et le benchmark."""
        pas = max(f.prechauffage + f.longueur for f in fenetres)
        sorties = []
        for debut in range(0, genomes.shape[0], COMPLETS_MAX):
            morceau = genomes[debut:debut + COMPLETS_MAX].to(self.marche.appareil)
            self.complet.ecrire(0, self.disposition.decoder(morceau))
            self.complet.completer(morceau.shape[0], fenetres)
            sorties.append(_tronquer(self.complet.executer(pas), len(fenetres)))
        return sorties


def _notees(fraction: torch.Tensor, fenetres: list[Fenetre]) -> torch.Tensor:
    """(pas, bots, fenetres) -> (bots, barres notees de toutes les fenetres)."""
    return torch.cat([fraction[f.prechauffage:f.prechauffage + f.longueur, :, w].T
                      for w, f in enumerate(fenetres)], dim=1)


def notees(trace: dict, fenetres: list[Fenetre], nom: str = "fraction") -> torch.Tensor:
    return _notees(trace[nom], fenetres)


def _tronquer(res: Resultats, fenetres: int) -> Resultats:
    """Garde les fenetres utilisees : un paquet peut en porter plus que le travail n'en demande."""
    champs = {}
    for nom in Resultats.__dataclass_fields__:
        valeur = getattr(res, nom)
        if nom == "trace":
            champs[nom] = None if valeur is None else {cle: t[:, :, :fenetres] for cle, t in valeur.items()}
        else:
            champs[nom] = None if valeur is None else valeur[:, :fenetres]
    return Resultats(**champs)


def _lignes(res: Resultats, debut: int, fin: int) -> Resultats:
    """Les bots [debut, fin) de resultats ; les traces sont en forme (pas, bots, fenetres, ...)."""
    champs = {}
    for nom in Resultats.__dataclass_fields__:
        valeur = getattr(res, nom)
        if nom == "trace":
            champs[nom] = None if valeur is None else {cle: t[:, debut:fin] for cle, t in valeur.items()}
        else:
            champs[nom] = None if valeur is None else valeur[debut:fin]
    return Resultats(**champs)


def lignes(res: Resultats, indices: list[int]) -> Resultats:
    """Resultats des bots d'indices donnes, dans cet ordre."""
    return _concatener([_lignes(res, i, i + 1) for i in indices], garder_trace=True)


def _bout_a_bout(parties: list[Resultats]) -> Resultats:
    """Les memes bots sur plusieurs listes de fenetres : leurs comptes, fenetres mises bout a bout, sans trace."""
    champs = {}
    for nom in Resultats.__dataclass_fields__:
        valeurs = [getattr(p, nom) for p in parties]
        champs[nom] = None if nom == "trace" or valeurs[0] is None else torch.cat(valeurs, dim=1)
    return Resultats(**champs)


def _concatener(morceaux: list[Resultats], garder_trace: bool = False) -> Resultats:
    champs = {}
    for nom in Resultats.__dataclass_fields__:
        valeurs = [getattr(m, nom) for m in morceaux]
        if valeurs[0] is None:
            champs[nom] = None
        elif nom == "trace":
            champs[nom] = {cle: torch.cat([v[cle] for v in valeurs], dim=1) for cle in valeurs[0]} if garder_trace else None
        else:
            champs[nom] = torch.cat(valeurs)
    return Resultats(**champs)
