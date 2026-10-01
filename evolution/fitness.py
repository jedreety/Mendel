"""Notation des bots : une note absolue, en unites de croissance du capital.

Par fenetre, la croissance du capital en logarithme, frais et glissement compris, moins penalite_chute fois le
carre de sa pire chute, elle aussi en logarithme. Les fenetres s'agregent par leur moyenne et la pire d'entre
elles. Un gain ne compte en entier que prouve par assez de trades : il est multiplie par n / (n + k), n les
trades des fenetres, k trades_preuve par fenetre. Un bot qui trade en moyenne moins de trades_minimum par
fenetre perd la part correspondante de penalite_inactivite.

Un bot qui ne trade pas a donc -penalite_inactivite, un bot qui perd une note plus basse, un bot qui gagne
regulierement, avec beaucoup de trades a l'appui, une note positive. La meme formule sert a l'entrainement, a la
validation et au test : les notes se comparent d'un bot, d'une generation et d'un run a l'autre.

Les calculs se font sur le processeur, en float64 : ils portent sur quelques dizaines de milliers de
nombres et doivent etre deterministes.
"""
import torch

from evolution.config import Config
from evolution.simulator import Resultats

COMPOSANTES = ("croissance", "chute", "preuve", "activite")  # parts de la note : leur somme est la note
CHUTE_MAX = 1 - 1e-12  # une chute totale reste finie : la note d'un bot ruine est tres basse, pas infinie


def composantes(res: Resultats, capital0: int) -> torch.Tensor:
    """(bots, fenetres, 3) : croissance du capital et pire chute, en logarithme, puis trades fermes."""
    croissance = torch.log(res.capital_final.double().clamp(min=1) / capital0)
    chute = -torch.log1p(-res.drawdown.double().clamp(max=CHUTE_MAX))
    return torch.stack((croissance, chute, res.trades.double()), 2)


def _notes_fenetres(comp: torch.Tensor, config: Config) -> torch.Tensor:
    return comp[..., 0] - config.penalite_chute * comp[..., 1] ** 2


def _preuve_et_activite(n: torch.Tensor, fenetres: int, config: Config) -> tuple[torch.Tensor, torch.Tensor]:
    """Part du gain retenue, et penalite d'inactivite, pour n trades sur ces fenetres."""
    preuve = n / (n + config.trades_preuve * fenetres)
    inactivite = config.penalite_inactivite * (1 - n / (config.trades_minimum * fenetres)).clamp(min=0)
    return preuve, inactivite


def noter(comp: torch.Tensor, config: Config) -> tuple[torch.Tensor, torch.Tensor]:
    """Note finale de chaque bot, et note de chacune de ses fenetres."""
    par_fenetre = _notes_fenetres(comp, config)
    brute = config.agregation["moyenne"] * par_fenetre.mean(1) + config.agregation["minimum"] * par_fenetre.amin(1)
    preuve, inactivite = _preuve_et_activite(comp[..., 2].sum(1), comp.shape[1], config)
    return torch.where(brute > 0, brute * preuve, brute) - inactivite, par_fenetre


def parts(comp: torch.Tensor, bot: int, config: Config) -> list[float]:
    """Part de chaque composante dans la note d'un bot, dans l'ordre de COMPOSANTES : leur somme est sa note.

    La croissance et la chute sont agregees comme la note, la pire fenetre etant celle de la note la plus basse.
    La preuve est ce que le manque de trades retire a un gain ; l'activite, la penalite d'inactivite.
    """
    croissance, chute, trades = comp[bot].unbind(1)
    pire = int(_notes_fenetres(comp[bot], config).argmin())
    moyenne, minimum = config.agregation["moyenne"], config.agregation["minimum"]
    carre = chute ** 2
    part_croissance = moyenne * croissance.mean() + minimum * croissance[pire]
    part_chute = -config.penalite_chute * (moyenne * carre.mean() + minimum * carre[pire])
    brute = part_croissance + part_chute
    preuve, inactivite = _preuve_et_activite(trades.sum(), comp.shape[1], config)
    part_preuve = brute * (preuve - 1) if brute > 0 else torch.zeros((), dtype=torch.float64)
    return [float(part_croissance), float(part_chute), float(part_preuve), float(-inactivite)]


def rangs_contre(valeurs: torch.Tensor, reference: torch.Tensor) -> torch.Tensor:
    """Rang centile de chaque valeur dans une population de reference : part des valeurs inferieures, la
    moitie des egales comptee.
    """
    tri = torch.sort(reference).values
    valeurs = valeurs.contiguous()
    dessous = torch.searchsorted(tri, valeurs, right=False).double()
    jusqua = torch.searchsorted(tri, valeurs, right=True).double()
    return (dessous + (jusqua - dessous) / 2) / reference.shape[0]
