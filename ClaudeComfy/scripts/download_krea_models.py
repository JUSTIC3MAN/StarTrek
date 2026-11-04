"""Downloads the uncensored Qwen3-VL-4B text encoder the Krea 2 workflow uses. Safe to re-run."""
import os
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download

MODELS = Path(__file__).resolve().parent.parent / "ComfyUI" / "models"
STAGING = MODELS / "_download_staging"
FILES = [
    ("text_encoders/Qwen3VL4B/qwen3-vl-4b-heretic_fp8_e4m3fn.safetensors",
     "DreamFast/Qwen3-VL-4b-Heretic-ComfyUI", "qwen3-vl-4b-heretic_fp8_e4m3fn.safetensors"),
]
ok = True
for dest, repo, name in FILES:
    target = MODELS / dest
    print(f"{dest}")
    if target.exists():
        print("    already in place - skipped")
        continue
    try:
        got = Path(hf_hub_download(repo_id=repo, filename=name, local_dir=STAGING))
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(got, target)
        print("    done")
    except Exception as e:  # noqa: BLE001
        print(f"    FAILED: {e}")
        ok = False
sys.exit(0 if ok else 1)
