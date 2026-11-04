# Star Trek — NEW PC SETUP

Justice's music-video production line, running locally on an NVIDIA RTX GPU:
- **SongMap** turns a song into a timing sheet.
- **Comfort** drives ComfyUI: Krea 2 pictures → MiniMax H3 video → 1080p60 finish.
- **FilmCraft** builds the edit from cut lists.
- **Subtitle Studio** puts the lyrics on timestamps.
- The **Overseer** is the local AI in charge.

**It runs without Claude.** Drop an MP3 into `Overseer\new_songs\` and the Overseer does everything with the local AI: the timing sheet, the art-style round, the shot list, every picture and video prompt, the checks, the FilmCraft edit. See [OPERATING.md](OPERATING.md). Claude is optional: it can still plan or fix things with few tokens.
The production rules are in [README.txt](README.txt), the single source for rules.

## Setup in four steps (no Git, no Claude needed)

1. Open https://github.com/JUSTIC3MAN/StarTrek → green **Code** button → **Download ZIP**.
2. Right-click the ZIP → **Extract All…** (anywhere, e.g. Downloads).
3. In the extracted folder, double-click **`SETUP NEW PC.bat`**. Windows may warn that the file came from the internet; choose **Run** / **Run anyway**.
   - **The PC has an A: drive:** setup copies everything to `A:\Ai projects\Star Trek`, the same place as on Justice's PC, and continues there. You can delete the extracted folder afterwards.
   - **No A: drive:** setup runs right where you extracted it.
4. When it asks for a **Civitai API key**, paste it (civitai.com → avatar → Account settings → API Keys → Add API key), or press Enter to skip. Without the key, Star Trek runs on official stand-in models (stock Krea 2 Turbo, Comfy-Org MiniMax H3 REF2VA). Run the setup again later with the key and it switches to DaSiWa H3 and RedCraft by itself.

The first run takes several hours, almost all of it downloads (~150 GB). Running it again is safe: finished steps are skipped and downloads resume.
When it says **SETUP FINISHED**, double-click **`Open Star Trek.bat`**. That starts Comfort with ComfyUI and the local AI, and opens the Star Trek interface.

> **For Claude** (if Claude is on this PC): run `SETUP NEW PC.bat` yourself and ask Justice only for the Civitai key. Don't take control of his screen.

## What the PC needs

| | |
|---|---|
| Windows 10 (1809+, LTSC 2019/2021 included) or 11, 64-bit | Admin rights help (Chrome install on LTSC) but most steps don't need them |
| NVIDIA RTX GPU, 24 GB+ VRAM (built on a 4090; a 5090 works) | NVIDIA driver **580 or newer** (CUDA 13) |
| 64 GB RAM recommended | **~250 GB free** disk |
| Internet | A free Civitai account for the two best models (optional, see step 4) |

## What the setup does

1. Installs Git, Python 3.12, ffmpeg, Ollama, the VC++ runtime and (if there's no Edge or Chrome) Chrome. It uses winget when Windows has it, otherwise the official installers. It skips what's already installed.
2. Clears Windows' downloaded-file block, makes the working folders, and (on A:) the old-path links Justice's tools still use: `A:\ClaudeComfy`, `A:\artcraft\FilmCraft`, `A:\Ai projects\Comfort`, `A:\Ai projects\ClaudeSubtitles`.
3. Clones **ComfyUI v0.39.2** and the **26 custom node packs** at the exact commits from Justice's PC (`setup\custom_nodes.txt`) and installs the workflows (`ClaudeComfy\comfyui_user\`).
4. Builds the Python environment (PyTorch 2.10 + CUDA 13.0, every node requirement, NVIDIA VFX for the RTX upscaler) and test-starts ComfyUI.
5. Downloads every model into `ClaudeComfy\ComfyUI\models\` (`setup\download_models.py`, list below).
6. Downloads **FilmCraft 0.10.0**, the exact build fc.py runs on, with its sha256 checked.
7. Sets up **Subtitle Studio** (Qwen3-ASR lyrics, ~7 GB) and **SongMap** (Beat This!, SongFormer, ~3 GB).
8. Pulls the local AI: `ollama pull qwen3.6:27b` (~18 GB). On a 32 GB card (5090) the stronger `qwen3.6:35b` fits: run `ollama pull qwen3.6:35b` and set `"model"` under `"llm"` in `Comfort\config.json`.
9. Writes Comfort's settings for this PC and checks everything.

Options: `SETUP NEW PC.bat -SkipModels` (everything but the models), `-AnyLocation` (set up where it is even with an A: drive).
Models only, any time: `ClaudeComfy\venv\Scripts\python.exe setup\download_models.py` (`--list` shows what is missing).

## Before the first start

`Overseer\songs.txt` lists Justice's songs. A song whose project folder isn't on this PC is skipped; copy its project over first (see below). `Overseer\level.txt` sets how much the local AI checks: strict / light / off (README.txt, OVERSEER LEVELS).

## What is in git and what is not

Git holds only what is needed to install and run Star Trek. Justice's project work and media stay on his PCs.

| In this repo | Not in git — Justice copies these from the old PC (same folders) |
|---|---|
| All program code, launchers, setups, docs and CLAUDE.md manuals | `FilmCraft\projects\` — the song projects (shot lists, plans, cut lists, .fcproj, MP3s, lyrics, SongMap sheets) |
| ComfyUI: every workflow (`ClaudeComfy\comfyui_user\`), Comfort's API workflows, the pinned node list, comfyui-krea2edit | `Comfort\songs\` — song briefs and picked pictures; `Comfort\lyrics\` |
| Comfort's config, presets, styles, guides; Overseer's rules, `songs.txt`, `level.txt` | `Comfort\inputs\` — reference images (Justice Man selfies etc.) |
| Format examples the manuals point to: `FilmCraft\projects\{floral,fauna,conqueress}\*.shots.txt`, `Comfort\jobs\done\*_styles_v2.*` | `Comfort\jobs\` history, `SongMap\out\`, `Comfort\out\` (every generated picture and video), `Preview\` |
| | Model files, venvs, FilmCraft exes — the setup downloads these |

To continue the songs on this PC, copy those folders from the old PC over the clone (merge, overwrite). Git ignores
them, so `git pull` never touches them. Song projects point at clips in `A:\Ai projects\Star Trek\Comfort\out\videos\`;
without them the Overseer renders new ones. Without a project's MP3 it can't build; SongMap remakes a sheet from the MP3.

## Every model file (all downloaded by the setup)

Into `ClaudeComfy\ComfyUI\models\` — sources and sizes are in `setup\download_models.py`.

| Use | Files | From |
|---|---|---|
| MiniMax H3 video (all H3 workflows) | `diffusion_models/MiniMaxH3/DasiwaMinimaxH3_dasiwaHybridV3_int8` (21 GB); without a key: `minimax_h3_ref2va_pruned_int8_convrot` | Civitai 2877206 v3 (3374445) — **API key**; stand-in: Comfy-Org/MiniMax-H3 (HF) |
| | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq`, `vae/MiniMaxH3/*` (video fp16 + int8, audio fp32), `vae_approx/taeh3`, `latent_upscale_models/*`, `loras/MINIMAX/*` (DMAD turbo + 2 optional) | Comfy-Org/MiniMax-H3, Kijai, LBH-123-AI, silveroxides (HF) |
| Krea 2 pictures (Comfort's default) | `diffusion_models/Krea2/redcraftHybridH3Krea2t_30Krea2_fp8` (13 GB); without a key: stock `krea2_turbo_fp8_scaled` | Civitai 958009 v3139241 — **API key** |
| Krea 2 edit / other angles (K>label) | `diffusion_models/Krea2/krea2_turbo_fp8_scaled`, `loras/Krea2/krea2_identity_edit_v1_2`, `text_encoders/Qwen3VL4B/*` (heretic + stock), `vae/qwen_image_vae` | Comfy-Org/Krea-2, conradlocke, DreamFast (HF) |
| Song looks | 31 Krea 2 style LoRAs `loras/<style>-comfy.safetensors` | ilkerzgi/krea-2-<style>-lora (HF) |
| 1080p60 finish + upscale | `frame_interpolation/rife_v4.26`, `rife/flownet.pkl`, `upscale_models/4x-UltraSharpV2`, `2x-AnimeSharpV4_RCAN` | Comfy-Org/Frame-Interpolation, hzwer/RIFE, Kim2091 (HF) |
| Image to 3D (Claude3D) | `pixal3d_int8_convrot`, `trellis_2_int8_convrot`, TRELLIS shape/texture VAEs, `dino_v3_L_naf_fp32`, `moge_2_vitl_normal_fp16`, `birefnet` | Comfy-Org (HF) |
| Local AI | `qwen3.6:27b` | Ollama |
| Lyrics / music analysis | Qwen3-ASR 1.7B, Qwen3-ForcedAligner, BS-RoFormer, SongFormer, Beat This! | Subtitle Studio + SongMap setups |

If a Civitai download says 401/403, the key is wrong, or the account needs to open the model page logged in and press
Download once. Until then the stand-in models are used (step 4). RedCraft 3.0 was marked free for everyone on Civitai in
October 2026; if it asks for Buzz (payment) now, Star Trek simply stays on stock Krea 2 Turbo for pictures.

## Updating

Download the ZIP again, extract it and double-click `SETUP NEW PC.bat`. On A: it updates `A:\Ai projects\Star Trek`
and keeps this PC's own settings: `Overseer\songs.txt`, `level.txt`, `planner.json`, `Comfort\config.json`.
Without an A: drive, extract the new ZIP over the old Star Trek folder first. A PC with Git can `git pull` instead. Media (`Comfort\out`, `Preview`) is never in git: copy it by drive when needed.
