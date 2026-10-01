"""Philox4x32-10 (Salmon, Moraes, Dror et Shaw, 2011) : generateur a compteur, sans etat.

Chaque tirage est une fonction pure d'une cle de 64 bits et d'un compteur de 128 bits. Rien n'est a
sauvegarder pour reprendre un run : l'etat des generateurs se resume aux compteurs.
La version en entiers Python sert aux tirages ponctuels, la version vectorisee aux genomes. Les deux
donnent les memes mots de 32 bits.
"""
import math

import torch

M0, M1 = 0xD2511F53, 0xCD9E8D57
W0, W1 = 0x9E3779B9, 0xBB67AE85
MASQUE = 0xFFFFFFFF

# Usages des cles derivees de la graine maitresse : un meme compteur ne sert jamais a deux usages.
GENERATION0, ENFANT, REFERENCE, HASARD, LOT, PERMUTATION = 1, 2, 3, 4, 5, 6

# Flux d'un genome, deuxieme mot du compteur. AMPLEURS : ampleur de chaque gene a la mutation ; FORCE : force de
# l'enfant, premier mot du flux.
NORMALES, UNIFORMES, UNIFORMES_BIS, NORMALES_SIGMA, AMPLEURS, FORCE = 0, 1, 2, 3, 4, 5


def bloc(k0: int, k1: int, c0: int, c1: int, c2: int, c3: int) -> tuple[int, int, int, int]:
    """Quatre mots de 32 bits pour la cle (k0, k1) et le compteur (c0, c1, c2, c3)."""
    for tour in range(10):
        if tour:
            k0, k1 = (k0 + W0) & MASQUE, (k1 + W1) & MASQUE
        p0, p1 = M0 * c0, M1 * c2
        c0, c1, c2, c3 = (p1 >> 32) ^ c1 ^ k0, p1 & MASQUE, (p0 >> 32) ^ c3 ^ k1, p0 & MASQUE
    return c0, c1, c2, c3


def _mulhilo(a: torch.Tensor, m: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Mots haut et bas de a * m, en int64 sans debordement : produits de moities de 16 bits."""
    a_lo, a_hi = a & 0xFFFF, a >> 16
    m_lo, m_hi = m & 0xFFFF, m >> 16
    p0 = a_lo * m_lo
    milieu = a_hi * m_lo + a_lo * m_hi + (p0 >> 16)
    return a_hi * m_hi + (milieu >> 16), ((milieu & 0xFFFF) << 16) | (p0 & 0xFFFF)


def bloc_t(k0, k1, c0, c1, c2, c3) -> tuple[torch.Tensor, ...]:
    """Meme calcul que bloc, vectorise : tenseurs int64 contenant des mots de 32 bits, diffusables."""
    for tour in range(10):
        if tour:
            k0, k1 = (k0 + W0) & MASQUE, (k1 + W1) & MASQUE
        hi0, lo0 = _mulhilo(c0, M0)
        hi1, lo1 = _mulhilo(c2, M1)
        c0, c1, c2, c3 = hi1 ^ c1 ^ k0, lo1, hi0 ^ c3 ^ k1, lo0
    return c0, c1, c2, c3


def cle(maitresse: int, usage: int, a: int, b: int) -> tuple[int, int]:
    """Cle de 64 bits d'un tirage, derivee de la graine maitresse, d'un usage et de deux indices."""
    mots = bloc(maitresse & MASQUE, (maitresse >> 32) & MASQUE, usage, a, b, 0)
    return mots[0], mots[1]


def cles_t(maitresse: int, usage: int, a: int, b: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Cles de 64 bits pour chaque indice de b, et un troisieme mot libre (le choix du parent d'un enfant)."""
    zero = torch.zeros_like(b)
    mots = bloc_t(maitresse & MASQUE, (maitresse >> 32) & MASQUE, zero + usage, zero + a, b, zero)
    return mots[0], mots[1], mots[2]


def mots_t(k0: torch.Tensor, k1: torch.Tensor, flux: int, n: int) -> torch.Tensor:
    """Au moins n mots de 32 bits par cle, du flux donne : tenseur (cles, 4 * blocs)."""
    blocs = torch.arange((n + 3) // 4, device=k0.device, dtype=torch.int64)[None, :]
    k0, k1 = k0[:, None], k1[:, None]
    zero = torch.zeros_like(blocs)
    return torch.stack(bloc_t(k0, k1, blocs, zero + flux, zero, zero), dim=2).reshape(k0.shape[0], -1)


def uniformes(mots: torch.Tensor) -> torch.Tensor:
    """Reels sur [0, 1), en float32 exact : les 24 bits de poids fort de chaque mot."""
    return (mots >> 8).to(torch.float32) * 2.0**-24


def normales(mots: torch.Tensor) -> torch.Tensor:
    """Loi normale centree reduite par Box-Muller : une normale par mot, les mots allant par paires."""
    u1 = ((mots[:, 0::2] >> 8) + 1).to(torch.float32) * 2.0**-24  # sur ]0, 1] : le logarithme reste fini
    u2 = (mots[:, 1::2] >> 8).to(torch.float32) * 2.0**-24
    rayon = torch.sqrt(-2.0 * torch.log(u1))
    angle = (2.0 * math.pi) * u2
    return torch.stack((rayon * torch.cos(angle), rayon * torch.sin(angle)), dim=2).reshape(mots.shape[0], -1)


def entier(k0: int, k1: int, c0: int, c1: int, n: int) -> int:
    """Un entier sur [0, n) par multiplication et decalage : biais inferieur a n / 2**32."""
    return (bloc(k0, k1, c0, c1, 0, 0)[0] * n) >> 32
