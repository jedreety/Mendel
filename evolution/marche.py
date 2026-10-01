"""Marche : barres des trois echelles et indicateurs communs, precalcules une fois pour tous les bots.

Chaque indicateur est calcule pour toutes ses periodes possibles, sur tout l'historique charge. Un bot lit
sa periode dans la table : aucun etat d'indicateur par bot, et des moyennes deja convergees au debut de
chaque fenetre, comme les verrait un bot en reel.

Les trois echelles sont mises bout a bout sur un axe combine. j designe une position sur cet axe ; -1
signifie qu'aucune barre de l'echelle n'est encore close. Un accesseur renvoie NaN quand l'historique ne
suffit pas ; le simulateur change alors le signal en 0.
"""
import math

import torch

from evolution import compilation, indicateurs
from evolution.data import Historique
from evolution.gene import ECHELLES

PERIODE_ATR_MAX = 500  # couvre periode_atr (5 a 100) et la volatilite relative (jusqu'a 500)
FENETRE_MAX = 500  # plus longue fenetre glissante des modules
VOLATILITE_MAX = 200  # plus longue periode de la volatilite R des regles du moteur
EMA_MIN, EMA_MAX = 2, 400  # periodes des moyennes exponentielles
QUANTUM = 1 / 127  # pas des tables a 8 bits : q x QUANTUM, arrondi en simple, redonne -1 et 1 exactement
INDEFINI = -128  # valeur a 8 bits qui n'est pas definie
QUANTUM16, INDEFINI16 = 1 / 32767, -32768  # de meme sur 16 bits, pour les signaux qui sautent a un seuil

# Un fil par periode, les barres dans l'ordre. Chaque operation est arrondie a part, sans contraction en FMA,
# comme les trois operations PyTorch de lisser_reference : les memes valeurs, au bit pres.
LISSER = r"""
extern "C" __global__ void lisser(const double* __restrict__ serie, const long long* __restrict__ depart,
                                  const double* __restrict__ amorce, const double* __restrict__ alpha, int n,
                                  int periodes, int premier, double* __restrict__ sortie) {
    const int p = blockIdx.x * blockDim.x + threadIdx.x;
    if (p >= periodes) return;
    const double a = alpha[p], debut = amorce[p];
    const long long d = depart[p];
    double y = __longlong_as_double(0x7ff8000000000000LL);
    for (int t = premier; t < n; ++t) {
        y = t == d ? debut : __dadd_rn(y, __dmul_rn(a, __dsub_rn(serie[t], y)));
        sortie[(long long)t * periodes + p] = y;
    }
}
"""


def lisser(serie: torch.Tensor, periodes: torch.Tensor, alpha: torch.Tensor, premier: int) -> torch.Tensor:
    """Moyennes recursives y = y + alpha (x - y), une ligne par periode, en float64.

    La moyenne de periode p demarre a l'indice premier + p - 1 sur la moyenne simple des p valeurs qui
    precedent, et vaut NaN avant : c'est l'amorce de Wilder et de l'EMA classique. Sur la GPU s'il y en a une,
    le resultat y restant ; sinon par lisser_reference.
    """
    if not torch.cuda.is_available():
        return lisser_reference(serie, periodes, alpha, premier)
    n, p = serie.shape[0], periodes.shape[0]
    depart, amorce = _amorce(serie, periodes, premier)
    gpu = lambda t: t.to("cuda", torch.float64 if t.is_floating_point() else torch.int64).contiguous()
    sortie = torch.full((n, p), math.nan, dtype=torch.float64, device="cuda")
    compilation.compiler(LISSER, "lisser")(grid=((p + 127) // 128, 1, 1), block=(128, 1, 1), args=[
        gpu(serie), gpu(depart), gpu(amorce), gpu(alpha), n, p, premier, sortie])
    return sortie.T.contiguous()


def lisser_reference(serie: torch.Tensor, periodes: torch.Tensor, alpha: torch.Tensor, premier: int) -> torch.Tensor:
    """Meme calcul que lisser, en operations PyTorch sur le processeur."""
    n = serie.shape[0]
    sortie = torch.full((n, periodes.shape[0]), math.nan, dtype=torch.float64)
    depart, amorce = _amorce(serie, periodes, premier)
    y = torch.full_like(alpha, math.nan)
    for t in range(premier, n):
        y = torch.where(depart == t, amorce, y + alpha * (serie[t] - y))
        sortie[t] = y
    return sortie.T.contiguous()


def _amorce(serie: torch.Tensor, periodes: torch.Tensor, premier: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Indice de depart de chaque periode et moyenne simple qui l'amorce, sur le processeur."""
    n = serie.shape[0]
    cumul = torch.cat((torch.zeros(1, dtype=torch.float64), serie.cumsum(0)))
    depart = premier + periodes - 1
    amorce = torch.where(depart < n, (cumul[(depart + 1).clamp(max=n)] - cumul[premier]) / periodes, math.nan)
    return depart, amorce


class Marche:
    def __init__(self, hist: Historique, appareil: torch.device):
        self.appareil = appareil
        self.pas_de_prix = float(hist.pas_de_prix)
        self.n1 = len(hist)
        pas = self.pas_de_prix
        heures = (hist.debut.timestamp() // 3600) + 1 + torch.arange(self.n1, dtype=torch.float64)  # clotures
        self.heures_cloture = heures.to(torch.int64)
        barres1 = {
            "ouverture": hist.ouverture.double() * pas, "haut": hist.haut.double() * pas,
            "bas": hist.bas.double() * pas, "cloture": hist.cloture.double() * pas, "volume": hist.volume,
        }
        self.barres = [barres1]  # par echelle, float64 sur le processeur : pour la preparation des modules
        indices = [torch.arange(self.n1, dtype=torch.int64)]
        for largeur in ECHELLES[1:]:
            barres, indice = self._agreger(barres1, largeur)
            self.barres.append(barres)
            indices.append(indice)
        self.longueurs = [b["cloture"].shape[0] for b in self.barres]
        self.decalages = [0, self.longueurs[0], self.longueurs[0] + self.longueurs[1]]
        self.ncomb = sum(self.longueurs)
        segment = torch.cat([torch.full((n,), s, dtype=torch.int64) for s, n in enumerate(self.longueurs)])
        self.local = self._gpu(torch.cat([torch.arange(n, dtype=torch.int64) for n in self.longueurs]))
        self.segment = self._gpu(segment)
        self.indices = self._gpu(torch.cat([
            torch.where(indice >= 0, indice + decalage, -1) for indice, decalage in zip(indices, self.decalages)
        ]))
        self.cloture = self._gpu(self._combiner("cloture").float())
        self.volume = self._gpu(self._combiner("volume").float())
        self.ouverture = self._gpu(self._combiner("ouverture").float())
        self.haut = self._gpu(self._combiner("haut").float())
        self.bas = self._gpu(self._combiner("bas").float())
        # Sommes cumulees par segment, precedees d'un zero : moyennes et ecarts-types de toute longueur.
        self.reference = float(barres1["cloture"][0])
        self.somme = self._gpu(self._cumuler(lambda b: b["cloture"] - self.reference))
        self.somme2 = self._gpu(self._cumuler(lambda b: (b["cloture"] - self.reference) ** 2))
        self.somme_vol = self._gpu(self._cumuler(lambda b: b["volume"]))
        # Prix typique et pression d'achat, cloture moins le plus bas entre le plus bas et la cloture precedente.
        self.somme_typique = self._gpu(self._cumuler(lambda b: (b["haut"] + b["bas"] + b["cloture"]) / 3))
        self.somme_pression = self._gpu(self._cumuler(
            lambda b: b["cloture"] - torch.minimum(b["bas"], torch.cat((b["cloture"][:1], b["cloture"][:-1])))))
        # Les memes moyennes, ecarts-types et volumes moyens, pour toutes les longueurs de 1 a FENETRE_MAX
        # (ligne n - 1) : calcules une fois par les accesseurs, le noyau les lit au lieu de diviser en double.
        self.moyennes = self._glissantes(self.moyenne_simple)
        self.ecarts_types = self._glissantes(self.ecart_type)
        self.volumes_moyens = self._glissantes(self.volume_moyen)
        # Volatilite R des regles du moteur, moyenne simple de l'etendue vraie, periodes 1 a VOLATILITE_MAX.
        self.volatilites = self.table([torch.stack([indicateurs.volatilite(b, n) for n in range(1, VOLATILITE_MAX + 1)])
                                       for b in self.barres])
        # Moyennes exponentielles des clotures, periodes EMA_MIN a EMA_MAX, amorcees sur la moyenne simple.
        periodes = torch.arange(EMA_MIN, EMA_MAX + 1, dtype=torch.int64)
        self.ema = self.table([lisser(b["cloture"], periodes, 2.0 / (periodes.double() + 1), 0) for b in self.barres])
        # ATR de Wilder, periodes 1 a PERIODE_ATR_MAX : ligne p - 1.
        periodes = torch.arange(1, PERIODE_ATR_MAX + 1, dtype=torch.int64)
        self.atr = self._gpu(torch.cat([
            lisser(self._etendue_vraie(b), periodes, 1.0 / periodes.double(), 0) for b in self.barres
        ], dim=1).float())
        # Tables creuses des extremes glissants : niveau k, maximum ou minimum des 2**k dernieres barres.
        self.niveaux = int(math.log2(FENETRE_MAX)) + 1
        self.max_haut = self._gpu(self._table_creuse("haut", torch.maximum).float())
        self.min_bas = self._gpu(self._table_creuse("bas", torch.minimum).float())
        self.niveau_de = self._gpu(torch.tensor(
            [0] + [int(math.log2(n)) for n in range(1, FENETRE_MAX + 1)], dtype=torch.int64))
        # Barres horaires en pas de prix entiers : la comptabilite exacte du simulateur.
        self.ouv_t, self.haut_t, self.bas_t, self.clo_t = (
            self._gpu(t) for t in (hist.ouverture, hist.haut, hist.bas, hist.cloture))
        heure = (self.heures_cloture % 24).double() * (2 * math.pi / 24)
        jour = ((self.heures_cloture // 24 + 3) % 7).double() * (2 * math.pi / 7)  # lundi = 0
        self.temps = self._gpu(torch.stack((heure.sin(), heure.cos(), jour.sin(), jour.cos()), 1).float())
        self.minuit = self._gpu(self.heures_cloture % 24 == 0)
        # Heure et jour de la semaine ou commence la barre suivante : ceux de l'instant de cloture de la barre.
        self.heure = self._gpu((self.heures_cloture % 24).to(torch.uint8))
        self.jour = self._gpu(((self.heures_cloture // 24 + 3) % 7).to(torch.uint8))

    def _gpu(self, t: torch.Tensor) -> torch.Tensor:
        return t.to(self.appareil)

    def _glissantes(self, accesseur) -> torch.Tensor:
        """Table (FENETRE_MAX, ncomb) d'un accesseur glissant, par tranches de 50 longueurs."""
        j = torch.arange(self.ncomb, device=self.appareil)[None, :]
        return torch.cat([accesseur(torch.arange(n, min(n + 50, FENETRE_MAX + 1), device=self.appareil)[:, None], j)
                          for n in range(1, FENETRE_MAX + 1, 50)])

    def _agreger(self, b: dict, largeur: int) -> tuple[dict, torch.Tensor]:
        """Barres de `largeur` heures faites de barres horaires closes ; seules les periodes completes comptent.

        Renvoie aussi, pour chaque barre horaire, l'indice de la derniere barre de l'echelle close a sa
        cloture, ou -1.
        """
        reste = (self.heures_cloture - 1) % largeur
        premiere = int((reste == 0).nonzero()[0])
        nombre = (self.n1 - premiere) // largeur
        fin = premiere + nombre * largeur
        grouper = lambda serie: serie[premiere:fin].reshape(nombre, largeur)
        barres = {
            "ouverture": grouper(b["ouverture"])[:, 0], "haut": grouper(b["haut"]).amax(1),
            "bas": grouper(b["bas"]).amin(1), "cloture": grouper(b["cloture"])[:, -1],
            "volume": grouper(b["volume"]).sum(1),
        }
        # La barre horaire i cloture a l'heure H ; la derniere periode close finit a (H // largeur) * largeur.
        rang = self.heures_cloture // largeur - (int(self.heures_cloture[premiere]) - 1) // largeur - 1
        return barres, torch.where((rang >= 0) & (rang < nombre), rang, -1)

    def _combiner(self, nom: str) -> torch.Tensor:
        return torch.cat([b[nom] for b in self.barres])

    def _cumuler(self, valeur) -> torch.Tensor:
        return torch.cat([torch.cat((torch.zeros(1, dtype=torch.float64), valeur(b).cumsum(0))) for b in self.barres])

    @staticmethod
    def _etendue_vraie(b: dict) -> torch.Tensor:
        veille = torch.cat((b["cloture"][:1], b["cloture"][:-1]))
        return torch.maximum(b["haut"], veille) - torch.minimum(b["bas"], veille)

    def _table_creuse(self, nom: str, extreme) -> torch.Tensor:
        niveaux = []
        for b in self.barres:
            courant = b[nom].clone()
            lignes = [courant]
            for k in range(1, self.niveaux):
                decale = torch.cat((torch.full((2 ** (k - 1),), math.nan, dtype=torch.float64), courant[:-2 ** (k - 1)]))
                courant = extreme(courant, decale)
                lignes.append(courant)
            niveaux.append(torch.stack(lignes))
        return torch.cat(niveaux, dim=1)

    # --- Accesseurs, vectorises sur les couloirs du simulateur ---

    @staticmethod
    def diviser(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """a / b, et NaN quand b n'est pas strictement positif : un ATR nul ne produit pas de signal."""
        return torch.where(b > 0, a / b, math.nan)

    def indice(self, echelle: torch.Tensor, i: torch.Tensor) -> torch.Tensor:
        """Position sur l'axe combine de la derniere barre close de l'echelle, a la cloture horaire i."""
        return self.indices.take(echelle * self.n1 + i)

    def _valide(self, j: torch.Tensor, n) -> torch.Tensor:
        return (j >= 0) & (self.local.take(j.clamp(min=0)) >= n - 1)

    def cloture_en(self, j: torch.Tensor) -> torch.Tensor:
        return torch.where(j >= 0, self.cloture.take(j.clamp(min=0)), math.nan)

    def cloture_avant(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        """Cloture n barres avant j, dans la meme echelle."""
        return torch.where(self._valide(j, n + 1), self.cloture.take((j - n).clamp(min=0)), math.nan)

    def atr_en(self, periode: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        return torch.where(j >= 0, self.atr.take((periode - 1) * self.ncomb + j.clamp(min=0)), math.nan)

    def _fenetre(self, table: torch.Tensor, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        """Somme des n dernieres valeurs jusqu'a j, en float64, lue dans une table de sommes cumulees."""
        position = j.clamp(min=0) + self.segment.take(j.clamp(min=0)) + 1
        return table.take(position) - table.take((position - n).clamp(min=0))

    def moyenne_simple(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        moyenne = self._fenetre(self.somme, n, j) / n + self.reference
        return torch.where(self._valide(j, n), moyenne, math.nan).float()

    def ecart_type(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        moyenne = self._fenetre(self.somme, n, j) / n
        variance = (self._fenetre(self.somme2, n, j) / n - moyenne**2).clamp(min=0)
        return torch.where(self._valide(j, n), variance.sqrt(), math.nan).float()

    def volume_en(self, j: torch.Tensor) -> torch.Tensor:
        return torch.where(j >= 0, self.volume.take(j.clamp(min=0)), math.nan)

    def volume_moyen(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        return torch.where(self._valide(j, n), self._fenetre(self.somme_vol, n, j) / n, math.nan).float()

    def valide(self, j: torch.Tensor, n) -> torch.Tensor:
        """Au moins n barres de l'echelle closes jusqu'a j compris."""
        return self._valide(j, n)

    def somme_typique_en(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        """Somme des prix typiques des n dernieres barres, en float64 ; NaN si l'historique ne suffit pas."""
        return torch.where(self._valide(j, n), self._fenetre(self.somme_typique, n, j), math.nan)

    def somme_pression_en(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        """Somme des pressions d'achat des n dernieres barres, qui exigent n + 1 barres, en float64."""
        return torch.where(self._valide(j, n + 1), self._fenetre(self.somme_pression, n, j), math.nan)

    def en(self, serie: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        """Valeur d'une serie combinee (ouverture, haut, bas, cloture, volume) a la place j, NaN si j < 0."""
        return torch.where(j >= 0, serie.take(j.clamp(min=0)), math.nan)

    def precedente(self, serie: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        """Valeur a la barre precedente de la meme echelle, NaN s'il n'y en a pas."""
        return torch.where(self._valide(j, 2), serie.take((j - 1).clamp(min=0)), math.nan)

    def volatilite(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        """R des regles du moteur sur n barres, lue dans la table ; NaN si l'historique ne suffit pas."""
        return torch.where(j >= 0, self.volatilites.take((n - 1) * self.ncomb + j.clamp(min=0)), math.nan)

    def ema_en(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        return torch.where(j >= 0, self.ema.take((n - EMA_MIN) * self.ncomb + j.clamp(min=0)), math.nan)

    def _extreme(self, table: torch.Tensor, extreme, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        k = self.niveau_de.take(n)
        base = k * self.ncomb
        a = table.take(base + j.clamp(min=0))
        b = table.take(base + (j - n + (1 << k)).clamp(min=0))
        return torch.where(self._valide(j, n), extreme(a, b), math.nan)

    def plus_haut(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        return self._extreme(self.max_haut, torch.maximum, n, j)

    def plus_bas(self, n: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        return self._extreme(self.min_bas, torch.minimum, n, j)

    def table(self, lignes_par_echelle: list[torch.Tensor]) -> torch.Tensor:
        """Table d'un module : une ligne par periode, trois echelles bout a bout, sur la GPU en float32."""
        return self._gpu(torch.cat(lignes_par_echelle, dim=1).float())

    def table8(self, calcul, indefini: bool = False, horaire: bool = False, bits: int = 8) -> torch.Tensor:
        """Table a 8 bits d'un module : calcul(barres d'une echelle) en donne les lignes, une par valeur de ses
        genes, ou une seule.

        Une valeur y de [-1, 1] devient l'entier round(127 y), relu par q x QUANTUM en simple, dans le noyau comme
        ici. Sans historique suffisant, NaN devient 0, le signal d'une regle qui s'abstient, ou INDEFINI si
        indefini. horaire : l'echelle horaire seule, lue a l'indice horaire. bits : 16 pour un signal qui saute a un
        seuil, que 8 bits ne trancheraient pas assez finement.
        """
        lignes = [calcul(b) for b in (self.barres[:1] if horaire else self.barres)]
        y = torch.cat([ligne if ligne.dim() == 2 else ligne[None] for ligne in lignes], dim=1)
        echelle, sentinelle, type_ = (127, INDEFINI, torch.int8) if bits == 8 else (32767, INDEFINI16, torch.int16)
        q = torch.round(y.clamp(-1, 1) * echelle)
        return self._gpu(torch.nan_to_num(q, nan=sentinelle if indefini else 0).to(type_))

    @staticmethod
    def octet(table: torch.Tensor, position: torch.Tensor) -> torch.Tensor:
        """Valeur d'une table a 8 ou 16 bits, NaN si elle n'est pas definie."""
        q = table.take(position)
        if table.dtype == torch.int16:
            return torch.where(q == INDEFINI16, math.nan, q.float() * QUANTUM16)
        return torch.where(q == INDEFINI, math.nan, q.float() * QUANTUM)

    def lire8(self, table: torch.Tensor, ligne: torch.Tensor, j: torch.Tensor) -> torch.Tensor:
        """Ligne `ligne` d'une table a 8 bits des trois echelles, a la place j ; NaN si j < 0."""
        return torch.where(j >= 0, self.octet(table, ligne * self.ncomb + j.clamp(min=0)), math.nan)

    def lire8_horaire(self, table: torch.Tensor, ligne: torch.Tensor, i: torch.Tensor) -> torch.Tensor:
        """Ligne `ligne` d'une table a 8 bits de l'echelle horaire, a la barre horaire i."""
        return self.octet(table, ligne * self.n1 + i)
