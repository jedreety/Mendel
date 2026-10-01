"""Historique horaire, blocs, fenetres et couts, permutation a blanc."""
import csv
import hashlib
import math
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import torch

from evolution import philox
from evolution.config import Config, ppm

HEURE = timedelta(hours=1)
MILLION = 1_000_000


def minuit(jour: date) -> datetime:
    return datetime.combine(jour, time(), tzinfo=UTC)


@dataclass(frozen=True)
class Historique:
    """Barres horaires sur une grille reguliere : la barre i s'ouvre a debut + i heures.

    Prix en pas de prix entiers, exacts ; volume en float64. Une heure absente du fichier est comblee par
    une barre plate au dernier cours, de volume nul : comblees donne leurs ouvertures.
    """

    debut: datetime
    ouverture: torch.Tensor
    haut: torch.Tensor
    bas: torch.Tensor
    cloture: torch.Tensor
    volume: torch.Tensor
    pas_de_prix: Decimal
    comblees: tuple[datetime, ...]
    empreinte: str

    def __len__(self) -> int:
        return self.cloture.shape[0]

    def indice(self, instant: datetime) -> int:
        """Indice de la barre qui s'ouvre a cet instant."""
        return (instant - self.debut) // HEURE

    def ouverture_de(self, i: int) -> datetime:
        return self.debut + i * HEURE


def charger(chemin: Path, pas_de_prix: Decimal, fin: datetime | None) -> Historique:
    """Lit un fichier de data/prepared/ jusqu'a `fin` exclue, en heures d'ouverture.

    `fin` est le debut du bloc de test pour l'entrainement : les barres de test ne sont alors jamais lues.
    Seul le benchmark final passe None, et lit tout.
    """
    with chemin.open("rb") as fichier:
        empreinte = hashlib.file_digest(fichier, "sha256").hexdigest()
    lignes: list[tuple[int, int, int, int, float]] = []
    comblees = []
    debut = None
    with chemin.open(encoding="utf-8", newline="") as fichier:
        for ligne in csv.DictReader(fichier):
            ouverture = datetime.fromisoformat(ligne["time"]) - HEURE
            if fin is not None and ouverture >= fin:
                break
            if debut is None:
                debut = ouverture
            attendue = debut + len(lignes) * HEURE
            if ouverture < attendue:
                raise ValueError(f"{chemin}: barre hors ordre a {ouverture}")
            while attendue < ouverture:
                cours = lignes[-1][3]
                lignes.append((cours, cours, cours, cours, 0.0))
                comblees.append(attendue)
                attendue += HEURE
            prix = []
            for champ in ("open", "high", "low", "close"):
                pas = Decimal(ligne[champ]) / pas_de_prix
                if pas != pas.to_integral_value():
                    raise ValueError(f"{chemin}: {ligne[champ]} hors du pas de prix a {ouverture}")
                prix.append(int(pas))
            lignes.append((*prix, float(ligne["volume"])))
    colonnes = list(zip(*lignes))
    entiers = [torch.tensor(colonne, dtype=torch.int64) for colonne in colonnes[:4]]
    return Historique(debut, *entiers, torch.tensor(colonnes[4], dtype=torch.float64), pas_de_prix,
                      tuple(comblees), empreinte)


@dataclass(frozen=True)
class Fenetre:
    """Une periode notee, precedee de son prechauffage. Indices de l'historique, couts en millioniemes."""

    nom: str
    debut: int
    prechauffage: int
    longueur: int
    frais: int
    glissement: int

    @property
    def fin(self) -> int:
        return self.debut + self.prechauffage + self.longueur


def _fenetre(hist: Historique, nom: str, debut: datetime, fin: datetime, prechauffage: int,
             frais: int, glissement: int) -> Fenetre:
    notee = hist.indice(debut)
    if notee - prechauffage < 0 or hist.indice(fin) > len(hist):
        raise ValueError(f"{nom} : l'historique ne couvre pas {debut} - {fin} et son prechauffage")
    return Fenetre(nom, notee - prechauffage, prechauffage, hist.indice(fin) - notee, frais, glissement)


def fin_entrainement(config: Config) -> date:
    """Le prechauffage de la validation sert de tampon : il n'est note par aucun bloc."""
    return config.debut_validation - timedelta(days=config.prechauffage_jours)


def fin_validation(config: Config) -> date:
    return config.debut_test - timedelta(days=config.prechauffage_jours)


def trimestres(hist: Historique, config: Config, debut: date, fin: date | None) -> list[Fenetre]:
    """Trimestres civils de debut a fin exclue, ou jusqu'a la derniere barre. Couts de reference."""
    limite = minuit(fin) if fin is not None else hist.ouverture_de(len(hist))
    bornes = [minuit(debut)]
    while bornes[-1] < limite:
        jour = bornes[-1].date()
        mois = jour.month + 3 - (jour.month - 1) % 3
        suivant = minuit(date(jour.year + (mois > 12), (mois - 1) % 12 + 1, 1))
        bornes.append(min(suivant, limite))
    heures = config.prechauffage_jours * 24
    frais, glissement = ppm(config.frais_reference), ppm(config.glissement_reference)
    return [
        _fenetre(hist, f"{a.year}-T{(a.month - 1) // 3 + 1}", a, b, heures, frais, glissement)
        for a, b in zip(bornes, bornes[1:])
    ]


_TIRAGES: dict[tuple, list[tuple[int, int, int]]] = {}  # reglages du tirage -> (jour, frais, glissement) par tirage


def renouvellement(config: Config) -> int:
    """Generations entre deux renouvellements : une fenetre du lot change a chaque fois."""
    return max(1, config.renouvellement_lot // config.fenetres_par_lot)


def _tirages(config: Config, nombre: int) -> list[tuple[int, int, int]]:
    """Les `nombre` premiers tirages de fenetres, dans l'ordre : jour de debut, frais et glissement.

    Les W premiers forment le lot de la generation 0. Le tirage d, a partir de W, remplace la fenetre de la place
    (d - W) mod W. Un tirage evite les periodes notees des autres fenetres du lot au moment ou il est fait.
    """
    duree, fenetres = config.duree_fenetre_jours, config.fenetres_par_lot
    jours = (fin_entrainement(config) - config.debut_entrainement).days - duree
    bornes = (tuple(map(ppm, config.frais_entrainement)), tuple(map(ppm, config.glissement_entrainement)))
    cle = (config.graine_maitresse, config.debut_entrainement, jours, duree, fenetres, bornes)
    tirages = _TIRAGES.setdefault(cle, [])
    while len(tirages) < nombre:
        d = len(tirages)
        place = d if d < fenetres else (d - fenetres) % fenetres
        autres = [tirages[_dernier(p, d, fenetres)][0] for p in range(fenetres) if p != place and p < d]
        k0, k1 = philox.cle(config.graine_maitresse, philox.LOT, d, 0)
        for essai in range(100_001):
            jour = philox.entier(k0, k1, essai, 0, jours + 1)
            if all(abs(jour - autre) >= duree for autre in autres):
                break
        else:
            raise ValueError("le bloc d'entrainement est trop court pour ce lot")
        (frais_bas, frais_haut), (gliss_bas, gliss_haut) = bornes
        tirages.append((jour, frais_bas + philox.entier(k0, k1, 0, 1, frais_haut - frais_bas + 1),
                        gliss_bas + philox.entier(k0, k1, 0, 2, gliss_haut - gliss_bas + 1)))
    return tirages[:nombre]


def _dernier(place: int, avant: int, fenetres: int) -> int:
    """Dernier tirage de la place parmi les `avant` premiers : la place p recoit les tirages d = p mod W."""
    return place + fenetres * ((avant - 1 - place) // fenetres)


def _fenetre_tiree(hist: Historique, config: Config, d: int, tirage: tuple[int, int, int]) -> Fenetre:
    jour, frais, glissement = tirage
    debut = minuit(config.debut_entrainement + timedelta(days=jour))
    return _fenetre(hist, f"F{d}", debut, debut + timedelta(days=config.duree_fenetre_jours),
                    config.prechauffage_jours * 24, frais, glissement)


def lot(hist: Historique, config: Config, generation: int) -> list[Fenetre]:
    """Fenetres d'entrainement de la generation, une par place, dans l'ordre des places.

    Toutes les renouvellement(config) generations, la fenetre de la place suivante est remplacee par un nouveau
    tirage : le lot change une fenetre a la fois, et chaque fenetre y reste renouvellement_lot generations.
    Chaque fenetre commence a minuit UTC. Ses frais et son glissement sont tires avec elle, en millioniemes
    entiers, communs a tous les bots de toutes les generations ou elle sert.
    """
    fenetres = config.fenetres_par_lot
    faits = fenetres + generation // renouvellement(config)
    tirages = _tirages(config, faits)
    return [_fenetre_tiree(hist, config, d, tirages[d]) for d in (_dernier(p, faits, fenetres) for p in range(fenetres))]


def confirmation(hist: Historique, config: Config, generation: int) -> list[Fenetre]:
    """Les fenetres sorties du lot le plus recemment, au plus une par place : les candidats au role de parent
    y sont revus. Aucune avant le premier renouvellement.
    """
    fenetres = config.fenetres_par_lot
    faits = fenetres + generation // renouvellement(config)
    sorties = range(max(0, faits - 2 * fenetres), faits - fenetres)
    tirages = _tirages(config, faits)
    return [_fenetre_tiree(hist, config, d, tirages[d]) for d in sorties]


def permuter(hist: Historique, config: Config) -> Historique:
    """Historique a blanc : les barres de chaque annee civile des blocs d'entrainement et
    de validation sont permutees, puis les prix reconstruits a partir de la derniere cloture intacte.

    Une barre est decrite par r = ln(C/C_prec), o = ln(O/C_prec), h = ln(H/C), l = ln(L/C) et son volume.
    """
    ouv, hau, bas, clo = (t.tolist() for t in (hist.ouverture, hist.haut, hist.bas, hist.cloture))
    vol = hist.volume.tolist()
    premiere = hist.indice(minuit(date(config.debut_entrainement.year, 1, 1)))
    if premiere < 1 or hist.ouverture_de(len(hist)) > minuit(config.debut_test):
        raise ValueError("le run a blanc exige un historique avant l'entrainement et arrete au test")
    k_perm = [philox.cle(config.graine_maitresse, philox.PERMUTATION, annee, 0)
              for annee in range(config.debut_entrainement.year, config.debut_test.year)]
    quintuplets = []
    for annee, (k0, k1) in zip(range(config.debut_entrainement.year, config.debut_test.year), k_perm):
        a = max(hist.indice(minuit(date(annee, 1, 1))), premiere)
        b = min(hist.indice(minuit(date(annee + 1, 1, 1))), len(hist))
        barres = [
            (math.log(clo[i] / clo[i - 1]), math.log(ouv[i] / clo[i - 1]), math.log(hau[i] / clo[i]),
             math.log(bas[i] / clo[i]), vol[i])
            for i in range(a, b)
        ]
        for j in range(len(barres) - 1, 0, -1):
            autre = philox.entier(k0, k1, j, 0, j + 1)
            barres[j], barres[autre] = barres[autre], barres[j]
        quintuplets.extend(barres)
    precedente = clo[premiere - 1]
    for decalage, (r, o, h, l, v) in enumerate(quintuplets):
        i = premiere + decalage
        c = precedente * math.exp(r)
        o_i, c_i = round(precedente * math.exp(o)), round(c)
        ouv[i], clo[i] = o_i, c_i
        hau[i] = max(round(c * math.exp(h)), o_i, c_i)
        bas[i] = max(min(round(c * math.exp(l)), o_i, c_i), 1)
        vol[i] = v
        precedente = c
    entiers = [torch.tensor(serie, dtype=torch.int64) for serie in (ouv, hau, bas, clo)]
    return replace(hist, ouverture=entiers[0], haut=entiers[1], bas=entiers[2], cloture=entiers[3],
                   volume=torch.tensor(vol, dtype=torch.float64))
