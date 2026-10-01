"""Genome du bot : disposition des genes, generation 0, mutation et decodage.

Un genome est un vecteur float32. Un enfant se reconstruit a partir du genome de son parent et de sa cle
Philox de 64 bits : seuls les genomes des parents et du Pantheon sont stockes en entier.

Sur la GPU, la generation 0 et la mutation passent par les noyaux de evolution/genome.cu, un bloc par genome.
generation0_reference et muter_reference font le meme calcul en operations PyTorch : les deux voies donnent
les memes genomes, au bit pres.
"""
import math
from dataclasses import dataclass
from pathlib import Path

import torch

from evolution import compilation, philox
from evolution.gene import Gene
from evolution.modules import (
    cassure, croisement, momentum, premiere_bougie, retour_moyenne, rsi, volatilite_relative, volume_relatif,
)
from evolution.modules.regles import REGLES

# Les 8 modules d'origine, puis les regles du moteur. Tous toujours allumes.
MODULES = (premiere_bougie, croisement, rsi, cassure, momentum, volatilite_relative, volume_relatif, retour_moyenne,
           *REGLES)
ETATS = 18  # entrees d'etat du bot
SORTIES = 7  # scores d'acheter, de vendre et de conserver, taille, stop, prise de gain, duree
GROUPES = ("modules", "reseau", "decision", "adaptation")
DECISION = (
    Gene("seuil_action", "reel", 0.34, 0.95),
    Gene("f_max", "reel", 0.01, 1),
    Gene("gamma", "reel", 0.25, 4),
    Gene("stop_max_propre", "reel", 0.5, 20),
    Gene("tp_max", "reel", 0.5, 30),
    Gene("periode_atr", "entier", 5, 100),
)
ADAPTATION = (Gene("eta", "reel", 0, 0.1), Gene("a", "reel", -1, 1), Gene("b", "reel", -1, 1),
              Gene("c", "reel", -1, 1), Gene("d", "reel", -1, 1))
POIDS = Gene("poids", "reel", -5, 5)
REEL, ENTIER, CATEGORIEL, SIGMA = range(4)
CODES = {"reel": REEL, "entier": ENTIER, "categoriel": CATEGORIEL}
TIRE, POIDS_NORMAL, DEMI, AMPLITUDE, AMPLITUDE_RESEAU = range(5)  # role d'un gene a la generation 0 (genome.cu)
SOURCE = Path(__file__).with_name("genome.cu")
FILS = 256  # fils par bloc des noyaux de genome.cu


@dataclass
class Parametres:
    """Genomes decodes en valeurs naturelles, une ligne par bot."""

    modules: list[dict[str, torch.Tensor]]
    decision: dict[str, torch.Tensor]
    adaptation: dict[str, torch.Tensor]  # coefficient -> (bots, cachee, 3)
    p: torch.Tensor  # (bots, signaux, canaux) : les signaux des modules resumes en canaux, entrees du reseau
    w: torch.Tensor  # (bots, entrees + cachee, cachee) : entrees (canaux puis etat) puis etat cache precedent
    b: torch.Tensor  # (bots, cachee)
    w_sortie: torch.Tensor  # (bots, cachee, 7)
    b_sortie: torch.Tensor  # (bots, 7)


def valeur(u: torch.Tensor, gene: Gene) -> torch.Tensor:
    """Valeur naturelle d'un gene a partir de sa valeur stockee."""
    if gene.type == "reel":
        return gene.bas + u * (gene.haut - gene.bas)
    if gene.type == "entier":
        n = int(gene.haut - gene.bas) + 1
        rang = torch.floor(u * n).long()
        return (rang % n if gene.circulaire else rang.clamp(max=n - 1)) + int(gene.bas)
    return u.long()


class Disposition:
    """Place de chaque gene dans le vecteur, pour une taille cachee et un nombre de canaux donnes.

    Ordre : les 4 amplitudes, les genes des modules, ceux de la decision, les coefficients d'adaptation, puis les
    poids du reseau : la projection des signaux en canaux, la couche cachee et la couche de sortie.
    """

    def __init__(self, cachee: int, canaux: int):
        self.cachee, self.canaux = cachee, canaux
        self.signaux = len(MODULES)
        self.entrees = canaux + ETATS
        self.tranches: dict[str, slice] = {}
        self.individuels: list[tuple[str, Gene]] = []
        self._types: list[int] = []
        self._groupes: list[int] = []
        self._categories: list[int] = []
        self._circulaires: list[bool] = []
        for groupe in GROUPES:
            self._ajouter(f"amplitude.{groupe}", 1, SIGMA, 0)
        for module in MODULES:
            for gene in module.GENES:
                self._individuel(f"{module.NOM}.{gene.nom}", gene, 0)
        for gene in DECISION:
            self._individuel(f"decision.{gene.nom}", gene, 2)
        for gene in ADAPTATION:
            self._ajouter(f"adaptation.{gene.nom}", cachee * 3, REEL, 3)
        e, h = self.entrees, cachee
        self._ajouter("reseau.p", self.signaux * canaux, REEL, 1)
        self._ajouter("reseau.w", (e + h) * h, REEL, 1)
        self._ajouter("reseau.b", h, REEL, 1)
        self._ajouter("reseau.w_sortie", h * SORTIES, REEL, 1)
        self._ajouter("reseau.b_sortie", SORTIES, REEL, 1)
        self.taille = len(self._types)
        par_groupe = [sum(1 for t, g in zip(self._types, self._groupes) if g == i and t != SIGMA) for i in range(4)]
        self.par_groupe = dict(zip(GROUPES, par_groupe))
        self._tau = [1 / math.sqrt(n) for n in par_groupe]
        self._ordonnes = [
            (self.tranches[f"{module.NOM}.{a}"].start, self._gene(module, a),
             self.tranches[f"{module.NOM}.{b}"].start, self._gene(module, b))
            for module in MODULES for a, b in module.ORDONNES
        ]
        # Poids tires selon une loi normale a la generation 0 : ecart-type 1/racine(entrees du neurone).
        self._normaux = (("reseau.p", self.signaux), ("reseau.w", e + h), ("reseau.w_sortie", h))
        self.appareil = None

    @staticmethod
    def _gene(module, nom: str) -> Gene:
        return next(gene for gene in module.GENES if gene.nom == nom)

    def _ajouter(self, nom: str, n: int, code: int, groupe: int, categories: int = 0, circulaire: bool = False):
        debut = len(self._types)
        self.tranches[nom] = slice(debut, debut + n)
        self._types += [code] * n
        self._groupes += [groupe] * n
        self._categories += [categories] * n
        self._circulaires += [circulaire] * n

    def _individuel(self, nom: str, gene: Gene, groupe: int):
        self.individuels.append((nom, gene))
        self._ajouter(nom, 1, CODES[gene.type], groupe, len(gene.categories), gene.circulaire)

    def vers(self, appareil: torch.device) -> "Disposition":
        """Descriptions vectorisees des genes, sur l'appareil des calculs."""
        self.appareil = appareil
        types = torch.tensor(self._types, device=appareil)
        self.continu = (types == REEL) | (types == ENTIER)
        self.circulaire = torch.tensor(self._circulaires, device=appareil)
        self.groupe = torch.tensor(self._groupes, device=appareil)
        self.categories = torch.tensor(self._categories, device=appareil, dtype=torch.float32)
        self.categoriel = types == CATEGORIEL
        self.discrets = self.categoriel.nonzero().squeeze(1)
        self.tau = torch.tensor(self._tau, device=appareil)
        if appareil.type == "cuda":
            self._preparer_noyaux(appareil)
        return self

    def _preparer_noyaux(self, appareil: torch.device) -> None:
        """Descriptions des genes pour genome.cu. Les scalaires y sont arrondis en simple comme PyTorch les
        arrondit face a un tenseur float32, et un diviseur devient son inverse, calcule en double.
        """
        octets = lambda valeurs: torch.tensor(valeurs, dtype=torch.uint8, device=appareil)
        self._code8 = octets(self._types)
        self._groupe8 = octets(self._groupes)
        self._circulaire8 = octets(self._circulaires)
        self._discrets32 = self.discrets.to(torch.int32)
        role = [TIRE] * self.taille
        inverse = [0.0] * self.taille
        for nom, entrees in self._normaux:
            for g in range(self.tranches[nom].start, self.tranches[nom].stop):
                role[g], inverse[g] = POIDS_NORMAL, 1 / (math.sqrt(entrees) * (POIDS.haut - POIDS.bas))
        for nom in ("reseau.b", "reseau.b_sortie"):
            for g in range(self.tranches[nom].start, self.tranches[nom].stop):
                role[g] = DEMI
        for groupe in GROUPES:
            role[self.tranches[f"amplitude.{groupe}"].start] = AMPLITUDE_RESEAU if groupe == "reseau" else AMPLITUDE
        self._role0 = octets(role)
        self._inverse0 = torch.tensor(inverse, dtype=torch.float32, device=appareil)
        paires = [[float(ia), float(ib), *_constantes_ordre(ga), *_constantes_ordre(gb)]
                  for ia, ga, ib, gb in self._ordonnes]
        self._paires = torch.tensor(paires or [[0.0] * 12], dtype=torch.float32, device=appareil)
        entete = (f"#define TAILLE {self.taille}\n#define ND {self.discrets.shape[0]}\n"
                  f"#define NPAIRES {len(paires)}\n")
        self.texte_noyaux = entete + SOURCE.read_text(encoding="utf-8")

    def _ordonner(self, x: torch.Tensor) -> torch.Tensor:
        """Si une periode courte depasse la longue, les deux valeurs naturelles sont echangees."""
        for ia, ga, ib, gb in self._ordonnes:
            na, nb = _naturel(x[:, ia], ga), _naturel(x[:, ib], gb)
            echange = na > nb
            ua, ub = _normaliser(nb, ga), _normaliser(na, gb)
            x[:, ia] = torch.where(echange, ua, x[:, ia])
            x[:, ib] = torch.where(echange, ub, x[:, ib])
        return x

    def generation0(self, k0: torch.Tensor, k1: torch.Tensor, sigma_reseau: float, sigma_autres: float) -> torch.Tensor:
        """Bots tires au hasard : chaque gene uniforme dans ses bornes, les poids du reseau selon une loi
        normale d'ecart-type 1/racine(entrees du neurone) puis bornes, les biais nuls.
        """
        if self.appareil is None or self.appareil.type != "cuda":
            return self.generation0_reference(k0, k1, sigma_reseau, sigma_autres)
        n = k0.shape[0]
        sortie = torch.empty(n, self.taille, device=self.appareil)
        if n:
            compilation.compiler(self.texte_noyaux, "generation0")(
                grid=(n, 1, 1), block=(FILS, 1, 1),
                args=[torch.stack((k0, k1), 1).contiguous(), self._code8, self._role0, self.categories, self._inverse0,
                      self._paires, float(sigma_reseau), float(sigma_autres), sortie])
        return sortie

    def generation0_reference(self, k0: torch.Tensor, k1: torch.Tensor, sigma_reseau: float,
                              sigma_autres: float) -> torch.Tensor:
        """Meme tirage que generation0, en operations PyTorch."""
        n = self.taille
        u = philox.uniformes(philox.mots_t(k0, k1, philox.UNIFORMES, n))[:, :n]
        x = torch.where(self.categoriel, torch.floor(u * self.categories), u)
        z = philox.normales(philox.mots_t(k0, k1, philox.NORMALES, n))[:, :n]
        for nom, entrees in self._normaux:
            tranche = self.tranches[nom]
            x[:, tranche] = (0.5 + z[:, tranche] / (math.sqrt(entrees) * (POIDS.haut - POIDS.bas))).clamp(0, 1)
        for nom in ("reseau.b", "reseau.b_sortie"):
            x[:, self.tranches[nom]] = 0.5
        for groupe in GROUPES:
            x[:, self.tranches[f"amplitude.{groupe}"]] = sigma_reseau if groupe == "reseau" else sigma_autres
        return self._ordonner(x)

    def bornes_amplitudes(self, sigma_reseau: float, sigma_autres: float, marge: float) -> torch.Tensor:
        """(2, 4) : amplitude minimale puis maximale de chaque groupe, sa valeur initiale divisee et multipliee
        par la marge. Sans elles, l'amplitude d'un groupe derive au hasard, jusqu'a geler ou disperser ses genes.
        """
        initiales = [sigma_reseau if groupe == "reseau" else sigma_autres for groupe in GROUPES]
        return torch.tensor([[s / marge for s in initiales], [s * marge for s in initiales]], device=self.appareil)

    def muter(self, parents: torch.Tensor, choix: torch.Tensor, k0: torch.Tensor, k1: torch.Tensor,
              proba_categoriel: float, force: tuple[float, float], ampleur: tuple[float, float],
              bornes: torch.Tensor) -> torch.Tensor:
        """Enfants des parents choisis. Les amplitudes mutent d'abord, dans leurs bornes. Puis l'enfant tire sa
        force, et chaque gene son ampleur, de facon log-uniforme entre leurs bornes : x' = x + sigma x force x
        ampleur x N(0, 1) en unites normalisees, sigma etant l'amplitude du groupe du gene, puis bornage ou modulo.
        Un gene categoriel est retire au hasard avec la probabilite proba_categoriel.
        """
        if self.appareil is None or self.appareil.type != "cuda":
            return self.muter_reference(parents, choix, k0, k1, proba_categoriel, force, ampleur, bornes)
        n = k0.shape[0]
        sortie = torch.empty(n, self.taille, device=self.appareil)
        if n:
            compilation.compiler(self.texte_noyaux, "muter")(
                grid=(n, 1, 1), block=(FILS, 1, 1),
                args=[parents.contiguous(), choix.contiguous(), torch.stack((k0, k1), 1).contiguous(), self._code8,
                      self._groupe8, self._circulaire8, self.categories, self._discrets32, self.tau, self._paires,
                      bornes.contiguous(), float(proba_categoriel), *_log_uniforme(force), *_log_uniforme(ampleur),
                      sortie])
        return sortie

    def muter_reference(self, parents: torch.Tensor, choix: torch.Tensor, k0: torch.Tensor, k1: torch.Tensor,
                        proba_categoriel: float, force: tuple[float, float], ampleur: tuple[float, float],
                        bornes: torch.Tensor) -> torch.Tensor:
        """Memes enfants que muter, en operations PyTorch."""
        x = parents.index_select(0, choix)
        n = self.taille
        z_sigma = philox.normales(philox.mots_t(k0, k1, philox.NORMALES_SIGMA, 4))[:, :4]
        sigma = (x[:, :4] * torch.exp(self.tau * z_sigma)).clamp(bornes[0], bornes[1])
        debut, etendue = _log_uniforme(force)
        f = torch.exp(philox.uniformes(philox.mots_t(k0, k1, philox.FORCE, 1))[:, :1] * etendue + debut)
        debut, etendue = _log_uniforme(ampleur)
        a = torch.exp(philox.uniformes(philox.mots_t(k0, k1, philox.AMPLEURS, n))[:, :n] * etendue + debut)
        z = philox.normales(philox.mots_t(k0, k1, philox.NORMALES, n))[:, :n]
        y = x + (sigma * f).index_select(1, self.groupe) * a * z
        y = torch.where(self.circulaire, torch.remainder(y, 1.0), y.clamp(0, 1))
        y = torch.where(self.continu, y, x)
        nd = self.discrets.shape[0]
        u1 = philox.uniformes(philox.mots_t(k0, k1, philox.UNIFORMES, nd))[:, :nd]
        u2 = philox.uniformes(philox.mots_t(k0, k1, philox.UNIFORMES_BIS, nd))[:, :nd]
        xd = x.index_select(1, self.discrets)
        tirage = torch.floor(u2 * self.categories.index_select(0, self.discrets))
        y.index_copy_(1, self.discrets, torch.where(u1 < proba_categoriel, tirage, xd))
        y[:, :4] = sigma
        return self._ordonner(y)

    def decoder(self, x: torch.Tensor) -> Parametres:
        n, e, h = x.shape[0], self.entrees, self.cachee
        naturels = {nom: valeur(x[:, self.tranches[nom].start], gene) for nom, gene in self.individuels}
        modules = [{gene.nom: naturels[f"{module.NOM}.{gene.nom}"] for gene in module.GENES} for module in MODULES]
        decision = {gene.nom: naturels[f"decision.{gene.nom}"] for gene in DECISION}
        adaptation = {gene.nom: valeur(x[:, self.tranches[f"adaptation.{gene.nom}"]], gene).view(n, h, 3)
                      for gene in ADAPTATION}
        poids = lambda nom: valeur(x[:, self.tranches[nom]], POIDS)
        return Parametres(modules, decision, adaptation, poids("reseau.p").view(n, self.signaux, self.canaux),
                          poids("reseau.w").view(n, e + h, h), poids("reseau.b"),
                          poids("reseau.w_sortie").view(n, h, SORTIES), poids("reseau.b_sortie"))

    def lisible(self, genome: torch.Tensor) -> dict:
        """Parametres d'un bot en clair, pour le Pantheon et pour la lecture humaine.

        L'importance d'un module est la norme de sa ligne de projection, rapportee a la plus forte : la force
        avec laquelle son signal entre dans les canaux du reseau.
        """
        p = self.decoder(genome[None].float().cpu())
        modules = {}
        for module, genes in zip(MODULES, p.modules):
            reglages = {}
            for gene in module.GENES:
                v = int(genes[gene.nom][0])
                reglages[gene.nom] = (gene.categories[v] if gene.type == "categoriel"
                                      else float(genes[gene.nom][0]) if gene.type == "reel" else v)
            modules[module.NOM] = reglages
        normes = p.p[0].norm(dim=1)
        importance = dict(zip((module.NOM for module in MODULES), (normes / normes.max().clamp(min=1e-12)).tolist()))
        decision = {gene.nom: (int(p.decision[gene.nom][0]) if gene.type == "entier" else float(p.decision[gene.nom][0]))
                    for gene in DECISION}
        amplitudes = {groupe: float(genome[self.tranches[f"amplitude.{groupe}"].start]) for groupe in GROUPES}
        return {"modules": modules, "importance": importance, "decision": decision, "amplitudes": amplitudes}


def _log_uniforme(bornes: tuple[float, float]) -> tuple[float, float]:
    """ln(bas) et ln(haut) - ln(bas) : exp(ln(bas) + u x etendue) est log-uniforme entre les bornes, u uniforme."""
    bas, haut = bornes
    return math.log(bas), math.log(haut) - math.log(bas)


def _constantes_ordre(gene: Gene) -> list[float]:
    """Pour genome.cu : entier ou non, puis naturel = a + u b et normaliser = ((v - bas) + demi) * inverse."""
    entier = gene.type == "entier"
    etendue = gene.haut - gene.bas + (1 if entier else 0)
    return [float(entier), gene.bas - 0.5 if entier else gene.bas, etendue, gene.bas, 1 / etendue]


def _naturel(u: torch.Tensor, gene: Gene) -> torch.Tensor:
    if gene.type == "entier":
        return gene.bas - 0.5 + u * (gene.haut - gene.bas + 1)
    return gene.bas + u * (gene.haut - gene.bas)


def _normaliser(v: torch.Tensor, gene: Gene) -> torch.Tensor:
    if gene.type == "entier":
        return ((v - gene.bas + 0.5) / (gene.haut - gene.bas + 1)).clamp(0, 1)
    return ((v - gene.bas) / (gene.haut - gene.bas)).clamp(0, 1)
