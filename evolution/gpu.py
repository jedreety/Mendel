"""Reglages GPU communs : appareil CUDA et mode deterministe."""
import os

import torch


def preparer() -> torch.device:
    """A appeler avant le premier calcul. Sans ces reglages, deux runs de meme graine divergeraient."""
    if not torch.cuda.is_available():
        raise RuntimeError("aucune GPU CUDA visible par PyTorch")
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")  # lu a la creation du premier contexte cuBLAS
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")
    return torch.device("cuda")
