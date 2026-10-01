"""Ce que les regles portees partagent : le gene d'echelle, et la lecture de leurs tables a 8 bits.

La plupart des regles precalculent leur signal pour chaque valeur de leurs genes entiers (Marche.table8) : leur
signal n'est plus qu'une lecture de table, la meme en PyTorch et dans le noyau. Les autres le calculent a la
volee, dans leur propre fichier.
"""
import torch

from evolution.gene import ECHELLES, Gene

ECHELLE = Gene("echelle", "categoriel", categories=ECHELLES)
SEUIL_BAS = Gene("bas", "reel", 5, 50)
SEUIL_HAUT = Gene("haut", "reel", 50, 95)


def oscillateur(y: torch.Tensor) -> torch.Tensor:
    """Un oscillateur de 0 a 100 dans une table a 8 bits : y = x/50 - 1, relu exactement par x = 50 + 50 y."""
    return y / 50 - 1


def seuils(x: torch.Tensor, bas: torch.Tensor, haut: torch.Tensor) -> torch.Tensor:
    """Lecture en retour a la moyenne d'un oscillateur de 0 a 100, comme les regles du moteur : sous bas +1, au-dessus
    de haut -1, entre les deux s'abstient. Intensite : profondeur au-dela du seuil, rapportee a la marge jusqu'a 0 ou
    100. NaN, un oscillateur indefini, donne 0.
    """
    return torch.where(x < bas, (bas - x) / bas, torch.where(x > haut, -((x - haut) / (100 - haut)), 0.0))


def lire_oscillateur(marche, table, ligne, j) -> torch.Tensor:
    return 50 + 50 * marche.lire8(table, ligne, j)


def lecture(gene: str | None = None, bas: int = 0):
    """Signal PyTorch d'une regle dont la table a une ligne par valeur du gene (a partir de bas), ou une seule."""
    def signal(marche, table, i, g, bot):
        ligne = 0 if gene is None else g[gene] - bas
        return marche.lire8(table, ligne, marche.indice(g["echelle"], i))
    return signal


def lecture_cuda(nom: str, gene: int | None = None, bas: int = 0) -> str:
    """Meme lecture dans le noyau : g[0] est l'echelle, g[gene] le gene qui choisit la ligne."""
    ligne = "0" if gene is None else f"(int)g[{gene}] - {bas}"
    return f"""
__device__ float signal_{nom}(const Marche& m, const float* g, int i, int periode_atr) {{
    return lire8(m, TABLE_{nom.upper()}, {ligne}, indice(m, (int)g[0], i));
}}
"""


def lecture_horaire(gene: str | None = None, bas: int = 0):
    """Signal PyTorch d'une regle de l'echelle horaire seule, lue a l'indice horaire."""
    def signal(marche, table, i, g, bot):
        return marche.lire8_horaire(table, 0 if gene is None else g[gene] - bas, i)
    return signal


def lecture_horaire_cuda(nom: str, ligne: str) -> str:
    """Meme lecture dans le noyau ; ligne : expression C de la ligne, en genes g[...]."""
    return f"""
__device__ float signal_{nom}(const Marche& m, const float* g, int i, int periode_atr) {{
    return lire8_horaire(m, TABLE_{nom.upper()}, {ligne}, i);
}}
"""
