"""Simulateur de reference, en operations PyTorch.

C'est la specification executable du pas : lisible operation par operation, verifiee contre le rejeu
exact. Le simulateur de production (evolution/simulator.py) fait le meme calcul dans un noyau CUDA fusionne,
bien plus rapide ; evolution/verifier.py compare les deux.

Un couloir est un bot sur une fenetre. Tous les couloirs d'un paquet avancent ensemble, barre apres barre :
chaque pas est vectorise sur les couloirs, sans branchement dependant des donnees, et capture en graphe
CUDA. Les fenetres d'un bot partagent ses poids : une seule lecture des poids par barre pour ses fenetres.

Comptabilite exacte, en entiers de 64 bits : prix en pas de prix, quantites en pas de quantite, montants
en unites de pas de prix x pas de quantite / 1 000 000. Un taux en millioniemes y donne donc des frais
exacts, et les arrondis sont ceux du lieu d'execution du moteur : le rejeu dans le grand livre en decimal
doit retrouver les memes montants.

Trois graphes. Les signaux des modules ne dependent que des genes et des barres, jamais de l'etat du bot :
le graphe des signaux les calcule d'un coup pour un bloc de barres. Le pas se deroule ensuite en deux
graphes. Dans un grand paquet, l'adaptation en cours de vie se fait entre les deux et ne touche que les
couloirs qui viennent de fermer un trade : une passe complete sur les poids de tous les couloirs a chaque
barre couterait plus que le reste. Dans un petit paquet, elle se fait dans le premier graphe, sur tous les
couloirs, avec le meme calcul element par element : les deux voies donnent les memes poids.

Un bot donne le meme resultat dans tout paquet d'au moins PAQUET_MIN bots : au-dessous, cuBLAS change de
noyau pour les produits du reseau et les arrondis changent. Tous les paquets respectent donc ce minimum.
"""
from bisect import bisect_left

import torch

from evolution.config import Config
from evolution.data import Fenetre
from evolution.genome import MODULES, Disposition, Parametres
from evolution.marche import Marche
from evolution.simulator import (
    CIBLE, CROISSANCE_MAX, DUREE, FERMETURE, FIN, MILLION, OUVERTURE, PLANCHER, PROTECTION, RIEN, STOP, VENTE,
    Resultats, entier,
)

ELEMENTS_PAR_BLOC = 2**21  # barres x couloirs calcules d'un coup par le graphe des signaux
PAQUET_MIN = 128  # bots : a partir de la, les noyaux cuBLAS du reseau ne dependent plus de la taille du paquet
ADAPTATION_EN_GRAPHE = 4096  # couloirs : jusque-la, l'adaptation passe sur tous les couloirs, dans le graphe


class SimulateurReference:
    def __init__(self, marche: Marche, disposition: Disposition, tables: list, config: Config,
                 bots: int, fenetres: int, pas_max: int, trace: str | None = None, bots_traces: int | None = None):
        """trace : None, "positions" (fraction engagee a chaque barre) ou "complet" (tout, pour le rejeu).

        bots_traces : nombre de premiers bots du paquet dont la trace est gardee, tous par defaut.
        Les moments des rendements horaires, qui servent au ratio de Sharpe, ne sont tenus qu'avec une trace.
        """
        if bots < PAQUET_MIN:
            raise ValueError(f"un paquet compte au moins {PAQUET_MIN} bots")
        self.marche, self.disposition, self.tables = marche, disposition, tables
        self.adaptation = config.adaptation_en_vie
        self.duree_barres = config.duree_max_barres
        self.trace_mode = trace
        self.B, self.W = bots, fenetres
        self.L = bots * fenetres
        B, W, L = self.B, self.W, self.L
        self.bots_traces = bots if bots_traces is None else bots_traces
        self.adaptation_en_graphe = L <= ADAPTATION_EN_GRAPHE
        H, E = disposition.cachee, disposition.entrees
        S, K = disposition.signaux, disposition.canaux
        self.E, self.S = E, S
        unite = config.pas_de_prix * config.pas_de_quantite / MILLION
        self.unite = unite
        self.capital0 = entier(config.capital_initial / unite)
        self.notionnel_min = entier(config.notionnel_minimum / unite)
        self.seuil_ruine = entier(config.capital_initial * config.seuil_ruine / unite)
        if self.capital0 * CROISSANCE_MAX >= 2**63:
            raise ValueError("pas trop fins : le capital ne tiendrait plus en entiers de 64 bits")
        self.bloc = max(8, min(256, ELEMENTS_PAR_BLOC // L))
        dev = marche.appareil
        f32, i64, f64 = torch.float32, torch.int64, torch.float64
        z = lambda *forme, dtype=f32: torch.zeros(forme, dtype=dtype, device=dev)
        # Poids par bot. xh porte les entrees du reseau suivies de son etat cache : h en est une vue.
        self.p = z(B, S, K)  # projection des signaux des modules en canaux
        self.p_couloir = z(L, S, K)
        self.w, self.b = z(B, E + H, H), z(B, 1, H)
        self.w_sortie, self.b_sortie = z(B, H, 4), z(B, 1, 4)
        self.w_action0, self.b_action = z(B, H, 3), z(B, 1, 3)
        self.adapt = {nom: z(B, H, 3) for nom in ("a", "b", "c", "d")}  # deja multiplies par eta
        # Genes par couloir.
        self.genes = [
            {gene.nom: z(L, dtype=f32 if gene.type == "reel" else i64) for gene in module.GENES} for module in MODULES
        ]
        self.seuil, self.f_max, self.gamma, self.stop_max, self.tp_max = (z(L) for _ in range(5))
        self.bot = {"periode_atr": z(L, dtype=i64)}
        # Fenetres par couloir.
        self.debut, self.prech, self.fin, self.frais, self.gliss = (z(L, dtype=i64) for _ in range(5))
        # Etat. Les poids d'action, h et y memorises ont une ligne de plus que de couloirs : la ligne L recoit
        # les places vides de l'adaptation compacte, sans jamais toucher un couloir.
        self.k = z(dtype=i64)
        self.xh = z(B, W, E + H)
        self.h = self.xh[:, :, E:]
        self.w_plein, self.h_ouv_plein, self.y_ouv_plein, self.r_plein = z(L + 1, H, 3), z(L + 1, H), z(L + 1, 3), z(L + 1)
        self.w_action = self.w_plein[:L].view(B, W, H, 3)
        self.h_ouv = self.h_ouv_plein[:L].view(B, W, H)
        self.y_ouv = self.y_ouv_plein[:L].view(B, W, 3)
        self.nb_fermetures = z(dtype=i64)
        self.capacites = [c for c in (256, 1024, 4096, 16384, 65536) if c < L] + [L]
        (self.cash, self.qte, self.prix_entree, self.frais_entree, self.risque0, self.capital_ouv, self.duree,
         self.duree_max, self.stop, self.cible, self.jour_ref, self.pic, self.frais_cum, self.capital_prec,
         self.nb, self.gagnants, self.frais_total, self.rotation) = (z(L, dtype=i64) for _ in range(18))
        self.somme_r, self.somme_r2, self.dd = z(L, dtype=f64), z(L, dtype=f64), z(L, dtype=f64)
        self.moments = z(L, 4, dtype=f64) if trace is not None else None
        self.ruine = z(L, dtype=torch.bool)
        self.sorties = z(L, 5, dtype=i64)
        self.anneau = z(24, L, dtype=i64)  # frais cumules a la fin de chacune des 24 dernieres barres
        self.derniers = z(L, 5)
        self.ferme_a, self.attente = z(L, dtype=torch.bool), z(L, dtype=torch.bool)
        self.r_a, self.r_attente = z(L), z(L)
        self.i = z(L, dtype=i64)
        self.C = z(L, dtype=i64)
        self.actif, self.note = z(L, dtype=torch.bool), z(L, dtype=torch.bool)
        self.signaux = z(self.bloc, L, len(MODULES) + 1)  # signaux des modules, puis ATR horaire du bot
        self.canaux = z(self.bloc, L, K)  # signaux projetes : les premieres entrees du reseau
        self._bloc = torch.arange(self.bloc, device=dev)
        self._5 = torch.arange(5, device=dev)
        self.pas_de_prix = float(config.pas_de_prix)
        self.traces = {}
        if trace is not None:
            T, Lt = pas_max, self.bots_traces * W
            self.traces["fraction"] = z(T, Lt)
            if trace == "complet":
                for nom in ("capital", "cash", "decision", "raison", "quantite", "quantite_tenue", "prix", "stop",
                            "cible", "prix_repos", "raison_repos"):
                    self.traces[nom] = z(T, Lt, dtype=i64)
                self.traces["entrees"] = z(T, Lt, S + E - K)  # signaux des modules, puis entrees d'etat
                self.traces["probas"] = z(T, Lt, 3)
                self.traces["sorties"] = z(T, Lt, 4)
        self.graphes = None
        self.n = 0

    # --- Chargement d'un paquet ---

    def ecrire(self, ligne: int, p: Parametres):
        """Place des bots decodes aux lignes [ligne, ligne + n) du paquet."""
        n, W = p.w.shape[0], self.W
        bots = slice(ligne, ligne + n)
        couloirs = slice(ligne * W, (ligne + n) * W)
        par_couloir = lambda t: t.repeat_interleave(W)
        self.p[bots] = p.p
        self.p_couloir[couloirs] = p.p.repeat_interleave(W, dim=0)
        self.w[bots] = p.w
        self.b[bots, 0] = p.b
        self.w_sortie[bots] = p.w_sortie[:, :, 3:]
        self.b_sortie[bots, 0] = p.b_sortie[:, 3:]
        self.w_action0[bots] = p.w_sortie[:, :, :3]
        self.b_action[bots, 0] = p.b_sortie[:, :3]
        eta = p.adaptation["eta"]
        for nom in ("a", "b", "c", "d"):
            self.adapt[nom][bots] = eta * p.adaptation[nom]
        for genes, decodes in zip(self.genes, p.modules):
            for nom, tenseur in genes.items():
                tenseur[couloirs] = par_couloir(decodes[nom])
        self.seuil[couloirs] = par_couloir(p.decision["seuil_action"])
        self.f_max[couloirs] = par_couloir(p.decision["f_max"])
        self.gamma[couloirs] = par_couloir(p.decision["gamma"])
        self.stop_max[couloirs] = par_couloir(p.decision["stop_max_propre"])
        self.tp_max[couloirs] = par_couloir(p.decision["tp_max"])
        self.bot["periode_atr"][couloirs] = par_couloir(p.decision["periode_atr"])

    def completer(self, n: int, fenetres: list[Fenetre] | list[list[Fenetre]]):
        """Complete le paquet par des copies du premier bot, pose les fenetres et remet l'etat a zero.

        fenetres : une liste commune a tous les bots, ou une liste par bot.
        """
        self.n = n
        if n < self.B:
            for t in (self.p, self.w, self.b, self.w_sortie, self.b_sortie, self.w_action0, self.b_action,
                      *self.adapt.values()):
                t[n:] = t[:1]
            self.p_couloir[n * self.W:] = self.p_couloir[:self.W].repeat(self.B - n, 1, 1)
            for t in (self.seuil, self.f_max, self.gamma, self.stop_max, self.tp_max, self.bot["periode_atr"],
                      *(v for genes in self.genes for v in genes.values())):
                t[n * self.W:] = t[:self.W].repeat(self.B - n)
        vide = Fenetre("vide", 0, 0, 0, 0, 0)
        par_bot = fenetres if fenetres and isinstance(fenetres[0], list) else [fenetres]
        lignes = [(liste + [vide] * self.W)[:self.W] for liste in par_bot]
        lignes += [lignes[0]] * (self.B - len(lignes)) if len(lignes) > 1 else []
        valeurs = torch.tensor([[(f.debut, f.prechauffage, f.prechauffage + f.longueur, f.frais, f.glissement)
                                 for f in ligne] for ligne in lignes], dtype=torch.int64).view(-1, 5)
        if len(lignes) == 1:
            valeurs = valeurs.repeat(self.B, 1)
        valeurs = valeurs.to(self.k.device)
        for colonne, tenseur in enumerate((self.debut, self.prech, self.fin, self.frais, self.gliss)):
            tenseur.copy_(valeurs[:, colonne])
        self._remettre()

    def _remettre(self):
        self.k.zero_()
        self.xh.zero_()
        for t in (self.w_plein, self.h_ouv_plein, self.y_ouv_plein, self.r_plein, self.nb_fermetures):
            t.zero_()
        self.w_action.copy_(self.w_action0[:, None].expand_as(self.w_action))
        for t in (self.qte, self.prix_entree, self.frais_entree, self.risque0, self.capital_ouv, self.duree,
                  self.duree_max, self.stop, self.cible, self.frais_cum, self.nb, self.gagnants, self.frais_total,
                  self.rotation, self.somme_r, self.somme_r2, self.dd, self.sorties, self.anneau,
                  self.derniers, self.r_a, self.r_attente):
            t.zero_()
        if self.moments is not None:
            self.moments.zero_()
        for t in (self.ruine, self.ferme_a, self.attente):
            t.fill_(False)
        for t in (self.cash, self.jour_ref, self.pic, self.capital_prec):
            t.fill_(self.capital0)
        for t in self.traces.values():
            t.zero_()

    # --- Execution ---

    def executer(self, pas: int) -> Resultats:
        if self.graphes is None:
            self._capturer()
        c, a, b, adaptations = self.graphes
        entre_graphes = self.adaptation and not self.adaptation_en_graphe
        for pas_courant in range(pas):
            if pas_courant % self.bloc == 0:
                c.replay()
            a.replay()
            if entre_graphes:
                n = int(self.nb_fermetures)  # seule synchronisation du pas : combien de couloirs ont ferme
                if n:
                    adaptations[bisect_left(self.capacites, n)].replay()
            b.replay()
        return self._resultats(pas)

    def _capturer(self):
        """Capture les graphes, apres quelques pas d'echauffement sur un flux a part.

        Dans un grand paquet, un graphe d'adaptation par capacite : le plus petit qui contient les
        fermetures de la barre est rejoue.
        """
        entre_graphes = self.adaptation and not self.adaptation_en_graphe
        flux = torch.cuda.Stream()
        flux.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(flux):
            for _ in range(3):
                self._pas_signaux()
                self._pas_a()
                if entre_graphes:
                    for capacite in self.capacites:
                        self._adapter_compact(capacite)
                self._pas_b()
        torch.cuda.current_stream().wait_stream(flux)
        c, a, b = torch.cuda.CUDAGraph(), torch.cuda.CUDAGraph(), torch.cuda.CUDAGraph()
        with torch.cuda.graph(c):
            self._pas_signaux()
        with torch.cuda.graph(a, pool=c.pool()):
            self._pas_a()
        with torch.cuda.graph(b, pool=c.pool()):
            self._pas_b()
        adaptations = []
        if entre_graphes:
            for capacite in self.capacites:
                graphe = torch.cuda.CUDAGraph()
                with torch.cuda.graph(graphe, pool=c.pool()):
                    self._adapter_compact(capacite)
                adaptations.append(graphe)
        self.graphes = (c, a, b, adaptations)
        self._remettre()

    def _pas_signaux(self):
        """Signaux des modules et ATR horaire du bot, pour le bloc de barres qui commence, puis
        leur projection en canaux : produit puis somme, arrondis a part, dans l'ordre des modules, comme le noyau.
        """
        m = self.marche
        i = (self.debut[None, :] + self.k + self._bloc[:, None]).clamp(max=m.n1 - 1)
        colonnes = []
        for module, genes, tables in zip(MODULES, self.genes, self.tables):
            colonnes.append(torch.nan_to_num(module.signal(m, tables, i, genes, self.bot), nan=0.0, posinf=0.0,
                                             neginf=0.0))
        colonnes.append(m.atr_en(self.bot["periode_atr"], i))
        torch.stack(colonnes, 2, out=self.signaux)
        canaux = torch.zeros_like(self.canaux)
        for s in range(self.S):
            canaux = canaux + self.signaux[:, :, s:s + 1] * self.p_couloir[None, :, s, :]
        self.canaux.copy_(canaux)

    def _fermer(self, masque: torch.Tensor, prix: torch.Tensor, raison: torch.Tensor) -> torch.Tensor:
        """Vend toute la position des couloirs masques a `prix`. Renvoie r, en multiples du risque initial."""
        q = self.qte
        brut = prix * q * MILLION
        frais = prix * q * self.frais
        net = (prix - self.prix_entree) * q * MILLION - self.frais_entree - frais
        torch.where(masque, self.cash + brut - frais, self.cash, out=self.cash)
        self.qte.masked_fill_(masque, 0)
        self.nb.add_(masque.long())
        self.gagnants.add_((masque & (net > 0)).long())
        r_capital = net.double() / self.capital_ouv.clamp(min=1).double()
        self.somme_r.add_(torch.where(masque, r_capital, 0.0))
        self.somme_r2.add_(torch.where(masque, r_capital * r_capital, 0.0))
        r = (net.double() / self.risque0.clamp(min=1).double()).clamp(-3, 3).float()
        decale = torch.cat((r[:, None], self.derniers[:, :4]), 1)
        torch.where(masque[:, None], decale, self.derniers, out=self.derniers)
        self.sorties.add_(((self._5 == raison[:, None]) & masque[:, None]).long())
        payes = torch.where(masque, frais, 0)
        self.frais_total.add_(payes)
        self.frais_cum.add_(payes)
        self.rotation.add_(torch.where(masque, brut, 0))
        return torch.where(masque, r, 0.0)

    def _pas_a(self):
        """Debut de la barre : ordres au repos testes contre le plus bas et le plus haut."""
        m = self.marche
        k = self.k
        torch.clamp(self.debut + k, max=m.n1 - 1, out=self.i)
        torch.lt(k, self.fin, out=self.actif)
        torch.logical_and(self.actif, k >= self.prech, out=self.note)
        i = self.i
        o, haut, bas = m.ouv_t.take(i), m.haut_t.take(i), m.bas_t.take(i)
        torch.take(m.clo_t, i, out=self.C)
        en_position = (self.qte > 0) & self.note
        stop = en_position & (bas <= self.stop)
        cible = en_position & ~stop & (haut >= self.cible)
        reference = torch.where(stop, torch.minimum(self.stop, o), self.cible)
        prix = reference * (MILLION - self.gliss) // MILLION
        masque = stop | cible
        r = self._fermer(masque, prix, torch.where(stop, STOP, CIBLE))
        self.ferme_a.copy_(masque)
        self.r_a.copy_(r)
        if self.trace_mode == "complet":
            self._tracer("prix_repos", torch.where(masque, prix, 0))
            self._tracer("raison_repos", torch.where(stop, STOP, torch.where(cible, CIBLE, -1)))
        if self.adaptation and self.adaptation_en_graphe:
            r = torch.where(self.ferme_a, self.r_a, torch.where(self.attente, self.r_attente, 0.0))
            self.w_action.copy_(_adapter(self.w_action, r.view(self.B, self.W, 1, 1), self.h_ouv[..., None],
                                         self.y_ouv[:, :, None, :], *(t[:, None] for t in self.adapt.values())))
            self.attente.fill_(False)
        elif self.adaptation:
            self.nb_fermetures.copy_((self.ferme_a | self.attente).sum())

    def _adapter_compact(self, capacite: int):
        """Adaptation en cours de vie, dans un grand paquet : seuls les couloirs qui ont ferme
        un trade sont lus et reecrits, au plus `capacite` ; les places vides visent la ligne L.

        Une fermeture au repos compte des cette barre ; une fermeture decidee a la cloture precedente
        compte ici aussi, avant le reseau de cette barre : les deux ne peuvent pas coincider.
        """
        L, W = self.L, self.W
        self.r_plein[:L].copy_(torch.where(self.ferme_a, self.r_a, self.r_attente))
        lignes = torch.nonzero_static(self.ferme_a | self.attente, size=capacite, fill_value=L).squeeze(1)
        bots = (lignes // W).clamp(max=self.B - 1)
        r = self.r_plein.index_select(0, lignes)[:, None, None]
        h = self.h_ouv_plein.index_select(0, lignes)[:, :, None]
        y = self.y_ouv_plein.index_select(0, lignes)[:, None, :]
        coef = [t.index_select(0, bots) for t in self.adapt.values()]
        self.w_plein.index_copy_(0, lignes, _adapter(self.w_plein.index_select(0, lignes), r, h, y, *coef))
        self.attente.fill_(False)

    def _pas_b(self):
        """Suite de la barre : entrees, reseau, decision a la cloture, comptes."""
        m = self.marche
        B, W, L, E = self.B, self.W, self.L, self.E
        k, i, C, note = self.k, self.i, self.C, self.note
        en_position = self.qte > 0
        self.duree.add_((en_position & note).long())
        valeur = self.qte * C * MILLION
        capital = self.cash + valeur
        torch.where(m.minuit.take(i) & self.actif, capital, self.jour_ref, out=self.jour_ref)
        case = (k % 24).view(1)
        frais_24h = self.frais_cum - self.anneau.index_select(0, case).squeeze(0)
        pic = torch.maximum(self.pic, capital)
        ligne = self.signaux.index_select(0, (k % self.bloc).view(1)).squeeze(0)
        canaux = self.canaux.index_select(0, (k % self.bloc).view(1)).squeeze(0)
        atr = ligne[:, -1]
        atr_ok = atr > 0
        inverse = torch.where(atr_ok, 1.0 / atr, 0.0)
        # Rapports en simple precision, sur des differences entieres exactes : comme le noyau.
        zero = torch.zeros(L, device=C.device)
        entree = self.prix_entree.clamp(min=1)
        etat = torch.stack([
            en_position.float(),
            valeur.float() / capital.float(),
            torch.where(en_position, (C - entree).float() / entree.float(), zero),
            torch.where(en_position, self.duree.float() / self.duree_barres, zero),
            torch.where(en_position, (C - self.stop).float() * self.pas_de_prix * inverse, zero),
            torch.where(en_position, (self.cible - C).float() * self.pas_de_prix * inverse, zero),
            (capital - self.jour_ref).float() / self.jour_ref.float(),
            frais_24h.float() / capital.float(),
            *self.derniers.unbind(1),
            (pic - capital).float() / pic.float(),
            *m.temps.index_select(0, i).unbind(1),
        ], 1)
        x = torch.cat((canaux, etat), 1)
        self.xh[:, :, :E].copy_(x.view(B, W, E))
        # Reseau recurrent : entrees et etat cache precedent, une lecture des poids pour toutes les fenetres.
        torch.tanh(torch.baddbmm(self.b, self.xh, self.w), out=self.h)
        h = self.h
        sorties = torch.baddbmm(self.b_sortie, h, self.w_sortie).view(L, 4)
        scores = torch.matmul(h.unsqueeze(2), self.w_action).squeeze(2) + self.b_action
        probas = torch.softmax(scores, -1).view(L, 3)
        # Regle d'action : la plus forte probabilite, conserver l'emporte en cas d'egalite.
        classees = torch.stack((probas[:, 2], probas[:, 0], probas[:, 1]), 1)
        choix = classees.argmax(1)
        p = classees.gather(1, choix[:, None]).squeeze(1)
        agit = p >= self.seuil
        achat, vente = agit & (choix == 1), agit & (choix == 2)
        taille = torch.sigmoid(sorties[:, 0])
        k_stop = 0.5 + (self.stop_max - 0.5) * torch.sigmoid(sorties[:, 1])
        k_cible = 0.5 + (self.tp_max - 0.5) * torch.sigmoid(sorties[:, 2])
        duree_voulue = torch.round(1 + (self.duree_barres - 1) * torch.sigmoid(sorties[:, 3])).long()
        # Sorties decidees a la cloture : duree, vente, fin de fenetre. Remplies au cours de cloture.
        derniere = k == self.fin - 1
        garde = (self.qte > 0) & note
        s_duree = garde & (self.duree >= self.duree_max)
        s_vente = garde & ~s_duree & vente
        s_fin = garde & ~s_duree & ~s_vente & derniere
        sortie = s_duree | s_vente | s_fin
        prix_vente = C * (MILLION - self.gliss) // MILLION
        raison = torch.where(s_duree, DUREE, torch.where(s_vente, VENTE, FIN))
        r = self._fermer(sortie, prix_vente, raison)
        self.attente.copy_(sortie & ~derniere)  # apres la derniere barre, la vie du bot est finie
        self.r_attente.copy_(r)
        # Caps : fixes a chaque barre par le reseau, jamais sous le plancher de 5 %.
        garde = (self.qte > 0) & note
        distance = atr.double() * (1 / self.pas_de_prix)  # un produit, comme le noyau : pas de division
        stop_voulu = torch.ceil(C.double() - k_stop.double() * distance).long()
        cible_voulue = torch.ceil(C.double() + k_cible.double() * distance).long()
        plancher = (self.prix_entree * (100 - PLANCHER) + 99) // 100
        maj = garde & atr_ok
        torch.where(maj, torch.maximum(stop_voulu, plancher), self.stop, out=self.stop)
        torch.where(maj, cible_voulue, self.cible, out=self.cible)
        # Ouverture : jamais sur une barre ou une position a ete fermee, ni sur la derniere barre.
        prix_achat = (C * (MILLION + self.gliss) + MILLION - 1) // MILLION
        s = self.seuil
        fraction = self.f_max * taille * ((p - s) / (1 - s)).clamp(min=0) ** self.gamma
        voulue = torch.floor(fraction.double() * self.cash.double() / (prix_achat.double() * MILLION)).long()
        possible = self.cash // (prix_achat * (MILLION + self.frais))
        q = torch.minimum(voulue, possible).clamp(min=0)
        notionnel = prix_achat * q * MILLION
        ouvre = (note & (self.qte == 0) & ~self.ferme_a & ~sortie & ~derniere & achat & atr_ok
                 & (q > 0) & (notionnel >= self.notionnel_min))
        frais = prix_achat * q * self.frais
        stop_ouv = torch.maximum(stop_voulu, (prix_achat * (100 - PLANCHER) + 99) // 100)
        torch.where(ouvre, self.cash, self.capital_ouv, out=self.capital_ouv)
        torch.where(ouvre, self.cash - notionnel - frais, self.cash, out=self.cash)
        torch.where(ouvre, q, self.qte, out=self.qte)
        torch.where(ouvre, prix_achat, self.prix_entree, out=self.prix_entree)
        torch.where(ouvre, frais, self.frais_entree, out=self.frais_entree)
        self.duree.masked_fill_(ouvre, 0)
        torch.where(ouvre, duree_voulue, self.duree_max, out=self.duree_max)
        torch.where(ouvre, stop_ouv, self.stop, out=self.stop)
        torch.where(ouvre, cible_voulue, self.cible, out=self.cible)
        risque = torch.maximum(q * (prix_achat - stop_ouv) * MILLION, notionnel // 1000)
        torch.where(ouvre, risque, self.risque0, out=self.risque0)
        ouvre_bw = ouvre.view(B, W, 1)
        torch.where(ouvre_bw, h, self.h_ouv, out=self.h_ouv)
        torch.where(ouvre_bw, probas.view(B, W, 3), self.y_ouv, out=self.y_ouv)
        payes = torch.where(ouvre, frais, 0)
        self.frais_total.add_(payes)
        self.frais_cum.add_(payes)
        self.rotation.add_(torch.where(ouvre, notionnel, 0))
        # Comptes de fin de barre.
        fin = self.cash + self.qte * C * MILLION
        torch.where(note, torch.maximum(self.pic, fin), self.pic, out=self.pic)
        torch.where(note, torch.maximum(self.dd, 1 - fin.double() / self.pic.double()), self.dd, out=self.dd)
        self.ruine.logical_or_(note & (fin < self.seuil_ruine))
        if self.moments is not None:
            rendement = fin.double() / self.capital_prec.double() - 1
            carre = rendement * rendement
            puissances = torch.stack((rendement, carre, carre * rendement, carre * carre), 1)
            self.moments.add_(torch.where(note[:, None], puissances, 0.0))
            torch.where(note, fin, self.capital_prec, out=self.capital_prec)
        self.anneau.index_copy_(0, case, self.frais_cum.unsqueeze(0))
        if self.trace_mode is not None:
            self._tracer("fraction", torch.where(note, (self.qte * C * MILLION).double() / fin.double(), 0.0).float())
        if self.trace_mode == "complet":
            decision = torch.where(ouvre, OUVERTURE, torch.where(sortie, FERMETURE,
                                                                 torch.where(maj, PROTECTION, RIEN)))
            self._tracer("capital", fin)
            self._tracer("cash", self.cash)
            self._tracer("decision", decision)
            self._tracer("raison", torch.where(sortie, raison, -1))
            self._tracer("quantite", torch.where(ouvre, q, 0))
            self._tracer("quantite_tenue", self.qte)
            self._tracer("prix", torch.where(ouvre, prix_achat, torch.where(sortie, prix_vente, 0)))
            self._tracer("stop", self.stop)
            self._tracer("cible", self.cible)
            self._tracer("entrees", torch.cat((ligne[:, :-1], etat), 1))
            self._tracer("probas", probas)
            self._tracer("sorties", sorties)
        self.k.add_(1)

    def _tracer(self, nom: str, valeur: torch.Tensor):
        tampon = self.traces[nom]
        tampon.index_copy_(0, self.k.view(1), valeur[:tampon.shape[1]].to(tampon.dtype).unsqueeze(0))

    def _resultats(self, pas: int) -> Resultats:
        n, W = self.n, self.W
        if int(self.pic.max()) >= self.capital0 * CROISSANCE_MAX:
            raise OverflowError("un couloir a depasse la croissance que la comptabilite entiere garantit")
        forme = lambda t: t.view(self.B, W, *t.shape[1:])[:n].cpu()
        trace = None
        if self.traces:
            gardes = min(n, self.bots_traces)
            trace = {nom: t[:pas].view(pas, self.bots_traces, W, *t.shape[2:])[:, :gardes].cpu()
                     for nom, t in self.traces.items()}
        return Resultats(
            forme(self.cash), forme(self.nb), forme(self.gagnants), forme(self.somme_r), forme(self.somme_r2),
            forme(self.dd), forme(self.ruine), forme(self.sorties), forme(self.frais_total), forme(self.rotation),
            forme(self.moments) if self.moments is not None else None, trace,
        )


def _adapter(poids, r, h, y, a, b, c, d) -> torch.Tensor:
    """Poids d'action apres la regle a cinq coefficients, eta deja integre aux coefficients.

    Un couloir sans fermeture a r = 0 : ses poids ressortent inchanges. Calcul element par element, donc
    identique qu'il porte sur tous les couloirs ou sur ceux qui ont ferme.
    """
    return (poids + r * (a * h * y + b * h + c * y + d)).clamp(-5, 5)
