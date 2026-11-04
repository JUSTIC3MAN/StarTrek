"""Download SongMap's models into SongMap\\models: SongFormer (Hugging Face) and the Beat This! checkpoint."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from smlib import models as M  # noqa: E402  (sets HF_HOME / TORCH_HOME to SongMap\models)


def main() -> int:
    print("          SongFormer (about 2.8 GB)...", flush=True)
    M.fetch_songformer()
    print("          Beat This! checkpoint...", flush=True)
    from beat_this.inference import load_model
    load_model("final0", device="cpu")
    print("          models ready in", M.MODELS, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
