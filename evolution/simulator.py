"""Simulateur GPU : un noyau CUDA fusionne, evolution/noyau.cu.

Un couloir est un bot sur une fenetre. Le noyau traite un bot par bloc, un fil par neurone cache : les poids
du neurone restent dans les registres du fil pendant toute une tranche de barres, et chaque poids lu sert a
toutes les fenetres du bot. Le calcul se fait bot par bot, dans un ordre fixe : le resultat d'un bot ne
depend ni de la taille du paquet ni de sa place dans le paquet.

Comptabilite exacte, en entiers de 64 bits : prix en pas de prix, quantites en pas de quantite, montants
en unites de pas de prix x pas de quantite / 1 000 000. Un taux en millioniemes y donne donc des frais
exacts, et les arrondis sont ceux du lieu d'execution du moteur : le rejeu dans le grand livre en decimal
retrouve les memes montants.

Une fenetre est parcourue en plusieurs appels du noyau, par tranches de barres : sous Windows, le pilote
interrompt tout noyau qui tient la GPU plus de deux secondes. L'etat des couloirs attend en memoire globale
entre deux tranches. evolution/reference.py fait le meme calcul en operations PyTorch.
"""
from dataclasses import dataclass
from decimal import Decimal

import torch

from evolution import noyau
from evolution.config import Config
from evolution.data import Fenetre
from evolution.genome import MODULES, Disposition, Parametres
from evolution.marche import Marche

MILLION = 1_000_000
PLANCHER = 5  # %, le stop ne descend jamais sous le prix d'entree moins 5 %
CROISSANCE_MAX = 100  # le capital d'un couloir doit pouvoir etre multiplie par 100 sans deborder
# Bots x barres d'un appel du noyau : environ 0,4 s a 33 ns par bot et par barre (RTX 3050 Ti), bien moins que
# les deux secondes au-dela desquelles Windows interrompt un noyau, meme sur une carte ralentie ou partagee.
BOTS_BARRES_PAR_APPEL = 12_000_000
STOP, CIBLE, DUREE, VENTE, FIN = range(5)  # raisons de sortie
RAISONS = ("stop", "prise de gain", "duree", "vente decidee", "fin de fenetre")
RIEN, OUVERTURE, PROTECTION, FERMETURE = range(4)  # decisions a la cloture, pour les traces
DECISIONS = ("rien", "ouverture", "protection", "fermeture")
ETAT = ("en_position", "fraction_engagee", "rendement_latent", "duree", "distance_stop", "distance_prise_de_gain",
        "gain_du_jour", "frais_recents", "trade_1", "trade_2", "trade_3", "trade_4", "trade_5", "drawdown",
        "heure_sinus", "heure_cosinus", "jour_sinus", "jour_cosinus")  # entrees d'etat, dans l'ordre du reseau
SORTIES_RESEAU = ("taille", "stop", "prise_de_gain", "duree")
# dd_fin et dd_pic : capital et pic de la barre du plus fort drawdown, compares exactement d'une barre a l'autre.
ENTIERS = ("cash", "qte", "prix_entree", "frais_entree", "risque0", "capital_ouv", "duree", "duree_max", "stop",
           "cible", "jour_ref", "pic", "frais_cum", "capital_prec", "nb", "gagnants", "frais_total", "rotation",
           "dd_fin", "dd_pic")
TRACES_ENTIERES = ("capital", "cash", "decision", "raison", "quantite", "quantite_tenue", "prix", "stop", "cible",
                   "prix_repos", "raison_repos")


@dataclass
class Resultats:
    """Comptes de chaque couloir en fin de fenetre, sur le processeur, en forme (bots, fenetres)."""

    capital_final: torch.Tensor  # unites comptables
    trades: torch.Tensor
    gagnants: torch.Tensor
    somme_r: torch.Tensor  # resultats nets des trades, en fraction du capital a l'ouverture
    somme_r2: torch.Tensor
    drawdown: torch.Tensor
    ruine: torch.Tensor
    sorties: torch.Tensor  # (bots, fenetres, 5), par raison
    frais: torch.Tensor
    rotation: torch.Tensor  # notionnel echange, achats et ventes
    moments: torch.Tensor | None  # (bots, fenetres, 4) : sommes des rendements horaires, puissances 1 a 4
    trace: dict | None


class Simulateur:
    def __init__(self, marche: Marche, disposition: Disposition, tables: list, config: Config,
                 bots: int, fenetres: int, pas_max: int, trace: str | None = None, bots_traces: int | None = None):
        """trace : None, "positions" (fraction engagee a chaque barre) ou "complet" (tout, pour le rejeu).

        bots_traces : nombre de premiers bots du paquet dont la trace est gardee, tous par defaut.
        Les moments des rendements horaires, qui servent au ratio de Sharpe, ne sont tenus qu'avec une trace.
        """
        self.marche, self.disposition = marche, disposition
        self.B, self.W = bots, fenetres
        self.L = L = bots * fenetres
        H, E = disposition.cachee, disposition.entrees
        S, K = disposition.signaux, disposition.canaux
        unite = config.pas_de_prix * config.pas_de_quantite / MILLION
        self.unite = unite
        self.capital0 = entier(config.capital_initial / unite)
        if self.capital0 * CROISSANCE_MAX >= 2**63:
            raise ValueError("pas trop fins : le capital ne tiendrait plus en entiers de 64 bits")
        self.bots_traces = bots if bots_traces is None else bots_traces
        self.trace_mode = trace
        dev = marche.appareil
        z = lambda *forme, dtype=torch.float32: torch.zeros(forme, dtype=dtype, device=dev)
        i64 = torch.int64
        self.nb_genes = sum(len(module.GENES) for module in MODULES)
        # Parametres des bots, puis des couloirs.
        self.p = z(bots, S, K)  # projection des signaux des modules en canaux
        self.w, self.b = z(bots, E + H, H), z(bots, H)
        self.w_sortie, self.b_sortie = z(bots, H, 4), z(bots, 4)
        self.w_action0, self.b_action = z(bots, H, 3), z(bots, 3)
        self.adapt = z(4, bots, H, 3)  # a, b, c et d, deja multiplies par eta
        self.genes = z(bots, self.nb_genes)
        self.decision = z(bots, 5)  # seuil d'action, f_max, gamma, stop_max_propre, tp_max
        self.periode_atr = z(bots, dtype=i64)
        self.fenetres = z(5, L, dtype=i64)  # debut, prechauffage, fin, frais, glissement
        # Etat des couloirs, entre deux appels du noyau.
        self.etat64 = z(len(ENTIERS), L, dtype=i64)
        self.etatf = z(7, L, dtype=torch.float64)  # somme_r, somme_r2, drawdown, moments 1 a 4
        self.ruine = z(L, dtype=i64)
        self.sorties = z(5, L, dtype=i64)
        self.anneau = z(24, L, dtype=i64)  # frais cumules a la fin de chacune des 24 dernieres barres
        self.derniers = z(5, L)
        self.h, self.wa, self.ho, self.yo = z(L, H), z(L, H, 3), z(L, H), z(L, 3)
        self.traces: dict[str, torch.Tensor] = {}
        Lt = self.bots_traces * fenetres
        if trace is not None:
            self.traces["fraction"] = z(pas_max, Lt)
        if trace == "complet":
            for nom in TRACES_ENTIERES:
                self.traces[nom] = z(pas_max, Lt, dtype=i64)
            self.traces["probas"] = z(pas_max, Lt, 3)
            self.traces["sorties"] = z(pas_max, Lt, 4)
            self.traces["entrees"] = z(pas_max, Lt, S + E - K)  # signaux des modules, puis entrees d'etat
        self.constantes = {
            "ADAPTATION": int(config.adaptation_en_vie), "TRACE": int(trace is not None),
            "COMPLET": int(trace == "complet"), "DUREE_BARRES": config.duree_max_barres,
            "NOTIONNEL_MIN": entier(config.notionnel_minimum / unite),
            "SEUIL_RUINE": entier(config.capital_initial * config.seuil_ruine / unite),
            "PAS_DE_PRIX": float(config.pas_de_prix),
        }
        self.noyau = noyau.compiler(disposition, fenetres, tables, self.constantes)
        self.marche_d = noyau.descripteur_marche(marche, tables)
        self.paquet_d = noyau.descripteur({
            "L": L, "B": bots, "W": self.w, "W_SORTIE": self.w_sortie, "B_CACHE": self.b, "B_SORTIE": self.b_sortie,
            "B_ACTION": self.b_action, "ADAPT": self.adapt, "GENES": self.genes, "DECISION": self.decision,
            "PROJ": self.p,
            "PERIODE_ATR": self.periode_atr, "FENETRES": self.fenetres, "ETAT64": self.etat64, "ETATF": self.etatf,
            "RUINE": self.ruine, "SORTIES": self.sorties, "ANNEAU": self.anneau, "DERNIERS": self.derniers,
            "H": self.h, "WA": self.wa, "HO": self.ho, "YO": self.yo,
            "T_FRACTION": self.traces.get("fraction", 0), "LT": Lt if trace is not None else 0,
            **{f"T_{nom.upper()}": self.traces.get(nom, 0) for nom in (*TRACES_ENTIERES, "probas", "sorties", "entrees")},
        }, noyau.PAQUET, dev)
        self.tranche = max(1, BOTS_BARRES_PAR_APPEL // bots)
        self.n = 0

    # --- Chargement d'un paquet ---

    def ecrire(self, ligne: int, p: Parametres):
        """Place des bots decodes aux lignes [ligne, ligne + n) du paquet."""
        n = p.w.shape[0]
        bots = slice(ligne, ligne + n)
        self.p[bots] = p.p
        self.w[bots] = p.w
        self.b[bots] = p.b
        self.w_sortie[bots] = p.w_sortie[:, :, 3:]
        self.b_sortie[bots] = p.b_sortie[:, 3:]
        self.w_action0[bots] = p.w_sortie[:, :, :3]
        self.b_action[bots] = p.b_sortie[:, :3]
        eta = p.adaptation["eta"]
        for rang, nom in enumerate(("a", "b", "c", "d")):
            self.adapt[rang, bots] = eta * p.adaptation[nom]
        colonnes = [decodes[gene.nom].float() for module, decodes in zip(MODULES, p.modules) for gene in module.GENES]
        self.genes[bots] = torch.stack(colonnes, 1)
        self.decision[bots] = torch.stack([p.decision[nom].float() for nom in
                                           ("seuil_action", "f_max", "gamma", "stop_max_propre", "tp_max")], 1)
        self.periode_atr[bots] = p.decision["periode_atr"]

    def completer(self, n: int, fenetres: list[Fenetre] | list[list[Fenetre]]):
        """Complete le paquet par des copies du premier bot, pose les fenetres et remet l'etat a zero.

        fenetres : une liste commune a tous les bots, ou une liste par bot.
        """
        self.n = n
        if n < self.B:
            for t in (self.p, self.w, self.b, self.w_sortie, self.b_sortie, self.w_action0, self.b_action,
                      self.genes, self.decision, self.periode_atr):
                t[n:] = t[:1]
            self.adapt[:, n:] = self.adapt[:, :1]
        vide = Fenetre("vide", 0, 0, 0, 0, 0)
        par_bot = fenetres if fenetres and isinstance(fenetres[0], list) else [fenetres]
        lignes = [(liste + [vide] * self.W)[:self.W] for liste in par_bot]
        lignes += [lignes[0]] * (self.B - len(lignes)) if len(lignes) > 1 else []
        valeurs = torch.tensor([[(f.debut, f.prechauffage, f.prechauffage + f.longueur, f.frais, f.glissement)
                                 for f in ligne] for ligne in lignes], dtype=torch.int64).view(-1, 5)
        if len(lignes) == 1:
            valeurs = valeurs.repeat(self.B, 1)
        self.fenetres.copy_(valeurs.T.to(self.fenetres.device))
        self._remettre()

    def _remettre(self):
        for t in (self.etat64, self.etatf, self.ruine, self.sorties, self.anneau, self.derniers, self.h, self.ho,
                  self.yo, *self.traces.values()):
            t.zero_()
        for nom in ("cash", "jour_ref", "pic", "capital_prec"):
            self.etat64[ENTIERS.index(nom)].fill_(self.capital0)
        self.wa.copy_(self.w_action0.repeat_interleave(self.W, dim=0))

    # --- Execution ---

    def executer(self, pas: int) -> Resultats:
        grille, bloc = (self.B, 1, 1), (self.disposition.cachee, 1, 1)
        for debut in range(0, pas, self.tranche):
            self.noyau(grid=grille, block=bloc, args=[self.marche_d, self.paquet_d, debut, min(self.tranche, pas - debut)])
        return self._resultats(pas)

    def _resultats(self, pas: int) -> Resultats:
        n, W = self.n, self.W
        pic = self.etat64[ENTIERS.index("pic")]
        if int(pic.max()) >= self.capital0 * CROISSANCE_MAX:
            raise OverflowError("un couloir a depasse la croissance que la comptabilite entiere garantit")
        forme = lambda t: t.view(self.B, W, *t.shape[1:])[:n].cpu()
        champ = lambda nom: forme(self.etat64[ENTIERS.index(nom)])
        trace = None
        if self.traces:
            gardes = min(n, self.bots_traces)
            trace = {nom: t[:pas].view(pas, self.bots_traces, W, *t.shape[2:])[:, :gardes].cpu()
                     for nom, t in self.traces.items()}
        return Resultats(
            champ("cash"), champ("nb"), champ("gagnants"), forme(self.etatf[0]), forme(self.etatf[1]),
            forme(self.etatf[2]), forme(self.ruine.bool()), forme(self.sorties.T.contiguous()), champ("frais_total"),
            champ("rotation"), forme(self.etatf[3:7].T.contiguous()) if self.trace_mode is not None else None, trace,
        )


def entier(montant: Decimal) -> int:
    if montant != montant.to_integral_value():
        raise ValueError(f"{montant} n'est pas un nombre entier d'unites comptables")
    return int(montant)
