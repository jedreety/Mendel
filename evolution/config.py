"""Configuration du bot evolutif, lue dans un fichier TOML ou chaque parametre figure."""
import tomllib
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal

MILLIONIEME = Decimal("0.000001")


@dataclass(frozen=True)
class Config:
    """Parametres du systeme d'entrainement. Ils ne mutent pas.

    Les montants et les taux sont des Decimal : les couts deviennent des entiers de millioniemes, et la
    comptabilite reste exacte.
    """

    donnees: str
    debut_entrainement: date
    debut_validation: date
    debut_test: date
    fenetres_par_lot: int
    duree_fenetre_jours: int
    prechauffage_jours: int
    renouvellement_lot: int
    capital_initial: Decimal
    frais_entrainement: tuple[Decimal, Decimal]
    glissement_entrainement: tuple[Decimal, Decimal]
    frais_reference: Decimal
    glissement_reference: Decimal
    pas_de_prix: Decimal
    pas_de_quantite: Decimal
    notionnel_minimum: Decimal
    taille_cachee: int
    canaux_modules: int
    duree_max_barres: int
    adaptation_en_vie: bool
    population: int
    nb_parents: int
    seuil_distinction: float
    candidats_examines: int
    sigma_initial_reseau: float
    sigma_initial_autres: float
    amplitude_marge: float
    mutation_enfant: tuple[float, float]
    mutation_gene: tuple[float, float]
    proba_categoriel: float
    graine_maitresse: int
    penalite_chute: float
    agregation: dict
    trades_preuve: int
    trades_minimum: int
    penalite_inactivite: float
    seuil_ruine: Decimal
    population_reference: int
    memoire_gpu_max: float
    stagnation_max: int
    generations_max: int
    tolerance_rejeu: Decimal


def _convertir(annotation, valeur):
    if annotation is Decimal:
        return Decimal(valeur)
    if annotation is float:
        return float(valeur)
    if annotation is int:  # un booleen est aussi un int en Python : il est refuse
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            return valeur
        raise TypeError(f"{valeur!r} n'est pas un entier")
    if annotation == tuple[Decimal, Decimal]:
        return tuple(Decimal(v) for v in valeur)
    if annotation == tuple[float, float]:
        return tuple(float(v) for v in valeur)
    if annotation is dict:
        return {cle: float(v) for cle, v in valeur.items()}
    if isinstance(valeur, annotation):
        return valeur
    raise TypeError(f"{valeur!r} n'est pas du type {annotation}")


def lire(texte: str) -> Config:
    """Config depuis le texte d'un fichier TOML. Un parametre manquant ou inconnu est une erreur."""
    brut = tomllib.loads(texte, parse_float=Decimal)
    noms = {champ.name for champ in fields(Config)}
    if brut.keys() != noms:
        raise ValueError(f"parametres manquants {sorted(noms - brut.keys())}, inconnus {sorted(brut.keys() - noms)}")
    config = Config(**{champ.name: _convertir(champ.type, brut[champ.name]) for champ in fields(Config)})
    for taux in (*config.frais_entrainement, *config.glissement_entrainement,
                 config.frais_reference, config.glissement_reference):
        ppm(taux)
    if not config.debut_entrainement < config.debut_validation < config.debut_test:
        raise ValueError("les blocs doivent se suivre : entrainement, validation, test")
    if config.population <= config.nb_parents:
        raise ValueError("la population doit depasser le nombre de parents")
    if config.trades_preuve <= 0 or config.trades_minimum <= 0:
        raise ValueError("trades_preuve et trades_minimum sont des entiers strictement positifs")
    if config.amplitude_marge < 1:
        raise ValueError("amplitude_marge vaut au moins 1")
    for nom in ("mutation_enfant", "mutation_gene"):
        bas, haut = getattr(config, nom)
        if not 0 < bas <= haut:
            raise ValueError(f"{nom} : deux bornes strictement positives, la premiere au plus egale a la seconde")
    return config


def ppm(taux: Decimal) -> int:
    """Taux en millioniemes entiers. Un taux plus fin rendrait la comptabilite inexacte."""
    entier = taux / MILLIONIEME
    if entier != entier.to_integral_value():
        raise ValueError(f"{taux} n'est pas un multiple de 0,000001")
    return int(entier)
