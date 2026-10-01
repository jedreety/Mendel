"""Appels a l'API Windows par ctypes, pour l'interface : processus, console, processeur, memoire et corbeille.

Bibliotheque standard seulement : ctypes tient le role de psutil. Chaque HANDLE est declare a la taille d'un
pointeur, comme dans evolution/rejeu.py, pour ne pas etre tronque sur 64 bits.
"""
import ctypes
import msvcrt
import os
import subprocess
from ctypes import wintypes
from pathlib import Path

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

LIRE = 0x80000000  # GENERIC_READ
PARTAGE_TOTAL = 0x7  # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
OUVRIR_EXISTANT = 3  # OPEN_EXISTING
ATTRIBUT_NORMAL = 0x80
ENCORE_ACTIF = 259  # STILL_ACTIVE
LECTURE_LIMITEE = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
LECTURE_MEMOIRE = 0x0010  # PROCESS_VM_READ
INSTANTANE_PROCESSUS = 0x2  # TH32CS_SNAPPROCESS
POIGNEE_INVALIDE = ctypes.c_void_p(-1).value
CONSOLE_NEUVE = 0x00000010  # CREATE_NEW_CONSOLE
SANS_CONSOLE = 0x00000008  # DETACHED_PROCESS
SANS_FENETRE = 0x08000000  # CREATE_NO_WINDOW
SUPPRIMER = 0x0003  # FO_DELETE
# FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI : vers la corbeille, sans fenetre
VERS_CORBEILLE = 0x0004 | 0x0010 | 0x0040 | 0x0400


class _Filetime(ctypes.Structure):
    _fields_ = [("bas", wintypes.DWORD), ("haut", wintypes.DWORD)]


class _Memoire(ctypes.Structure):
    _fields_ = [("taille", wintypes.DWORD), ("charge", wintypes.DWORD), ("physique_totale", ctypes.c_ulonglong),
                ("physique_libre", ctypes.c_ulonglong), ("pagination_totale", ctypes.c_ulonglong),
                ("pagination_libre", ctypes.c_ulonglong), ("virtuelle_totale", ctypes.c_ulonglong),
                ("virtuelle_libre", ctypes.c_ulonglong), ("etendue_libre", ctypes.c_ulonglong)]


class _CompteursMemoire(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS
    _fields_ = [("taille", wintypes.DWORD), ("defauts", wintypes.DWORD), ("pic_travail", ctypes.c_size_t),
                ("travail", ctypes.c_size_t), ("pic_pagine", ctypes.c_size_t), ("pagine", ctypes.c_size_t),
                ("pic_non_pagine", ctypes.c_size_t), ("non_pagine", ctypes.c_size_t),
                ("fichier_pagination", ctypes.c_size_t), ("pic_fichier_pagination", ctypes.c_size_t)]


class _EntreeProcessus(ctypes.Structure):  # PROCESSENTRY32W
    _fields_ = [("taille", wintypes.DWORD), ("usages", wintypes.DWORD), ("pid", wintypes.DWORD),
                ("tas", ctypes.c_size_t), ("module", wintypes.DWORD), ("fils", wintypes.DWORD),
                ("parent", wintypes.DWORD), ("priorite", ctypes.c_long), ("drapeaux", wintypes.DWORD),
                ("executable", ctypes.c_wchar * 260)]


class _OperationFichiers(ctypes.Structure):  # SHFILEOPSTRUCTW
    _fields_ = [("fenetre", ctypes.c_void_p), ("fonction", wintypes.UINT), ("depuis", ctypes.c_void_p),
                ("vers", ctypes.c_void_p), ("drapeaux", wintypes.WORD), ("abandon", wintypes.BOOL),
                ("correspondances", ctypes.c_void_p), ("titre", ctypes.c_void_p)]


_FT = ctypes.POINTER(_Filetime)
kernel32.CreateFileW.restype = ctypes.c_void_p
kernel32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                 wintypes.DWORD, ctypes.c_void_p)
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
kernel32.GetExitCodeProcess.argtypes = (ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD))
kernel32.GetProcessTimes.argtypes = (ctypes.c_void_p, _FT, _FT, _FT, _FT)
kernel32.GetSystemTimes.argtypes = (_FT, _FT, _FT)
kernel32.GlobalMemoryStatusEx.argtypes = (ctypes.POINTER(_Memoire),)
kernel32.K32GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.POINTER(_CompteursMemoire), wintypes.DWORD)
kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
kernel32.Process32FirstW.argtypes = (ctypes.c_void_p, ctypes.POINTER(_EntreeProcessus))
kernel32.Process32NextW.argtypes = (ctypes.c_void_p, ctypes.POINTER(_EntreeProcessus))
shell32.SHFileOperationW.argtypes = (ctypes.POINTER(_OperationFichiers),)


def _entier(ft: _Filetime) -> int:
    return (ft.haut << 32) | ft.bas


def lire(chemin: Path, depuis: int = 0, taille: int = -1) -> bytes:
    """Octets d'un fichier, ouvert en partage complet, suppression comprise : pendant la lecture, le bot peut
    encore effacer le fichier ou son dossier (shutil.rmtree de pantheon/). Un open() ordinaire l'en empecherait.

    Ce partage ne suffit pas a os.replace : aucun fichier que le bot remplace ne doit etre ouvert pendant qu'il
    ecrit (interface/lecture.py)."""
    poignee = kernel32.CreateFileW(str(chemin), LIRE, PARTAGE_TOTAL, None, OUVRIR_EXISTANT, ATTRIBUT_NORMAL, None)
    if poignee is None or poignee == POIGNEE_INVALIDE:
        raise ctypes.WinError(ctypes.get_last_error())
    with open(msvcrt.open_osfhandle(poignee, os.O_RDONLY | os.O_BINARY), "rb") as fichier:
        if depuis:
            fichier.seek(depuis)
        return fichier.read(taille)


def temps_systeme() -> tuple[int, int] | None:
    """Temps inactif et temps total de tous les coeurs, en centaines de nanosecondes."""
    inactif, noyau, utilisateur = _Filetime(), _Filetime(), _Filetime()
    if not kernel32.GetSystemTimes(ctypes.byref(inactif), ctypes.byref(noyau), ctypes.byref(utilisateur)):
        return None
    return _entier(inactif), _entier(noyau) + _entier(utilisateur)  # le temps noyau compte deja l'inactif


def memoire() -> tuple[int, int]:
    """Memoire physique utilisee et totale, en octets."""
    m = _Memoire()
    m.taille = ctypes.sizeof(m)
    kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.physique_totale - m.physique_libre, m.physique_totale


def processus(pid: int) -> dict | None:
    """Etat d'un processus : vivant, instant de creation (contre la reutilisation des numeros), temps de calcul
    et memoire de travail. None s'il n'existe plus ou reste inaccessible."""
    poignee = kernel32.OpenProcess(LECTURE_LIMITEE | LECTURE_MEMOIRE, False, pid)
    if not poignee:
        poignee = kernel32.OpenProcess(LECTURE_LIMITEE, False, pid)
        if not poignee:
            return None
    try:
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(poignee, ctypes.byref(code))
        creation, fin, noyau, utilisateur = _Filetime(), _Filetime(), _Filetime(), _Filetime()
        kernel32.GetProcessTimes(poignee, ctypes.byref(creation), ctypes.byref(fin), ctypes.byref(noyau),
                                 ctypes.byref(utilisateur))
        compteurs = _CompteursMemoire()
        compteurs.taille = ctypes.sizeof(compteurs)
        lue = kernel32.K32GetProcessMemoryInfo(poignee, ctypes.byref(compteurs), compteurs.taille)
        return {"vivant": code.value == ENCORE_ACTIF, "creation": _entier(creation),
                "calcul": _entier(noyau) + _entier(utilisateur), "memoire": compteurs.travail if lue else 0}
    finally:
        kernel32.CloseHandle(poignee)


def descendants(pid: int) -> list[int]:
    """Le processus et tous ses descendants : le bot et ses processus de rejeu."""
    instantane = kernel32.CreateToolhelp32Snapshot(INSTANTANE_PROCESSUS, 0)
    if not instantane or instantane == POIGNEE_INVALIDE:
        return [pid]
    enfants: dict[int, list[int]] = {}
    try:
        entree = _EntreeProcessus()
        entree.taille = ctypes.sizeof(entree)
        encore = kernel32.Process32FirstW(instantane, ctypes.byref(entree))
        while encore:
            enfants.setdefault(entree.parent, []).append(entree.pid)
            encore = kernel32.Process32NextW(instantane, ctypes.byref(entree))
    finally:
        kernel32.CloseHandle(instantane)
    trouves, file = [pid], [pid]
    while file:
        for enfant in enfants.get(file.pop(), []):
            if enfant not in trouves:
                trouves.append(enfant)
                file.append(enfant)
    return trouves


# Envoie Ctrl+C a la console d'un processus, depuis un processus a part : s'y attacher detacherait
# l'interface de sa propre console. Le processus d'envoi ignore lui-meme le signal.
_CTRL_C = r"""
import ctypes, sys
k = ctypes.windll.kernel32
k.FreeConsole()
if not k.AttachConsole(int(sys.argv[1])):
    sys.exit(2)
k.SetConsoleCtrlHandler(None, True)
sys.exit(0 if k.GenerateConsoleCtrlEvent(0, 0) else 3)
"""


def autoriser_ctrl_c() -> None:
    """Leve, pour ce processus et les taches qu'il lancera, la desactivation de Ctrl+C que Windows transmet aux
    enfants d'un processus lance dans un nouveau groupe (par un planificateur, un editeur ou un autre outil).
    Sans cela, la console de la tache recevrait Ctrl+C sans que le bot le voie."""
    kernel32.SetConsoleCtrlHandler(None, False)


def ctrl_c(python: str, pid: int) -> bool:
    """Ctrl+C a tous les processus de la console de pid, exactement comme au clavier dans un terminal."""
    envoi = subprocess.run([python, "-c", _CTRL_C, str(pid)], creationflags=SANS_CONSOLE, timeout=15,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return envoi.returncode == 0


def tuer(pid: int) -> bool:
    """Arret force du processus et de ses descendants. Le dernier point de sauvegarde reste intact."""
    arret = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, encoding="utf-8",
                           errors="replace", creationflags=SANS_FENETRE)
    return arret.returncode == 0


def corbeille(chemins: list[Path]) -> None:
    """Envoie des dossiers a la corbeille de Windows, d'ou ils se restaurent. Leve OSError en cas d'echec."""
    # Liste de chemins absolus separes par un caractere nul, et terminee par deux.
    liste = ctypes.create_unicode_buffer("\0".join(str(c.resolve()) for c in chemins) + "\0")
    operation = _OperationFichiers(fonction=SUPPRIMER, depuis=ctypes.addressof(liste), drapeaux=VERS_CORBEILLE)
    code = shell32.SHFileOperationW(ctypes.byref(operation))
    if code != 0 or operation.abandon:
        raise OSError(f"la corbeille de Windows a refuse la suppression (code {code:#x})")
