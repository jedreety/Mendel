"""Assemblage et compilation du noyau CUDA du simulateur (evolution/noyau.cu), par NVRTC via PyTorch.

Le texte du noyau recoit ses constantes, les fonctions de signal des modules (l'attribut CUDA de chaque
fichier de evolution/modules/) et leur aiguillage. Les donnees lui parviennent par deux descripteurs, des
tableaux d'entiers de 64 bits sur la GPU : pointeurs vers les tenseurs et valeurs scalaires, a des places
nommees ici et dans le noyau par les memes constantes.
"""
from pathlib import Path

import torch

from evolution import compilation
from evolution.genome import MODULES, Disposition

SOURCE = Path(__file__).with_name("noyau.cu")

MARCHE = ("OUV", "HAUT", "BAS", "CLO", "TEMPS", "MINUIT", "INDICES", "LOCAL", "CLOTURE", "VOLUME", "MOYENNES",
          "ECARTS_TYPES", "VOLUMES_MOYENS", "ATR", "MAX_HAUT", "MIN_BAS", "NIVEAU_DE", "N1", "NCOMB", "OUVERTURE_C",
          "HAUT_C", "BAS_C", "VOLATILITES", "EMA", "SOMME_TYPIQUE", "SOMME_PRESSION", "SEGMENT", "HEURE", "JOUR",
          "TABLES")
PAQUET = ("L", "B", "W", "W_SORTIE", "B_CACHE", "B_SORTIE", "B_ACTION", "ADAPT", "GENES", "DECISION", "PROJ",
          "PERIODE_ATR", "FENETRES", "ETAT64", "ETATF", "RUINE", "SORTIES", "ANNEAU", "DERNIERS", "H", "WA", "HO",
          "YO", "T_FRACTION", "LT", "T_PRIX_REPOS", "T_RAISON_REPOS", "T_CAPITAL", "T_CASH", "T_DECISION", "T_RAISON",
          "T_QUANTITE", "T_QUANTITE_TENUE", "T_PRIX", "T_STOP", "T_CIBLE", "T_PROBAS", "T_SORTIES", "T_ENTREES")


def tables_des_modules(tables: list) -> list[torch.Tensor]:
    """Tables propres aux modules, dans l'ordre des modules puis de leur preparation."""
    liste = []
    for table in tables:
        if table is None:
            continue
        liste.extend(table if isinstance(table, tuple) else (table,))
    return liste


def source(disposition: Disposition, fenetres: int, tables: list, constantes: dict) -> str:
    """Texte complet du noyau pour ces dimensions et ces constantes : ce que NVRTC compile."""
    tailles, debuts, echelles, table_premiere = [], [], [], []
    position = rang_table = 0
    for module, table in zip(MODULES, tables):
        noms = [gene.nom for gene in module.GENES]
        tailles.append(len(noms))
        debuts.append(position)
        echelles.append(noms.index("echelle") if "echelle" in noms else -1)
        position += len(noms)
        table_premiere.append(rang_table)
        rang_table += 0 if table is None else len(table) if isinstance(table, tuple) else 1
    entete = [
        f"#define H {disposition.cachee}",
        f"#define E {disposition.entrees}",
        f"#define CANAUX {disposition.canaux}",
        f"#define W {fenetres}",
        f"#define NMOD {len(MODULES)}",
        f"#define NG {position}",
        f"#define GMAX {max(tailles)}",
        f"#define NTABLES {rang_table}",
    ]
    entete += [f"#define {nom} {_litteral(valeur)}" for nom, valeur in constantes.items()]
    entete += [f"#define M_{nom} {rang}" for rang, nom in enumerate(MARCHE)]
    entete += [f"#define P_{nom} {rang}" for rang, nom in enumerate(PAQUET)]
    entete += [f"#define TABLE_{module.NOM.upper()} {premiere}" for module, premiere in zip(MODULES, table_premiere)]
    tableau = lambda nom, valeurs: f"__device__ __constant__ int {nom}[{len(valeurs)}] = {{{', '.join(map(str, valeurs))}}};"
    entete += [tableau("MODULE_TAILLE", tailles), tableau("MODULE_DEBUT", debuts), tableau("MODULE_ECHELLE", echelles)]
    texte = SOURCE.read_text(encoding="utf-8")
    modules = "\n".join(module.CUDA for module in MODULES)
    aiguillage = "\n".join(f"        case {rang}: return signal_{module.NOM}(m, g, i, periode_atr);"
                           for rang, module in enumerate(MODULES))
    texte = texte.replace("/*MODULES*/", modules).replace("/*AIGUILLAGE*/", aiguillage)
    return "\n".join(entete) + "\n" + texte


def compiler(disposition: Disposition, fenetres: int, tables: list, constantes: dict):
    """Noyau compile pour ces dimensions et ces constantes.

    constantes : reglages et mode de trace, figes dans le texte du noyau (voir noyau.cu). Un bloc compte un
    fil par neurone cache, en warps entiers, et porte au plus 4 fenetres : les valeurs d'une entree pour toutes
    les fenetres tiennent dans un float4, et les sept sorties des fenetres dans les 32 fils d'un warp.
    """
    if disposition.cachee % 32 or fenetres > 4:
        raise ValueError("le noyau demande une couche cachee multiple de 32 et au plus 4 fenetres par bot")
    return compilation.compiler(source(disposition, fenetres, tables, constantes), "simuler")


def _litteral(valeur) -> str:
    """Constante C : entier de 64 bits, ou double ecrit de facon a se relire a l'identique."""
    if isinstance(valeur, float):
        return repr(valeur)
    return f"{int(valeur)}LL"


def descripteur(valeurs: dict, noms: tuple, appareil: torch.device) -> torch.Tensor:
    """Tableau des pointeurs et des scalaires, a la place que le noyau attend pour chaque nom."""
    ligne = []
    for nom in noms:
        valeur = valeurs.get(nom, 0)
        if isinstance(valeur, list):  # suite de tenseurs : les tables des modules, a la fin du descripteur
            ligne.extend(t.data_ptr() for t in valeur)
        elif isinstance(valeur, torch.Tensor):
            ligne.append(valeur.data_ptr())
        else:
            ligne.append(int(valeur))
    return torch.tensor(ligne, dtype=torch.int64, device=appareil)


def descripteur_marche(marche, tables: list) -> torch.Tensor:
    m = marche
    return descripteur({
        "OUV": m.ouv_t, "HAUT": m.haut_t, "BAS": m.bas_t, "CLO": m.clo_t, "TEMPS": m.temps, "MINUIT": m.minuit,
        "INDICES": m.indices, "LOCAL": m.local, "CLOTURE": m.cloture, "VOLUME": m.volume, "MOYENNES": m.moyennes,
        "ECARTS_TYPES": m.ecarts_types, "VOLUMES_MOYENS": m.volumes_moyens, "ATR": m.atr, "MAX_HAUT": m.max_haut,
        "MIN_BAS": m.min_bas, "NIVEAU_DE": m.niveau_de, "N1": m.n1, "NCOMB": m.ncomb, "OUVERTURE_C": m.ouverture,
        "HAUT_C": m.haut, "BAS_C": m.bas, "VOLATILITES": m.volatilites, "EMA": m.ema,
        "SOMME_TYPIQUE": m.somme_typique, "SOMME_PRESSION": m.somme_pression, "SEGMENT": m.segment,
        "HEURE": m.heure, "JOUR": m.jour, "TABLES": tables_des_modules(tables),
    }, MARCHE, m.appareil)
