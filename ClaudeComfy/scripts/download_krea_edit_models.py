"""Downloads the files the Krea 2 Identity Edit workflow needs. Safe to re-run (resumes, skips files already in place)."""
import os
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download

MODELS = Path(__file__).resolve().parent.parent / "ComfyUI" / "models"
STAGING = MODELS / "_download_staging"
# (destination under models/, Hugging Face repo, file in repo, size, what it is)
FILES = [
    ("loras/Krea2/krea2_identity_edit_v1_2.safetensors",
     "conradlocke/krea2-identity-edit", "krea2_identity_edit_v1_2.safetensors",
     "1.8 GB", "Krea 2 Identity Edit v1.2 LoRA (full rank)"),
    ("diffusion_models/Krea2/krea2_turbo_fp8_scaled.safetensors",
     "Comfy-Org/Krea-2", "diffusion_models/krea2_turbo_fp8_scaled.safetensors",
     "13.1 GB", "stock Krea 2 Turbo fp8 - the base the LoRA was built and tested for"),
    ("text_encoders/Qwen3VL4B/qwen3vl_4b_fp8_scaled.safetensors",
     "Comfy-Org/Krea-2", "text_encoders/qwen3vl_4b_fp8_scaled.safetensors",
     "5.2 GB", "stock Qwen3-VL-4B text encoder - the one the LoRA was trained with"),
]
ok = True
for i, (dest, repo, name, size, what) in enumerate(FILES, 1):
    target = MODELS / dest
    print(f"[{i}/{len(FILES)}] {dest}  ({size})")
    print(f"        {what}")
    if target.exists():
        print("        already in place - skipped")
        continue
    try:
        got = Path(hf_hub_download(repo_id=repo, filename=name, local_dir=STAGING))
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(got, target)
        print("        done")
    except Exception as e:  # noqa: BLE001
        print(f"        FAILED: {e}")
        ok = False
print()
print("All Krea 2 Identity Edit files are in place." if ok else "Some downloads failed - run the .bat again to resume.")
sys.exit(0 if ok else 1)
