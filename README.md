# Star Trek — NEW PC SETUP

Justice's music-video production line: **Comfort** (drives ComfyUI: Krea 2 pictures → MiniMax H3 video → 1080p60 finish),
**SongMap** (song → timing sheet), **FilmCraft** (the edit, built from cut lists), **Subtitle Studio** (lyrics on timestamps)
and the **Overseer** (the local AI that checks and keeps production going). Everything runs locally on an NVIDIA RTX GPU.

This page is only for putting Star Trek on a new Windows PC. **How to use it once it is installed: [OPERATING.md](OPERATING.md).**
The production rules (what a finished video must be) are in [README.txt](README.txt) — that page is the single source for rules.

> **For Claude:** follow the steps in order and run the commands yourself. Ask Justice only for the things marked **ASK**.
> Don't take control of his screen. Setup is one script and can be re-run safely; on a failure, read the last lines of
> `setup\setup_log.txt`, fix that one thing, then run it again.

---

## What the PC needs

| | |
|---|---|
| Windows 10 (1809 or newer, LTSC 2019/2021 included) or 11, 64-bit | winget is used when present; without it (LTSC) the setup downloads the official installers |
| NVIDIA RTX GPU, **24 GB VRAM** (built on an RTX 4090) | NVIDIA driver **580 or newer** (CUDA 13) |
| **64 GB RAM** recommended | **~250 GB free** on the drive that becomes `A:` |
| Internet | a GitHub login (this repo is private) and a free Civitai account (for 2 models) |

## Step 1 — the A: drive and the folder

Everything (configs, docs, song projects) uses these exact paths, so the PC must have them:

```
A:\Ai projects\Star Trek     <- this repository
```

- If the PC already has an `A:` drive, go to step 2.
- If not: **ASK** Justice which drive to use (it needs ~250 GB free), then give that drive the letter A: from an *admin* PowerShell window, e.g. for D:
  `Get-Partition -DriveLetter D | Set-Partition -NewDriveLetter A`
  (or Disk Management → right-click the drive → Change Drive Letter and Paths → A:). Shortcuts that pointed to the old letter must be redone.

## Step 2 — clone

```
winget install -e --id Git.Git
git clone https://github.com/JUSTIC3MAN/StarTrek.git "A:\Ai projects\Star Trek"
```
**No winget** (Windows 10 LTSC): install Git from its official release instead, in PowerShell, then open a new window and clone:
```
$r = Invoke-RestMethod https://api.github.com/repos/git-for-windows/git/releases/latest
$u = ($r.assets | Where-Object { $_.name -match '^Git-[0-9.]+-64-bit\.exe$' } | Select-Object -First 1).browser_download_url
Invoke-WebRequest $u -OutFile "$env:TEMP\git-setup.exe"; Start-Process -Wait "$env:TEMP\git-setup.exe" '/VERYSILENT /NORESTART /SP-'
```

**Claude on this PC:** if the Claude desktop app can't be installed (Windows 10 LTSC), use **Claude Code** in PowerShell:
`irm https://claude.ai/install.ps1 | iex`, open a new window, run `claude`, sign in. It supports Windows 10 1809+.

**No Git and no Claude on this PC?** That works too: on https://github.com/JUSTIC3MAN/StarTrek press **Code → Download ZIP**,
extract it into `A:\Ai projects\` and rename the folder `StarTrek-main` to `Star Trek`. The setup installs Git itself
(ComfyUI needs it) and clears Windows' "downloaded file" block on everything. The PC can't `git pull` updates that way;
download the ZIP again (or clone later) to update.

## Step 3 — run the setup

Double-click **`SETUP NEW PC.bat`** in `A:\Ai projects\Star Trek` (or run it from a terminal; it is the same thing).
**ASK** Justice for his **Civitai API key** when it asks (civitai.com → avatar → Account settings → API Keys → Add API key).
Pressing Enter skips it; run the setup again later with the key to fetch those two models.

It takes several hours the first time, almost all of it downloads. It does, in order:

1. Installs Git, Python 3.12, ffmpeg, Ollama, the VC++ runtime and (if there is no Edge or Chrome) Chrome: with winget when
   Windows has it, otherwise from the official installers. Skips what is installed.
2. Makes the folders, and the old-path links Justice's tools still use (folder junctions, nothing copied):
   `A:\ClaudeComfy` → `Star Trek\ClaudeComfy`, `A:\artcraft\FilmCraft` → `Star Trek\FilmCraft`,
   `A:\Ai projects\Comfort` → `Star Trek\Comfort`, `A:\Ai projects\ClaudeSubtitles` → `Star Trek\ClaudeSubtitles`.
3. Clones **ComfyUI v0.39.2** and the **26 custom node packs** at the exact commits from Justice's PC (`setup\custom_nodes.txt`),
   and puts the workflows (`ClaudeComfy\comfyui_user\`) into `ComfyUI\user\default\`.
4. Builds the ClaudeComfy Python env (uv, Python 3.12, PyTorch 2.10 + CUDA 13.0, every node requirement, NVIDIA VFX for the
   RTX upscaler) and test-starts ComfyUI (`ClaudeComfy\scripts\setup_claudecomfy.ps1`, Justice's own setup).
5. Downloads every model into `ClaudeComfy\ComfyUI\models\` (`setup\download_models.py`, list below).
6. Downloads **FilmCraft 0.10.0** (the exact build fc.py runs on; sha256 checked) into `FilmCraft\`.
7. Sets up **Subtitle Studio** (`ClaudeSubtitles\SubtitleStudio\setup.bat`: PyTorch, Qwen3-ASR, ~7 GB) and then
   **SongMap** (`SongMap\setup.bat`: Beat This!, SongFormer, ~3 GB; it uses Subtitle Studio's models for lyrics).
8. Pulls the local AI model: `ollama pull qwen3.6:27b` (~18 GB) — the Comfort agent and the Overseer both use it.
9. Writes Comfort's `config.json` / `launcher.json` for this PC (no change when the paths are the same as Justice's).
10. Puts the Caprasimo font (Sentimientos subtitles) in `A:\finished\sentimientos_style_tests\fonts`.
11. Checks everything and lists any model still missing.

Useful options: `SETUP NEW PC.bat -SkipModels` (everything but the models), and later just `SETUP NEW PC.bat` again.
Models only: `A:\ClaudeComfy\venv\Scripts\python.exe "A:\Ai projects\Star Trek\setup\download_models.py"` (`--list` = what is missing).

## Step 4 — before the first start

- **`Overseer\songs.txt`**: every song set to `auto` starts generating as soon as Comfort runs. The shot pictures and videos
  from the old PC are not in git (see below), so an `auto` song re-renders its missing shots. **ASK** Justice which songs
  should run; set the others to `off`. `Overseer\level.txt` = how much the local AI checks (strict / light / off, README.txt).
- Start: double-click **`Open Star Trek.bat`** → Comfort starts (with ComfyUI on port 8189 and Ollama), the Star Trek
  interface opens at http://127.0.0.1:8790/startrek. First start loads models for a few minutes.
- Check it is alive the right way (README.txt rule 8): `Comfort\heartbeat.txt` rewritten in the last 60 s.

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
| MiniMax H3 video (all H3 workflows) | `diffusion_models/MiniMaxH3/DasiwaMinimaxH3_dasiwaHybridV3_int8` (21 GB) | Civitai 2877206 v3 (3374445) — **API key** |
| | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq`, `vae/MiniMaxH3/*` (video fp16 + int8, audio fp32), `vae_approx/taeh3`, `latent_upscale_models/*`, `loras/MINIMAX/*` (DMAD turbo + 2 optional) | Comfy-Org/MiniMax-H3, Kijai, LBH-123-AI, silveroxides (HF) |
| Krea 2 pictures (Comfort's default) | `diffusion_models/Krea2/redcraftHybridH3Krea2t_30Krea2_fp8` (13 GB) | Civitai 958009 v3139241 — **API key** |
| Krea 2 edit / other angles (K>label) | `diffusion_models/Krea2/krea2_turbo_fp8_scaled`, `loras/Krea2/krea2_identity_edit_v1_2`, `text_encoders/Qwen3VL4B/*` (heretic + stock), `vae/qwen_image_vae` | Comfy-Org/Krea-2, conradlocke, DreamFast (HF) |
| Song looks | 31 Krea 2 style LoRAs `loras/<style>-comfy.safetensors` | ilkerzgi/krea-2-<style>-lora (HF) |
| 1080p60 finish + upscale | `frame_interpolation/rife_v4.26`, `rife/flownet.pkl`, `upscale_models/4x-UltraSharpV2`, `2x-AnimeSharpV4_RCAN` | Comfy-Org/Frame-Interpolation, hzwer/RIFE, Kim2091 (HF) |
| Image to 3D (Claude3D) | `pixal3d_int8_convrot`, `trellis_2_int8_convrot`, TRELLIS shape/texture VAEs, `dino_v3_L_naf_fp32`, `moge_2_vitl_normal_fp16`, `birefnet` | Comfy-Org (HF) |
| Local AI | `qwen3.6:27b` | Ollama |
| Lyrics / music analysis | Qwen3-ASR 1.7B, Qwen3-ForcedAligner, BS-RoFormer, SongFormer, Beat This! | Subtitle Studio + SongMap setups |

If a Civitai download says 401/403: the key is wrong, or the account needs to open the model page logged in and press
Download once. RedCraft 3.0 was marked free for everyone on Civitai in October 2026; if it asks for Buzz (payment) now, Comfort can
run Krea pictures on the stock `krea2_turbo_fp8_scaled` (change `"unet"` under `"krea"` in `Comfort\config.json` — **ASK** Justice first).

## Keeping two PCs in step

Code and project text: `git pull` before working, `git add -A && git commit -m "..." && git push` after (from
`A:\Ai projects\Star Trek`). Media (`Comfort\out`, `Preview`) is not in git: copy it by drive when needed.
