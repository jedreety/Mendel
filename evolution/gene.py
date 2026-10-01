from dataclasses import dataclass

ECHELLES = (1, 4, 24)  # heures : l'echelle de base et les deux echelles superieures


@dataclass(frozen=True)
class Gene:
    """Un gene du bot. type : "reel", "entier" ou "categoriel".

    Un gene reel ou entier est stocke en unites normalisees, sur [0, 1] entre ses bornes. Un entier garde
    sa valeur reelle sous-jacente, arrondie a l'usage : chaque entier de [bas, haut] y occupe une part
    egale. Un categoriel vaut l'indice de sa valeur dans categories.
    circulaire : la valeur est prise modulo son etendue au lieu d'etre bornee.
    """

    nom: str
    type: str
    bas: float = 0.0
    haut: float = 1.0
    categories: tuple = ()
    circulaire: bool = False
