"""Download the MiniMax H3 support files ClaudeComfy needs into ComfyUI\\models.

Safe to re-run: finished files are skipped and interrupted downloads resume.
Run it with the ClaudeComfy venv:  venv\\Scripts\\python.exe scripts\\download_h3_models.py
Add --singularity to also fetch Minimax-h3_Singularity (the REF2VA finetune the Seed Hunter author uses, 21 GB).
"""
import os
import shutil
import sys
import zipfile
from pathlib import Path

try:
    from huggingface_hub import get_hf_file_metadata, hf_hub_download, hf_hub_url
except ImportError:
    sys.exit("huggingface_hub is missing - run '1 - Setup ClaudeComfy.bat' first.")

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "ComfyUI" / "models"
STAGING = MODELS / "_download_staging"
LOG = ROOT / "download_log.txt"

# (destination under ComfyUI\models, Hugging Face repo, file inside the repo, what it is for)
FILES = [
    ("text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
     "Comfy-Org/MiniMax-H3", "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
     "Qwen3-VL 32B text encoder, NVFP4 (both workflows; works on RTX 40-series)"),
    ("vae/MiniMaxH3/minimax_h3_video_vae_fp16.safetensors",
     "Comfy-Org/MiniMax-H3", "vae/minimax_h3_video_vae_fp16.safetensors",
     "video VAE fp16 (DaSiWa default)"),
    ("vae/MiniMaxH3/minimax_h3_video_vae_int8_convrot.safetensors",
     "Kijai/MiniMax-H3-experimental", "minimax_h3_video_vae_int8_convrot.safetensors",
     "video VAE int8, ~1.5x faster decode (Seed Hunter default)"),
    ("vae/MiniMaxH3/minimax_h3_audio_vae_fp32.safetensors",
     "Comfy-Org/MiniMax-H3", "vae/minimax_h3_audio_vae_fp32.safetensors",
     "audio VAE (both workflows)"),
    ("vae_approx/taeh3.safetensors",
     "Kijai/MiniMax-H3-TAE", "vae_approx/taeh3.safetensors",
     "TAEH3 live-preview decoder"),
    ("latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors",
     "LBH-123-AI/Minimax_h3_latent_Upscaler",
     "minimax_h3_latent_upscaler_3d_conv_v1/minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors",
     "latent upscaler 2x (Seed Hunter)"),
    ("latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors",
     "LBH-123-AI/Minimax_h3_latent_Upscaler",
     "minimax_h3_latent_upscaler_3d_conv_v1/minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors",
     "latent upscaler 2x (DaSiWa)"),
    ("loras/MINIMAX/minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors",
     "Kijai/MiniMax-H3-experimental", "loras/minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors",
     "Kijai DMAD turbo LoRA - FL2VA and REF2VA (Seed Hunter default)"),
    ("loras/MINIMAX/minimax_h3_fl2v_turbo_silver_dareties_comfy_pruned_v1.safetensors",
     "silveroxides/MiniMax-H3_tests", "minimax_h3_fl2v_turbo_silver_dareties_comfy_pruned_v1.safetensors",
     "silveroxides dareties turbo LoRA for FL2VA"),
    ("loras/MINIMAX/minimax_h3_ref2v_turbo_4step_v0.1_v4_step600_dareties_fro0975.safetensors",
     "silveroxides/MiniMax-H3_tests",
     "ref2v_dareties/minimax_h3_ref2v_turbo_4step_v0.1_v4_step600_dareties_fro0975.safetensors",
     "silveroxides dareties turbo LoRA for REF2VA"),
]

OPTIONAL = {
    "--singularity": [
        ("diffusion_models/MiniMaxH3/Minimax-h3_Singularity_ref2va_Pruned_v1.3_int8.safetensors",
         "WarmBloodAban/Minimax-h3_Singularity", "Minimax-h3_Singularity_ref2va_Pruned_v1.3_int8.safetensors",
         "Singularity REF2VA finetune, pruned int8 (Seed Hunter author's model)"),
    ],
}
if any(flag in sys.argv for flag in OPTIONAL):
    for flag, extra in OPTIONAL.items():
        if flag in sys.argv:
            FILES += extra


def fetch_rife():
    """RIFE 4.26 flownet.pkl for the Seed Hunter 'RIFE Frame Interpolation' node (ComfyUI-VFI)."""
    target = MODELS / "rife" / "flownet.pkl"
    if target.exists():
        log("[RIFE] rife/flownet.pkl already in place - skipped")
        return True
    try:
        log("[RIFE] rife/flownet.pkl (22 MB zip from hzwer/RIFE)")
        z = Path(hf_hub_download(repo_id="hzwer/RIFE", filename="RIFEv4.26_0921.zip", local_dir=STAGING))
        with zipfile.ZipFile(z) as zf:
            member = next(m for m in zf.namelist() if m.endswith("flownet.pkl"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        log("        done")
        return True
    except Exception as e:  # noqa: BLE001
        log(f"        FAILED: {e} (the node can also fetch it by itself on first use)")
        return False


def log(msg=""):
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


def human(n):
    if n is None:
        return "size unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def main():
    STAGING.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for dest, repo, path, _ in FILES:
        try:
            sizes[dest] = get_hf_file_metadata(hf_hub_url(repo, path)).size
        except Exception as e:  # noqa: BLE001
            log(f"Could not read the size of {repo}/{path}: {e}")
            sizes[dest] = None
    todo = [d for d, *_ in FILES if not ((MODELS / d).exists() and (sizes[d] is None or (MODELS / d).stat().st_size == sizes[d]))]
    need = sum(sizes[d] or 0 for d in todo)
    free = shutil.disk_usage(MODELS).free
    log(f"{len(todo)} of {len(FILES)} files to download, {human(need)} total, {human(free)} free on the drive.\n")
    if need > free:
        sys.exit("Not enough free disk space.")

    failed = []
    for i, (dest, repo, path, why) in enumerate(FILES, 1):
        target = MODELS / dest
        size = sizes[dest]
        log(f"[{i}/{len(FILES)}] {dest}  ({human(size)})\n        {why}")
        if dest not in todo:
            log("        already in place - skipped")
            continue
        try:
            got = Path(hf_hub_download(repo_id=repo, filename=path, local_dir=STAGING))
            if size is not None and got.stat().st_size != size:
                raise RuntimeError(f"size mismatch ({got.stat().st_size} vs {size})")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            os.replace(got, target)
            log("        done")
        except Exception as e:  # noqa: BLE001
            log(f"        FAILED: {e}")
            failed.append(dest)

    fetch_rife()  # optional: the RIFE node can also download this itself on first use

    if failed:
        log("\nThese did not finish (re-run the script to resume them):")
        for f in failed:
            log("  - " + f)
        sys.exit(1)
    shutil.rmtree(STAGING, ignore_errors=True)
    log("\nAll MiniMax H3 support files are in place.")


if __name__ == "__main__":
    main()
