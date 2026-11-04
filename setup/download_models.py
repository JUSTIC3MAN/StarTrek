"""Download every model file Star Trek uses into ClaudeComfy\\ComfyUI\\models - the same files, names and folders as on
Justice's PC (checked 2026-11-03). Safe to re-run: files already in place (right size) are skipped, interrupted
downloads resume.

Run with the ClaudeComfy venv (setup_startrek.ps1 does this for you):
    A:\\ClaudeComfy\\venv\\Scripts\\python.exe setup\\download_models.py            everything
    ...download_models.py --list                                                  show what is missing, download nothing
    ...download_models.py --only civitai                                          one group (h3, krea, civitai, styles, finish, 3d)

Civitai files need a Civitai API key (civitai.com > Account settings > API Keys > Add API key). Give it as the
CIVITAI_TOKEN environment variable or put it alone in setup\\civitai_token.txt (that file is git-ignored).
Hugging Face files need no login.
"""
import hashlib, os, shutil, sys, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                   # the Star Trek folder
MODELS = ROOT / "ClaudeComfy" / "ComfyUI" / "models"
STAGING = MODELS / "_download_staging"
LOG = HERE / "download_log.txt"

GB = 1_000_000_000
# (group, destination under models/, source, file in source, size in bytes or None, sha256 or None, what uses it)
#   source "hf:<repo>" = Hugging Face, "civitai:<download url>" = Civitai (needs CIVITAI_TOKEN)
FILES = [
    # --- MiniMax H3 video (H3 Keyframe Chain, H3 Reference Video, Director, Seed Hunter) ---
    ("h3", "diffusion_models/MiniMaxH3/DasiwaMinimaxH3_dasiwaHybridV3_int8.safetensors",
     "civitai:https://civitai.com/api/download/models/3374445", None, None,
     "0ce4dfecce862b010823a5a74903543bd7f2ad21872272232f70f9a836d30e53",
     "DaSiWa MiniMax H3 Hybrid v3 int8 (civitai.com/models/2877206, version 3374445) - every H3 video workflow"),
    ("h3", "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "hf:Comfy-Org/MiniMax-H3",
     "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", None, None, "H3 text encoder"),
    ("h3", "vae/MiniMaxH3/minimax_h3_video_vae_fp16.safetensors", "hf:Comfy-Org/MiniMax-H3",
     "vae/minimax_h3_video_vae_fp16.safetensors", None, None, "H3 video VAE (Director)"),
    ("h3", "vae/MiniMaxH3/minimax_h3_video_vae_int8_convrot.safetensors", "hf:Kijai/MiniMax-H3-experimental",
     "minimax_h3_video_vae_int8_convrot.safetensors", None, None, "H3 video VAE int8 (Keyframe Chain, Reference Video)"),
    ("h3", "vae/MiniMaxH3/minimax_h3_audio_vae_fp32.safetensors", "hf:Comfy-Org/MiniMax-H3",
     "vae/minimax_h3_audio_vae_fp32.safetensors", None, None, "H3 audio VAE"),
    ("h3", "vae_approx/taeh3.safetensors", "hf:Kijai/MiniMax-H3-TAE", "vae_approx/taeh3.safetensors", None, None,
     "H3 live preview (Director)"),
    ("h3", "loras/MINIMAX/minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors", "hf:Kijai/MiniMax-H3-experimental",
     "loras/minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors", None, None, "H3 4-step turbo LoRA"),
    ("h3", "latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors", "hf:LBH-123-AI/Minimax_h3_latent_Upscaler",
     "minimax_h3_latent_upscaler_3d_conv_v1/minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors", None, None, "Seed Hunter"),
    ("h3", "latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors", "hf:LBH-123-AI/Minimax_h3_latent_Upscaler",
     "minimax_h3_latent_upscaler_3d_conv_v1/minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors", None, None, "DaSiWa workflow"),
    ("h3", "loras/MINIMAX/minimax_h3_fl2v_turbo_silver_dareties_comfy_pruned_v1.safetensors", "hf:silveroxides/MiniMax-H3_tests",
     "minimax_h3_fl2v_turbo_silver_dareties_comfy_pruned_v1.safetensors", None, None, "optional turbo LoRA (FL2VA)"),
    ("h3", "loras/MINIMAX/minimax_h3_ref2v_turbo_4step_v0.1_v4_step600_dareties_fro0975.safetensors", "hf:silveroxides/MiniMax-H3_tests",
     "ref2v_dareties/minimax_h3_ref2v_turbo_4step_v0.1_v4_step600_dareties_fro0975.safetensors", None, None, "optional turbo LoRA (REF2VA)"),
    # --- Krea 2 pictures (Krea 2 RedCraft, Krea2 From Image, Krea 2 Identity Edit) ---
    ("civitai", "diffusion_models/Krea2/redcraftHybridH3Krea2t_30Krea2_fp8.safetensors",
     "civitai:https://civitai.com/api/download/models/3139241?fileId=3019490", None, 13141826368,
     "f6088960c0febd27cbd372fc758bb07d012f2d8ae3cd10c45c903d48b94409ea",
     "RedCraft Krea2 3.0 fp8 (civitai.com/models/958009, version 3139241) - Comfort's default picture model"),
    ("krea", "diffusion_models/Krea2/krea2_turbo_fp8_scaled.safetensors", "hf:Comfy-Org/Krea-2",
     "diffusion_models/krea2_turbo_fp8_scaled.safetensors", None, None, "Krea 2 Turbo (Identity Edit / K>label angles)"),
    ("krea", "text_encoders/Qwen3VL4B/qwen3-vl-4b-heretic_fp8_e4m3fn.safetensors", "hf:DreamFast/Qwen3-VL-4b-Heretic-ComfyUI",
     "qwen3-vl-4b-heretic_fp8_e4m3fn.safetensors", None, None, "Krea text encoder + image-to-prompt"),
    ("krea", "text_encoders/Qwen3VL4B/qwen3vl_4b_fp8_scaled.safetensors", "hf:Comfy-Org/Krea-2",
     "text_encoders/qwen3vl_4b_fp8_scaled.safetensors", None, None, "Identity Edit text encoder"),
    ("krea", "loras/Krea2/krea2_identity_edit_v1_2.safetensors", "hf:conradlocke/krea2-identity-edit",
     "krea2_identity_edit_v1_2.safetensors", None, None, "Krea 2 Identity Edit LoRA"),
    ("krea", "vae/qwen_image_vae.safetensors", "hf:Comfy-Org/Krea-2", "vae/qwen_image_vae.safetensors", 253806246, None,
     "Krea VAE"),
    # --- 1080p60 finish and image upscale ---
    ("finish", "frame_interpolation/rife_v4.26.safetensors", "hf:Comfy-Org/Frame-Interpolation",
     "frame_interpolation/rife_v4.26.safetensors", 22674688, None, "Stage 1080p60 / Upscale and Interpolate (RIFE)"),
    ("finish", "upscale_models/4x-UltraSharpV2.safetensors", "hf:Kim2091/UltraSharpV2", "4x-UltraSharpV2.safetensors",
     139792588, None, "Comfort image upscale (#final, Gallery upscale)"),
    ("finish", "upscale_models/2x-AnimeSharpV4_RCAN.safetensors", "hf:Kim2091/2x-AnimeSharpV4", "2x-AnimeSharpV4_RCAN.safetensors",
     31053198, None, "upscaler"),
    # --- Image to 3D Pixal3D (Claude3D) ---
    ("3d", "diffusion_models/pixal3d_int8_convrot.safetensors", "hf:Comfy-Org/Pixal3D", "diffusion_models/pixal3d_int8_convrot.safetensors", 5584555824, None, "Pixal3D"),
    ("3d", "diffusion_models/trellis_2_int8_convrot.safetensors", "hf:Comfy-Org/TRELLIS.2", "diffusion_models/trellis_2_int8_convrot.safetensors", 5253048192, None, "TRELLIS.2"),
    ("3d", "vae/trellis_2_shape_vae_bf16.safetensors", "hf:Comfy-Org/Pixal3D", "vae/trellis_2_shape_vae_bf16.safetensors", 1095844024, None, "3D shape VAE"),
    ("3d", "vae/trellis_2_texture_vae_bf16.safetensors", "hf:Comfy-Org/Pixal3D", "vae/trellis_2_texture_vae_bf16.safetensors", 948461364, None, "3D texture VAE"),
    ("3d", "clip_vision/dino_v3_L_naf_fp32.safetensors", "hf:Comfy-Org/Pixal3D", "clip_vision/dino_v3_L_naf_fp32.safetensors", 1215214176, None, "DINOv3"),
    ("3d", "geometry_estimation/moge_2_vitl_normal_fp16.safetensors", "hf:Comfy-Org/MoGe", "geometry_estimation/moge_2_vitl_normal_fp16.safetensors", 661859924, None, "MoGe depth"),
    ("3d", "background_removal/birefnet.safetensors", "hf:Comfy-Org/BiRefNet", "background_removal/birefnet.safetensors", 444473596, None, "BiRefNet"),
]

# Krea 2 style LoRAs (fal series by ilkerzgi on Hugging Face) - the 31 on Justice's PC. A song's look = one of these
# (#lora <name>-comfy.safetensors:1.1 and the trigger "<name with spaces> style" at the end of each prompt).
STYLES = """aged-tempera-fable airy-gouache-minimalist amber-dusk-anime amber-ink-mist amber-silhouette-gothic
azure-sunlit-storybook bold-flash-tattoo bold-flatcolor-cartoon bold-impasto-sunlit bold-inked-anime-realism
bold-woodcut-linocut botanical-gouache-miniature cobalt-terracotta-risograph early-cgi-surreal-render
embroidered-textile-diorama ethereal-porcelain-mist flat-cel-anime foggy-neon-streak geometric-color-block
golden-impasto-oil golden-misty-xianxia graphic-novel-earthy-ink inked-comic-crosshatch iridescent-anime-nightscape
luminous-anime-film misty-anime-cinematic muted-plein-air-pastel neon-cyberpunk-anime orange-blue-riso-etching
pastel-dusk-anime pastel-rainbow-watercolor""".split()
for s in STYLES:
    FILES.append(("styles", f"loras/{s}-comfy.safetensors", f"hf:ilkerzgi/krea-2-{s}-lora", f"{s}-comfy.safetensors",
                  None, None, f"style LoRA, trigger '{s.replace('-', ' ')} style'"))

RIFE_PKL = ("finish", "rife/flownet.pkl")            # Seed Hunter's RIFE node (ComfyUI-VFI); fetched from hzwer/RIFE zip


def log(msg=""):
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


def human(n):
    return "?" if n is None else f"{n / GB:.2f} GB" if n >= 0.1 * GB else f"{n / 1e6:.0f} MB"


def token():
    t = os.environ.get("CIVITAI_TOKEN", "").strip()
    f = HERE / "civitai_token.txt"
    if not t and f.exists():
        t = f.read_text("utf-8").strip()
    return t


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(16 << 20), b""):
            h.update(b)
    return h.hexdigest()


def hf_size(repo, path):
    from huggingface_hub import get_hf_file_metadata, hf_hub_url
    return get_hf_file_metadata(hf_hub_url(repo, path)).size


def get_hf(repo, path):
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(repo_id=repo, filename=path, local_dir=STAGING / repo.replace("/", "__")))


def get_civitai(url, dest_name, size):
    tok = token()
    if not tok:
        raise RuntimeError("no Civitai API key: set CIVITAI_TOKEN or write it into setup\\civitai_token.txt")
    part = STAGING / (dest_name + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}", "User-Agent": "StarTrek-setup/1.0",
                                               **({"Range": f"bytes={have}-"} if have else {})})
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416 and have:              # already complete
            return part
        if e.code in (401, 403):
            raise RuntimeError(f"Civitai said {e.code}: the API key is wrong, or this account has no access to the file "
                               "(open the model page logged in and press Download once)") from e
        raise
    if have and r.status != 206:                # server ignored the range: start over
        have = 0
    total = (int(r.headers.get("Content-Length", 0)) + have) or size
    t0, last = time.time(), 0
    with open(part, "ab" if have else "wb") as fh:
        while True:
            b = r.read(8 << 20)
            if not b:
                break
            fh.write(b)
            have += len(b)
            if time.time() - last > 10:
                last = time.time()
                rate = (have / max(1, time.time() - t0)) / 1e6
                print(f"        {human(have)} of {human(total)}  ({rate:.0f} MB/s)", flush=True)
    return part


def fetch_rife_pkl():
    target = MODELS / RIFE_PKL[1]
    if target.exists():
        return True
    try:
        import zipfile
        z = get_hf("hzwer/RIFE", "RIFEv4.26_0921.zip")
        with zipfile.ZipFile(z) as zf:
            member = next(m for m in zf.namelist() if m.endswith("flownet.pkl"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        log("[rife/flownet.pkl] done")
        return True
    except Exception as e:  # noqa: BLE001
        log(f"[rife/flownet.pkl] FAILED: {e} (the RIFE node can also fetch it on first use)")
        return False


def main():
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    list_only = "--list" in sys.argv
    files = [f for f in FILES if not only or f[0] in only]
    MODELS.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    log(f"\n=== {time.strftime('%Y-%m-%d %H:%M')}  {len(files)} model files -> {MODELS}")
    failed, missing = [], []
    for i, (grp, dest, src, path, size, sha, why) in enumerate(files, 1):
        target = MODELS / dest
        kind, _, where = src.partition(":")
        if size is None and kind == "hf":
            try:
                size = hf_size(where, path)
            except Exception as e:  # noqa: BLE001
                log(f"[{i}/{len(files)}] {dest}: could not reach Hugging Face for its size ({e})")
        if target.exists() and (size is None or target.stat().st_size == size):
            continue
        missing.append(dest)
        log(f"[{i}/{len(files)}] {dest}  ({human(size)}) - {why}")
        if list_only:
            continue
        try:
            got = get_hf(where, path) if kind == "hf" else get_civitai(where, Path(dest).name, size)
            if size is not None and got.stat().st_size != size:
                raise RuntimeError(f"size mismatch ({got.stat().st_size} vs {size}) - run again to resume")
            if sha:
                log("        checking sha256 ...")
                if sha256(got) != sha:
                    got.unlink()
                    raise RuntimeError("sha256 mismatch - the download was damaged and was deleted; run again")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            os.replace(got, target)
            log("        done")
        except Exception as e:  # noqa: BLE001
            log(f"        FAILED: {e}")
            failed.append(dest)
    if not list_only and (not only or "finish" in only):
        fetch_rife_pkl()
    if list_only:
        log(f"{len(missing)} missing" + ("" if missing else " - all model files are in place"))
        return
    if failed:
        log("\nNot finished (run this again to resume):")
        for f in failed:
            log("  - " + f)
        sys.exit(1)
    shutil.rmtree(STAGING, ignore_errors=True)
    log("All Star Trek model files are in place.")


if __name__ == "__main__":
    main()
