"""Bilan d'un bot sur des trimestres : note absolue, rendement horaire, positions.

Sert a la validation des parents a chaque generation et au benchmark final sur le test.
"""
from dataclasses import dataclass

import torch

from evolution import mesures
from evolution.config import Config
from evolution.data import Fenetre
from evolution.evaluation import notees
from evolution.fitness import composantes, noter
from evolution.simulator import RAISONS, Resultats


@dataclass
class Bilan:
    note: float
    notes: list[float]  # par trimestre : croissance moins penalite de chute
    composantes: list[list[float]]  # par trimestre : croissance et chute en logarithme, trades
    ruine: list[bool]  # par trimestre : capital passe sous seuil_ruine
    capitaux: list[float]  # capital final de chaque trimestre, en monnaie
    trades: list[int]
    sorties: list[dict[str, int]]
    frais: list[float]
    rotation: list[float]  # notionnel echange sur le capital initial
    sharpe: float  # par heure, sur les rendements horaires des trimestres mis bout a bout
    sharpe_annualise: float
    asymetrie: float
    kurtosis: float
    heures: int
    serie: torch.Tensor  # fraction engagee a chaque barre notee

    def resume(self) -> dict:
        contenu = {cle: valeur for cle, valeur in self.__dict__.items() if cle != "serie"}
        contenu["psr"] = mesures.psr(self.sharpe, self.heures, self.asymetrie, self.kurtosis)
        return contenu


def bilans(resultats: list[Resultats], fenetres: list[Fenetre], capital0: int, unite: float,
           config: Config) -> list[Bilan]:
    """Un bilan par bot des resultats traces."""
    liste = []
    for res in resultats:
        comp = composantes(res, capital0)
        finales, par_fenetre = noter(comp, config)
        series = notees(res.trace, fenetres)
        for b in range(res.capital_final.shape[0]):
            sommes = res.moments[b].sum(0).tolist()
            heures = sum(f.longueur for f in fenetres)
            moyenne, ecart, asymetrie, kurtosis = mesures.moments(sommes, heures)
            liste.append(Bilan(
                note=float(finales[b]),
                notes=par_fenetre[b].tolist(),
                composantes=comp[b].tolist(),
                ruine=res.ruine[b].tolist(),
                capitaux=(res.capital_final[b].double() * unite).tolist(),
                trades=res.trades[b].tolist(),
                sorties=[dict(zip(RAISONS, s)) for s in res.sorties[b].tolist()],
                frais=(res.frais[b].double() * unite).tolist(),
                rotation=(res.rotation[b].double() / capital0).tolist(),
                sharpe=mesures.sharpe(moyenne, ecart),
                sharpe_annualise=mesures.sharpe_annualise(moyenne, ecart),
                asymetrie=asymetrie,
                kurtosis=kurtosis,
                heures=heures,
                serie=series[b].clone(),
            ))
    return liste
