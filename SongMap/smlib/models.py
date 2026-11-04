"""GPU models, loaded once per worker: Beat This! (beats + downbeats) and SongFormer (sections)."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
SONGFORMER_DIR = MODELS / "SongFormer"
os.environ.setdefault("HF_HOME", str(MODELS / "hf"))
os.environ.setdefault("TORCH_HOME", str(MODELS / "torch"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("MPLBACKEND", "Agg")


def device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def fetch_songformer(repo: str = "ASLP-lab/SongFormer") -> Path:
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo, repo_type="model", local_dir=str(SONGFORMER_DIR),
                      ignore_patterns=["SongFormer.pt", "SongFormer.safetensors"])
    return SONGFORMER_DIR


def _msaf_shim() -> None:
    """SongFormer's model.py imports msaf.eval (evaluation only). If msaf won't import, stand in for it."""
    import scipy
    if not hasattr(scipy, "inf"):
        scipy.inf = np.inf
    try:
        import msaf.eval  # noqa: F401
    except Exception:  # noqa: BLE001
        m, e = types.ModuleType("msaf"), types.ModuleType("msaf.eval")
        e.compute_results = lambda *a, **k: {}
        m.eval = e
        sys.modules["msaf"], sys.modules["msaf.eval"] = m, e


class Models:
    def __init__(self, beat_checkpoint: str = "final0", repo: str = "ASLP-lab/SongFormer"):
        self.ckpt, self.repo = beat_checkpoint, repo
        self.bt = None
        self.sf = None
        self.sf_error = ""

    def beats(self, mono: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
        if self.bt is None:
            from beat_this.inference import Audio2Beats
            self.bt = Audio2Beats(checkpoint_path=self.ckpt, device=device(), dbn=False)
        a, b = self.bt(np.ascontiguousarray(mono, dtype=np.float32), sr)
        a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        if len(b) > len(a):          # downbeats are the shorter list
            a, b = b, a
        return a, b

    def load_songformer(self):
        import torch
        if not (SONGFORMER_DIR / "model.safetensors").is_file():
            fetch_songformer(self.repo)
        d = str(SONGFORMER_DIR)
        os.environ["SONGFORMER_LOCAL_DIR"] = d
        if d not in sys.path:
            sys.path.append(d)
        _msaf_shim()
        from transformers import AutoModel
        m = AutoModel.from_pretrained(d, trust_remote_code=True, low_cpu_mem_usage=False)
        m.to(device()).eval()
        torch.set_grad_enabled(False)
        return m

    def sections(self, mono: np.ndarray, sr: int) -> list[dict]:
        if self.sf_error:
            raise RuntimeError(self.sf_error)
        if self.sf is None:
            try:
                self.sf = self.load_songformer()
            except Exception as e:  # noqa: BLE001
                self.sf_error = f"{type(e).__name__}: {e}"[:300]
                raise
        import soxr
        import torch
        y = np.ascontiguousarray(soxr.resample(mono.astype(np.float32), sr, 24000), dtype=np.float32)
        with torch.no_grad():
            res = self.sf(y)
        return [{"start": float(r["start"]), "end": float(r["end"]), "label": str(r["label"])} for r in res]
