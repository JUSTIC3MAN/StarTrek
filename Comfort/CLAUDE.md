# Comfort - operating manual for Claude
**Song videos: A:\Ai projects\Star Trek\README.txt is the single source (goal, process, Justice's rules). Where this file disagrees, the README wins.**
Read this first in any session that opens this folder. Full rewrite 2026-10-15, story-video lessons added 2026-10-20 (sections 14-15); keep it current when you change Comfort.

## 1. What Comfort is
Justice's own program for driving his ComfyUI ("ClaudeComfy") with minimal tokens. One double-click on **Comfort.exe** starts everything:
- Comfort.exe (Go launcher) starts `pythonw comfort_app.py` hidden and opens the UI in an Edge app window (http://127.0.0.1:8790).
- comfort_app.py runs the **inbox watcher** (executes job files Claude drops in `inbox\`), starts **Ollama** hidden (local master AI qwen3.6:27b) and **ComfyUI** hidden (A:\ClaudeComfy, port 8189).
- UI tabs: Agent (chat with the local AI), Workflows, Gallery (All / Photos / Videos switch since 2026-10-23; Videos lists every clip in out\videos with hover preview, player and its prompt/pictures; Upscale / Send to Agent on photos), Settings (Test AI speed, Quit).

| Windows path (Comfort + job files use these) | Device shell path (device_bash) |
|---|---|
| A:\Ai projects\Comfort | $HOME/mnt/Ai projects/Comfort |
| A:\ClaudeComfy | $HOME/mnt/ClaudeComfy |
| A:\Ai projects\Claude3D | $HOME/mnt/Ai projects/Claude3D |

The device shell is a Linux VM: it can NOT reach ports 8189/8790 and can NOT launch Windows programs. Talk to Comfort only through files. Paths inside job files are Windows paths (`A:\\...` with doubled backslashes in JSON).

## 2. Justice's rules (always)
- Finish the whole set he asked for, then let him judge. No re-rolls or self-corrections mid-way.
- A change = a fresh prompt.
- Krea 2 Identity Edit only when he asks for it (it is never the first option). Exception: song shot lists make a scene's other angles with Krea 2 edit (K>label) - that is part of the README process.
- Upscale only images he approved: re-run the same `#seed` with `#final WxH`.
- Battle arenas: high 3/4 camera ~35 deg down, big open floor in the lower 2/3, scenery only at the back and sides.
- Stay on exactly what he asked. Keep tokens low: one device_bash call per job, look at `_sheet.jpg` instead of every image.

## 3. Start of a session (one call, before sending anything)
- The device-shell path depends on what is connected: `$HOME/mnt/Ai projects/Comfort` when "Ai projects" is connected, `$HOME/mnt/Comfort` when only Comfort is (`ls $HOME/mnt` once). Connect A:\ClaudeComfy only when you need workflow files.
`cd "$HOME/mnt/Ai projects/Comfort"; cat status.txt; echo " age $(( $(date +%s) - $(stat -c %Y status.txt) ))s"; ls inbox`
- `idle ...` or `done ...` and age < 30 s = Comfort is running.
- `running ...` = busy; during a video render status can sit unchanged for many minutes.
- `idle`/`done` and age > 30 s = Comfort is not running. Ask Justice to double-click Comfort.exe. Jobs you queue meanwhile run once it starts.
- Files already in `inbox\` are queued jobs, possibly from another session (e.g. Claude3D). Don't delete or reorder them without asking.
- The timestamp text inside status.txt is his local time (UTC-6); the device shell clock is UTC. Use the mtime math above.

## 4. Inbox protocol
**OUTPUT LAYOUT (Justice, 2026-10-20): every video job puts its video in `out\videos\<job name>.mp4` (all videos in one folder) and its json/info (_done.txt, _manifest.json, _texts.txt) in `out\video_info\<job name>\`. Wait loop for a video job: `out/video_info/NAME/_done.txt` (line 1 OK/FAILED, then the full video path). Image jobs still go to `out\NAME\`. Song videos are always built in their FilmCraft project (README). For other clips: do NOT join them into a film unless he asks.**

- One file per job in `inbox\`: `NAME.txt` (Krea 2 image job) or `NAME.json` (everything else).
- Write it under a dot-name, then `mv` (atomic). Names starting with `_` or `.` are ignored.
- Jobs run one at a time in sorted filename order: prefix `1_`, `2_` to control order.
- Results go to `out\NAME\`. If `out\NAME` exists the job writes `out\NAME_2` - so use a NEW name every time or your wait loop will read the old `_done.txt`.
- The job file then moves to `jobs\done\` or `jobs\failed\` (+ `NAME.error.txt`).
- Per job: `_done.txt` (line 1 `OK ...`/`FAILED ...`, then one line per result), `_sheet.jpg` (contact sheet), `_prompts.txt` (final prompts), `_texts.txt` (text outputs of workflow jobs), `_manifest.json`.

Text job + wait (one device_bash call, timeout_ms 180000):
`D="$HOME/mnt/Ai projects/Comfort"; cd "$D"; printf '%s\n' '#name NAME' '#preset wide' 'PROMPT' > inbox/.t && mv inbox/.t inbox/NAME.txt; for i in $(seq 1 56); do [ -f out/NAME/_done.txt ] && break; sleep 3; done; cat out/NAME/_done.txt 2>/dev/null || cat status.txt`

JSON job: `cat > inbox/.t <<'EOF'` ... `EOF` then `mv inbox/.t inbox/NAME.json`, then the same wait loop.
Not done after one call: repeat only the wait loop. For videos, tell Justice the expected time and check back.

## 5. Job types

### 5a. Krea 2 image job - `NAME.txt` (default for images)
`#` lines set options for every prompt line below them; each other line is one prompt; `[k=v k=v]` at the start of a line overrides for that line only; `//` and `##` lines are comments.
- `#name N` output folder
- `#preset P` size/style bundle (section 8)
- `#style S[,S2]|none` suffix(es) from styles.json appended to the prompt
- `#size WxH` exact size (Krea 2: 1-2 MP, multiples of 16), e.g. 1536x864
- `#aspect 16:9` + `#mp 2` size from aspect and megapixels instead
- `#n N` images per prompt
- `#seed N|random` with n>1 a fixed seed gives seed, seed+1, ...
- `#final WxH|none` upscale after generating - ONLY for approved images
- `#upscale MODEL|none` upscale model (default 4x-UltraSharpV2)
- `#lora file:0.8`
- `#label x` file-name label
- `#steps N`
- `#pass2 off` skip the refine pass
- `#i2p IMG` image-to-prompt first: Qwen3-VL describes IMG, and the prompt line becomes the creative direction (`-` = none). The derived prompt goes to `_prompts.txt`, then it renders.
- `#wf i2p` prompt only, no render
- `#wf edit` + `#image IMG` (+ `#boost N`) = Krea 2 Identity Edit - only when Justice asks
- `#lora` works with `#wf edit` too (2026-10-26): style LoRAs (e.g. ilkerzgi Krea 2 Turbo styles) chain after the identity LoRA. Used for the Justice Man character set from his selfie (inputs\justice_ref1.jpg), lora 0.9. JUSTICE MAN (2026-10-28): he liked the v1 pictures where the gold scales-of-justice chest emblem showed (01, 04); v2 made the scales the motif in all 10. Use inputs\justice_ref_face.jpg (selfie cropped above his t-shirt): the full selfie leaked his shirt logo onto the suit in 4 of 10 v1 pictures; the crop fixed it. Job: jobs\done\justiceman_v2.txt.

IMG can be an absolute path, a file in `inputs\`, `out\JOB\file.png`, or a gallery description like `pond wide 3` (fuzzy-matched against `out\` folders). Prefer exact paths.

Example:
```
#name rez_forest_set_v4
#preset brawler_bg
#n 2
PROMPT ONE ON ONE LINE
[preset=brawler_prop n=1] PROMPT TWO ON ONE LINE
```
JSON form: `{"name": "x", "preset": "wide", "n": 2, "prompts": ["p1", {"prompt": "p2", "size": "1024x1024"}]}`

### 5b. Any workflow - `NAME.json`
`{"workflow": "<exact name>", "name": "out_name", "set": {"node_id.input": value, "Node Title.input": value}, "raw_set": {"node_id.input": value}, "images": {"node_id.image": "A:\\path\\img.png"}, "n": 1, "seed": "random", "free_after": false, "copy_to": "A:\\some\\folder", "copy_prefix": "x"}`
- `set` values are converted to the input's type; `raw_set` writes exactly (socket inputs such as `external_prompt_overwrite`).
- `images` are uploaded to ComfyUI for you (same IMG rules as 5a).
- `seed: "random"` re-randomises every seed / noise_seed / seed_value input each run; a number fixes them.
- `copy_to` copies results with clean names (`<prefix>_<name>.<ext>` + `<prefix>_previews.jpg`) into a project folder.
- `free_after: true` unloads ComfyUI models after the job.
- Node ids: read `guides\<workflow>.md` first. If you need more, list the nodes:
`python3 -c "import json,sys;g=json.load(open(sys.argv[1]));[print(k,v['class_type'],v.get('_meta',{}).get('title',''),[i for i,x in v['inputs'].items() if not isinstance(x,list)]) for k,v in g.items()]" "$HOME/mnt/ClaudeComfy/ComfyUI/user/default/comfort_api/NAME.api.json"`

### 5c. Video with audio (MiniMax H3 / DaSiWa) - `NAME.json`
**STAGE FINISH (Justice, 2026-10-25): every video job now automatically queues `<clip>_stage60` ("Stage 1080p60 (Comfort)": RIFE to 60 fps + RTX VSR to 1920x1080, audio kept, about 30 s). That _stage60 file is the deliverable for the concert screen; the raw 1376x768 24 fps clip stays as the source. Send Justice the _stage60 version. To skip it for one job add "stage": false.**

**VIDEO DEFAULT (Justice, 2026-10-20): always make videos with the multi-image workflow "H3 Keyframe Chain (Comfort)" (the Seed Hunter Reference-to-Video path: pictures pinned as first/last frame) and write each clip prompt as the transition from one picture to the next. Do NOT default to the DaSiWa workflow (make_video / "MiniMax H3 Director (Comfort)") - only when Justice asks for DaSiWa by name.**

`{"make_video": {"prompt": "...", "mode": "I2VA", "duration": 5, "width": 1376, "height": 768, "start_image": "A:\\path\\first.png", "end_image": null, "n": 1, "seed": "random", "name": "clip_name"}}`
- Modes: `T2VA` (text), `I2VA` (start image), `FL2VA` (first + last image), `L2VA` (last image).
- Sizes are multiples of 32 (auto-snapped): 1376x768 is the default, 768x1376 vertical. Duration is 2-15 s.
- Write the prompt per `guides\_h3_prompting.md`. make_video auto-repairs missing structure (alignment line, `[Shot 1]`, `non_diegetic_music`).
- Expect about 5 min for a 5 s clip and 12.5 min for 10 s at 1376x768. Tell Justice before starting long clips.
- Output: `.webm` with audio in `out\NAME\`.

### 5d. Ask the local AI - `NAME.json`
`{"agent": "request in plain words", "attachments": ["A:\\path\\img.png"]}`
qwen3.6 plans and runs its tools itself. The transcript goes to `agent_logs\NAME.txt` (lines `[tool]`, `[result]`, `[error]`, with file paths). Use this to test the local AI or when Justice wants it to work on its own; for normal jobs write 5a-5c directly, which is cheaper and exact.

### 5e. Utility jobs - `NAME.json`
- `{"convert_workflows": true, "only": ["Workflow Name"]}`: converts UI workflows from `ComfyUI\user\default\workflows\` into API exports in `comfort_api\` using headless Edge. Run it after Justice adds or changes a workflow; omit `only` to convert all.
- `{"name": "x", "download": [{"url": "https://...", "dest": "vae/file.safetensors"}]}`: downloads models into `ComfyUI\models\`. Resumable, skips files already present; the report goes to `out\x\_done.txt`.
- `{"filmcraft_build": "projects/<song>/<song>.txt", "name": "fc_<song>"}`: runs A:\artcraft\FilmCraft\fc.py build on Windows (no 3-minute shell limit; the device shell kills background jobs). Result line in out\fc_<song>\_done.txt. Use this for every FilmCraft build.
- `{"llm_benchmark": true}`: measures local AI speed into `llm_benchmark.json`.

## 6. Looking at results and delivering them
- Look: device_stage_files `["A:\\Ai projects\\Comfort\\out\\NAME\\_sheet.jpg"]`, then Read the returned stagedPath. One sheet shows the whole set; open single images only when needed.
- Send to Justice: stage the image or `.webm`/`.mp4`, then SendUserFile.
- Chat image into Comfort: copy it to `/mnt/user-data/outputs/`, use device_commit_files to write it to `A:\Ai projects\Comfort\inputs\name.png`, then run `md5sum` on the device to confirm (see the upload warning in section 10).

## 7. Workflows (`A:\ClaudeComfy\ComfyUI\user\default\comfort_api\*.api.json`)
| Workflow | Use | Key inputs |
|---|---|---|
| Krea 2 RedCraft (Comfort) | text to image (same engine as .txt jobs) | see guide |
| Krea2 From Image (Comfort) | image to prompt to image in one pass | img.image, gen.prompt, lat.width / lat.height |
| Krea 2 Identity Edit (ClaudeComfy) | edit keeping identity - only when Justice asks | 72.image, 84.prompt |
| MiniMax H3 Director (Comfort) | video + audio - use make_video | 2831.* (see guide) |
| Working | his original H3 Director graph (same as above) | |
| MiniMax H3 Seed Hunter (ClaudeComfy) | UI-only: its API export has missing links (Anything Everywhere supplies sampler/sigmas/VAE) - never run via API; use the next row | |
| H3 Reference Video (Comfort) | REF2VA from 3 pictures, each pinned as the first frame of its shot (Seed Hunter's single-pass path, rebuilt 2026-10-20) | pic1/pic2/pic3.image, ref.prompt, ref.length, key1/2/3.frame_idx - see guide |
| H3 Keyframe Chain (Comfort) | ONE continuous clip from a first picture (frame 0) to a last picture (last frame) - the building block for story films (section 14) | pic1.image, pic2.image, ref.prompt, ref.length |
| Upscale and Interpolate (Comfort) | RTX VSR (DaSiWa RTX Upscaler) to 1920x1080, then RIFE 4.26 x2 -> 48 fps, audio kept | load.video (full path) - see guide |
| Stage 1080p60 (Comfort) | DEFAULT for the concert screen: RIFE x5 at source size, every 2nd frame (60 fps), RTX VSR to 1920x1080, audio kept. 10 s clip = 29 s | load.video (full path) - see guide |
| Image to 3D Pixal3D (Claude3D) | image to textured .glb (queued for conversion 2026-10-15) | 122.image; see Claude3D\CLAUDE.md |

- Not convertible, so use the replacements: "Krea 2 RedCraft (ClaudeComfy)" -> "Krea 2 RedCraft (Comfort)", and "DaSiWa MiniMax H3 (ClaudeComfy)" -> "MiniMax H3 Director (Comfort)", and "MiniMax H3 Seed Hunter (ClaudeComfy)" -> "H3 Reference Video (Comfort)".
- The "(Comfort)" workflows are rebuilt automatically at app start if missing.
- Prompting rules: `guides\_krea2_prompting.md`, `guides\_h3_prompting.md`. Local AI rules: `guides\_agent_rules.md`. Read a workflow's guide before running it. When you add a workflow, write its guide in `guides\` (same file name as the workflow) - the app shows it and the local AI reads it.

## 8. Presets and styles (presets.json / styles.json, reloaded every job)
Krea 2 renders at about 2 MP. A preset's `target` is the size to upscale to only after Justice approves; nothing upscales automatically.
- General: square, square1k, portrait, landscape, wide (16:9), vertical (9:16), cinema (21:9), uhd
- BeatEmUp layers: concept, bg_sky, bg_far, bg_mid, landmark, floor_slab, floor_decals, prop, prop_tall, prop_wide, prop_sheet, foreground, portrait_card, portrait_bg
- Rez Me Energy brawler: brawler_bg (2.4:1, style rez_bg), brawler_prop (1:1, style rez_prop)
- Styles: be_scene, be_iso, be_topdown, be_topdown_cut, be_strip, be_sky, be_fg, rez_bg, rez_prop
- Widescreen single image: `#size 1536x864`.

## 9. The local master AI
- Ollama at 127.0.0.1:11434 (`%LOCALAPPDATA%\Programs\Ollama\ollama.exe`), model qwen3.6:27b (vision, tools, thinking). Settings are in config.json `llm`.
- VRAM handoff: it frees ComfyUI before thinking, unloads itself (keep_alive 0) before heavy tools, and frees ComfyUI again after them. It runs 115-127 tok/s with the GPU free and takes about 17 s to load cold. If it drops to about 6 tok/s, ComfyUI is still holding VRAM.
- Tools: generate, generate_from_image, image_to_prompt, list_workflows, describe_workflow, run_workflow, make_video, upscale, list_presets, recent_results, prompt_guide, find_images (gallery by name), look_at.
- Its instructions are AGENT_PROMPT.txt + `guides\_agent_rules.md` + the workflow guides + a list of the newest gallery jobs. Improve its behaviour by editing those files; Claude writes the guides.

## 10. Code map and changing Comfort
- `comfort.py`: core. Config, ComfyUI start/free, Krea / edit / i2p graph builders, .txt/.json job parser, `run_file` (inbox dispatcher), model downloads, gallery-name resolver, legacy `watch()`.
- `comfort_flows.py`: any-workflow engine (load / describe / `run_flow`, copy_to, upscale_image), workflow conversion, built-in workflows.
- `comfort_agent.py`: local AI (Ollama control, tools, `normalize_h3`, Agent loop).
- `comfort_app.py`: aiohttp server on 8790, inbox watcher thread, warm-up. `ui.html` is the whole UI.
- `config.json`: paths, models, sampler settings, i2p, llm. `launcher.json`: pythonw path, port, window size. Python is A:\ClaudeComfy\venv (3.12) - only aiohttp, Pillow and stdlib; don't add packages.
- `Comfort.exe` is the launcher, with source in `launcher_src\`. Rebuild in the container: `GOOS=windows GOARCH=amd64 go build -ldflags "-H windowsgui -s -w" -o Comfort.exe`. On launch it quits a running app that is older than the code on disk.

Editing rules:
- Edit code in place on the device with a short python read-modify-write, after saving a `.bak` copy. Check syntax with `python3 -m py_compile file.py`.
- device_commit_files can silently write an OLDER version of a file you re-staged from the same container path (it happened twice). Copy the file to a new unique file name in `/mnt/user-data/outputs/` before every commit, then compare `md5sum` in the container and on the device.
- The running app restarts itself when any of the 4 .py files changes, but only while idle. To force a restart, `touch comfort_app.py`.
- presets / styles / config reload every job; guides are read live.
- Only one inbox watcher may run. `watcher.lock` holds `owner|time`, and the app is owner `app`. "Start Comfort.bat" now just opens Comfort.exe; the old separate watcher loop is gone.

## 11. Known problems
- NEVER read status.txt while a job runs (2026-10-26): Comfort replaces it every few seconds and one read from the device shell at that instant made the replace fail (Access denied) and killed conqueress_keys_v1. set_status now retries (active after a Comfort restart), but still wait only with `[ -f out/NAME/_done.txt ]`.
- Gallery (2026-10-27): shows the 20 newest jobs / videos (ui.html asks ?limit=20); typing in the filter searches all. Justice found it slow with 80 jobs / 400 videos.
- CANCEL a running job: the "Cancel job" button in the Comfort app (shows while a job runs), or `touch inbox/_CANCEL` from the device shell (Comfort sends ComfyUI /interrupt and clears its queue; the node stops at its next step). Added 2026-10-25 after a 30-minute job couldn't be stopped.
- i2p returns empty text: TextGenerate needs thinking=True (config `i2p.thinking`, already on).
- H3 "reshape" error: width/height not multiples of 32.
- "Ollama not running" / "model not found": the app starts Ollama at launch; if it still fails, check that `ollama.exe` exists and look in comfort.log.
- Seed Hunter fails via API: it is UI-only.
- A converted workflow runs the wrong graph: conversion now validates node types. Bad exports were moved to `A:\ClaudeComfy\_to_delete`.
- Logs: `comfort.log` (jobs), `app.log` (app), `agent_logs\` (local AI transcripts), `jobs\failed\*.error.txt`.

- A workflow fails validation with "Value ... bigger than max of 4294967295 seed": random seeds are now capped at 32 bits in comfort_flows.py (2026-10-23); a fixed seed in a job must also be under 4294967295.

## 12. Timings on his 4090
- Krea 2 at 2 MP: about 17-20 s per image
- i2p: 10-20 s
- 4x upscale to 3840 wide: adds about 30 s
- H3 video (Director, 25 steps): 5 s clip about 5 min, 10 s about 12.5 min, 15 s about 24 min
- H3 Reference Video (turbo LoRA, 8 steps): 15 s at 1376x768 with 3 pictures about 6.5 min
- Pixal3D: a few minutes
- Stage 1080p60 (RIFE x5 + RTX VSR 1080p): 10 s clip 29 s. SeedVR2 7B took about 29 min for the same clip and was DROPPED (Justice: a waste of time); its model files were deleted 2026-10-25 at his request (the SeedVR2 custom node is still installed but has no models).

## 13. Other files
- `README.txt`: older job-format notes.
- `comfort_mcp.py`, `LOCAL_AI_SETUP.txt`, `lmstudio_mcp.json`: MCP alternative, not used.
- `Install Ollama.bat`: already run.
- `Start Comfort.bat`: opens Comfort.exe.
- `_to_delete\`: old items for Justice to delete.
- `.convert_profile\`: browser profile used by workflow conversion.
- `*.bak*`: backups from code edits.

Related: `A:\Ai projects\Claude3D\CLAUDE.md` covers the image-to-3D pipeline that runs through Comfort.

## 14. Story films from linked keyframes (learned 2026-10-20 - follow this)
Justice's brief: he gives a reference image; you make a short story film in its style, wide (16:9), that flows like one piece. He rated hard-cut versions "terrible".

Pipeline
1. Reverse-prompt his image for vocabulary: `#wf i2p` + `#i2p IMG` + `-` (5 s). Build one fixed style sentence from it and reuse it word for word in every picture prompt.
2. Plan the story as a CHAIN of keyframes and send him the plan in a few lines (he wants the plan before execution).
3. Write every keyframe prompt from the plan up front and queue them ALL in ONE .txt job (`#size 1376x768` = exact video size, `#n 1`, one prompt line per keyframe, `[label=k1]` ...), so Comfort renders them back to back with no idle GPU (about 12 s each). Justice found one-at-a-time too slow (2026-10-20: about 35 s idle between 12 s renders). Fastest (no idle gap at all): drop the keyframe job AND all clip jobs into inbox in the same call - `0_NAME_keys.txt` with `[label=k1]` ... `[label=k5]` per line gives fixed paths `out\NAME_keys\01-1_k1.png`, `02-1_k2.png` ..., and `1_NAME_c1.json` ... point pic1/pic2 at those paths. Clip prompts are then written from the plan, so describe each picture the way its keyframe prompt does. Justice also found an 80 s gap between the last picture and the first clip too long (2026-10-20). Show him the _sheet.jpg while the clips render; drift goes into the next version as an on-screen action, not a re-roll.
4. Render one clip per pair with "H3 Keyframe Chain (Comfort)": clip N starts on picture N and ends on picture N+1.
5. Only if Justice asks for a joined film (by default he edits the clips himself) - join on the device: `cd <Comfort>/out; python3 -I ../join_chain.py NAME/NAME.mp4 c1.mp4 c2.mp4 ...` (0.5 s dissolve + 0.5 s audio crossfade + loudnorm -20 LUFS; ffmpeg is in the device shell). Do the join on the device: device_commit_files refuses files over 30 MB.
6. Stage the film and send it.

Rules
- Every clip LONGER than 6 s, and the lengths vary (e.g. 8.7 / 10.1 / 7.3 / 11.5 s). ref.length frames (17k+5 grid): 158 = 6.6 s, 175 = 7.3, 192 = 8.0, 209 = 8.7, 226 = 9.4, 243 = 10.1, 260 = 10.8, 277 = 11.5, 294 = 12.25, 311 = 13, 362 = 15 (max).
- One continuous shot per clip, ONE camera idea: glide forward, push in, pedestal up/down, tilt up/down, slow pull back. These stayed continuous every time.
- Make in-between pictures for every action (a separate picture of her stepping into the window) and for every big camera change. Each clip should only travel a short way.
- Plan each next picture from the previous one: same subject position, facing and direction of travel; camera stays on one side (180-degree rule); landmarks sit where the move would put them (tilt up = things slide down in frame; arc right = background swings left).
- Describe the character with identical wording in every prompt. Krea still drifts (hood up -> down, lantern in hand vs on staff, moon size). Don't re-roll: write the change into the clip as an on-screen action ("she pushes her hood back").
- Finish the set, then let him judge. Report problems plainly (where, what, why, the fix).

Transitions - what happened
- Chained first/last frames + 0.5 s dissolve: joins invisible. WORKS.
- Forward glide, push-in, tilt, pedestal inside a clip: continuous. WORKS.
- Push through a portal (camera follows her through the rippling window glass): continuous. WORKS.
- A foreground element crossing the lens (a dove's wing) carries a cut as match-on-action: better than a plain cut, still a cut.
- Orbit/arc around the subject, or switching to a very different angle (behind -> side, side -> directly behind) in one clip: H3 put a HARD CUT mid-clip (lantern film clips 3 and 4). FAILS without an in-between keyframe partway round.
- Three pictures pinned at the starts of equal 5 s shots inside one 15 s "H3 Reference Video" clip: reads as 3 separate videos. FAILS - don't use it for story films.
- A picture pinned mid-shot at a different angle from where the move is heading: hard jump. FAILS.
- Ink Moon film (2026-10-20): clip 1, a slow push-in while the light falls from white paper to black night (moon glowing, cat turning to white line art) and back, he called great - dynamic, composed like a real show. Use a light change like that only when it fits; he said not to push color shifts into every film. Clip 2, crouch to mid-air leap plus a tilt in one 7.3 s clip: the leap finished in 2 s, then held, and the cat went smooth and flat. He called it cartoonish with a janky AI feel. FAILS. Tried fix: an in-between keyframe at the push-off, slow-motion wording, and a line saying the subject keeps its brushed texture and is never a smooth flat cartoon shape. He rated the redos (c2a push-off, c2b slow-motion rise, c4b crow into the moon with the page flooding to ink-black night) all bad and said to stop generating. He liked only the beginning of c4b, where the page floods to ink-black from the edges. Of this film he kept c1 and c3 (c3's cat-to-crow burst was 'cool' and dynamic).

Prompts (official MiniMax REF2VA format; source: DaSiWa-Nodes data/h3_forge.json, modes.REF2VA.system)
- subject_definitions: <Subject 1> = character (full outfit + how she moves), <Subject 2> = style, citing the pictures; "<Picture 1> is the first frame of [Shot 1], showing ..." and "<Picture 2> is the last frame of [Shot 1], showing ...".
- summary: "[keyframe completion + reference generation] An N-second 16:9 single continuous shot ... from <Picture 1> to <Picture 2>: ...".
- retention_analysis: one line per subject and picture ("<Picture 2> ([Shot 1] last frame): fully_preserved - ...").
- detailed_description: one style sentence, then "[Shot 1] The shot begins from <Picture 1>. ... one camera move ... The camera is still moving as the shot ends on <Picture 2>. No cut or transition occurs." About 200 words is enough for a single shot.
- overall_soundscape: diegetic sounds that fit the action. non_diegetic_music: N/A for joined clips (each generation would start its own score); he can lay his own track, or add one score pass at the end.

Timings on the 4090: Krea picture 10-20 s; chain clip 6.6 s ~2 min, 8 s ~2.5 min, 10 s ~3.5 min, 12.25 s ~4.5 min; 15 s REF2VA ~6.5 min; Director (25 steps) 15 s ~24 min.

## 15. Token budget (Justice pays for every call)
- Every tool call re-sends the whole chat, so long sessions get expensive fast. One project per chat; start a new chat when a film is done.
- Don't poll. After queueing, use ONE wait loop or a scheduled check-in (send_later), not repeated status calls.
- Don't Read every picture or video frame. Look at _sheet.jpg; check video frames only when a problem is suspected or he asks.
- Hand multi-step work to Comfort's local AI (5d agent job): one brief with keyframe paths, the clip list (first/last picture, ref.length, action, camera move) and the rules above. It writes the prompts and runs the workflows locally; Claude only joins and delivers.
- Keep messages to him short.


## 15b. Song video projects (2026-10-25)
Each song has a FilmCraft project in A:\artcraft\FilmCraft\projects\<song>\ (cut list + .fcproj + render), built from the `_stage60` clips. Edit them through fc.py only - see A:\artcraft\FilmCraft\CLAUDE.md.
AUTO (Justice, 2026-10-25: "when you make a clip for any of the projects add them to the filmcraft so I can see them in context"): when a `<song>_vid<N>` clip's Stage 1080p60 finish completes, comfort_flows.filmcraft_add() appends it to projects\<song>\<song>.txt with a 16-frame dissolve (or its fc_in) and queues `fc_<song>.json` (filmcraft_build) - the joined edit rebuilds by itself on Windows (about 50 s for 30 s of video). Name new project clips `<song>_vid<N>` so this works; send Justice the rebuilt edit.
NEW SCENES (Justice, 2026-10-25): don't only extend the chain. Sometimes start a fresh scene from new pictures in the same art style and join it with a real FilmCraft transition (glitch, flash, whip, leak, chroma, burn...). Put `"fc_in": "luma_fade 40 invert"` (transition INTO this clip, frames at 60 fps, plus params) in the clip's job; it carries to its stage job and into the cut list. Chained clips (starting on the previous last frame) get `dissolve 16`. CHOOSE TRANSITIONS AND READ RAMPS BY SECTION 17 - never default to dissolve/flash.

## 16. Song art for music videos (2026-10-23) - same text as README.txt
```
SONG ART FOR MUSIC VIDEOS - what Justice taught (2026-10-23)
Folders: songs\<Artist - Song>\  ->  lyrics.txt, brief.md (analysis, concept, prompts, lyric behind each picture), images\v1..v4\

0. FIND THE STYLE FIRST: A STYLE ROUND (Justice, 2026-10-27)
- To find a song's art style, the 5 pictures are 5 DIFFERENT art styles - never 5 pictures in one style. Five
  pictures in one style is not a choice of style, it is redundant.
- NEVER THE SAME SCENE IN EVERY PICTURE (Justice, 2026-10-28: Talawa v1 drew one scene 15 times - "never do that again").
  Every picture takes its inspiration from a DIFFERENT part of the lyrics (intro, each verse, chorus, outro), so he gets
  a real range of options: different subjects and moments AND a different style in each. Write the lyric line and its
  time behind every picture in brief.md. Each is a best attempt: its own tuned style sentence, the palette and light that
  suit that style and that moment, its LoRA + trigger. He may ask for more than 5 (Talawa: 15).
- Take the 5 from different families (anime film, oil/impasto, watercolour/gouache, print, ink, textile/craft,
  graphic poster), grounded in the ilkerzgi download ranking and matched to the song. Never photoreal, never tattoo flash.
  One .txt job per song: [label=<style> lora=<style>-comfy.safetensors:1.1] per line (example: jobs\done\*_styles_v2.txt).
- Only after he picks a style: the 5-picture storyboard (keyframes) in that one style, then the video clips.
- PREVIEW: copy every song picture set to A:\Ai projects\Star Trek\Preview\<Artist - Song>\ as "<version> <style> <n>.png"
  (device_bash cp: zero image tokens) and tell him it is there. Pictures go to Preview, not into the chat
  (an image Claude reads costs about 1,500 tokens and is re-sent with every later call); look at _sheet.jpg once per set
  only to catch problems.

1. EACH SONG IS ITS OWN PROJECT
- Analyse only that song's lyrics, give it its own art style, and never blend songs into one analysis or prompt.
- 5 pictures per song at 1376x768 (= H3 video size). Justice picks which ones go to video.

2. ART IS AN EXTENDED METAPHOR
- Make the viewer FEEL the song's specific details without literally showing the subject. His example: a dying butterfly can stand for the death of a child, the loss of innocence, without showing a body. Learn the principle; don't reuse butterflies.
- Don't act the lyrics out. v1 showed the singer at a border fence, holding fire, crossing a river: "terrible".
- Don't put Rasta men or the artist in every frame. A figure only appears where it serves the image, as a silhouette or fragment (a sneaker, raised hands).
- Keep the song's own identity and world. The metaphor has to come from the song's culture and scene, not an unrelated nature documentary. v2 used sea turtle hatchlings for a border song and bees for a weed song: rejected. Real Herbalist is a marijuana song, so show smoke, the leaf, the chalice, jars and haze.
- It is for a music video and stage projection, so every frame must be cool and aesthetic, like an album cover or a still from a great music video.
- Metaphor objects that worked: empty clothes billowing on a line (ghost town), a marimba played by the wind, a bell rope swinging alone, lit windows in an empty street, smoke forming mountains, smoke turning into a galaxy, glowing jars as lanterns, a sneaker stepping over a border line, fence shadows on a sound system, a map tearing off a wall, colour rings radiating from a small figure, cupped hands holding a small sun.

3. ART STYLE: NO PHOTOREALISM, AND NOTHING FROM THIN AIR
- Ultra-realistic or photographic looks were rejected (v1-v3).
- Ground the style in data, then match it to the song's mood:
  a) Rankings of the 1,500+ Krea 2 style LoRAs (ilkerzgi) by downloads and likes:
     https://huggingface.co/api/models?author=ilkerzgi&sort=downloads&direction=-1&limit=60   (also sort=likes)
  b) Community surveys, e.g. Creative Boom's top illustrators of 2026 (voted by 1,000+ creatives): flat gouache, graphic print, detailed ink.
- v4 results:
  WORKED ("much better"): luminous-anime-film (Real Herbalist, #1 by downloads), orange-blue-riso-etching (Cruzando Fronteras), aged-tempera-fable (Ciudad Fantasma), airy-gouache-minimalist (Sentimientos).
  FAILED ("terrible"): bold-flash-tattoo (Dem Cyaan). Don't use tattoo flash. Its designs also sat small in empty cream paper, which is wrong for a 16:9 video frame.

4. KREA 2 PROMPTING THAT WORKED
- Style LoRA: use a Comfort download job to put <name>-comfy.safetensors in ComfyUI\models\loras (URL https://huggingface.co/ilkerzgi/<repo>/resolve/main/<name>-comfy.safetensors), then put  #lora <name>-comfy.safetensors:1.1  in the job and the trigger phrase (e.g. "luminous anime film style") at the END of every prompt.
- One fixed style sentence, reused word for word in all 5 prompts of a song, placed right after the subject.
- Order: subject + action -> style sentence -> composition (camera, framing, where things sit, what stays empty) -> lighting -> concrete colours -> "no people, no text, no watermark".
- Write a lyric anchor for every picture (the line it comes from) in brief.md.
- Negative prompts do nothing. Say what you want. "No people" helps, but Krea still adds hands sometimes.
- NUDITY RISK: Krea painted nude figures twice ("bodies painted as thin washes of color", "a mural of musicians and dancers"). Always state the clothing for any figure, even painted ones ("fully clothed musicians in long skirts and white shirts"). That fixed it.
- Shapes formed by other things (hills forming a woman's face in profile) usually don't come out. Use direct objects.
- Job setup: one .txt job per song, #size 1376x768, #n 1, #seed random, #style none, [label=x] per line. Queue all songs (and any downloads as 0_*.json) in one call. About 55 s per 5-picture job on the 4090.

5. PROCESS
- When the direction changes, send Justice a short concept list per song before rendering.
- Finish the whole set, then let him judge. No re-rolls midway.
- Check _sheet.jpg. Open a full image only when you suspect a problem (nudity, hands). Report problems plainly: which picture, what went wrong, and the fix.
- When asked "why this style", answer with sources and data, never taste alone.
6. WHAT JUSTICE PICKED (after v4) AND WHY IT WORKS
Picks are in songs\<song>\picks\ (prefix = version). Liked: Ciudad v4 ropa/campana/mural/ventanas and v1 watercolor mapa/viento/firma; Fronteras v4 linea/reja/manos; Herbalist v4 frascos/aros and v3 aros; Sentimientos all of v4 (gouache), v2 pastel gota/tormenta/raices/danza, v1 adentro. Dem Cyaan: nothing (Baroque v1, volcano v2 and tattoo v4 all failed).
What the picks share:
- LIGHT IS THE SUBJECT: glowing windows, jars glowing like lanterns, rings of light in dark water, a light burst behind the crowd, a little sun in cupped hands, roots lit from inside.
- ABSENCE / IMPLIED PRESENCE: empty clothes on the line, a bell ringing alone, lit windows in an empty street, a sneaker or raised hands instead of a person, faceless crowned men instead of a named politician.
- RINGS, RIPPLES, RIBBONS radiating outward (drop, dance on the lake, figure on the hill, smoke rings, ribbons of voices). This is sound and vibration made visible, and it animates well.
- ONE CLEAR IDEA PER FRAME with calm negative space and a strong focal point (a vanishing point down the street, a centred ring, a tiny figure in a vast field).
- A HAND-MADE SURFACE: tempera cracks, watercolour bleed, riso grain and misregistration, pastel strokes, gouache paper, painted anime light. Never a photo look.
- A TIGHT PALETTE per song: two riso inks, muted tempera, blue-green on black, soft pastel gouache.
- Figures: tiny in vast space, a lone figure in one strong colour (a woman in a red dress in the wind), or satirical allegory. Never the artist acting the lyrics.
- BUILT-IN MOTION for the video stage: wind in cloth and hair, ripples, smoke, a swinging rope.
What failed: photoreal; nature-documentary swaps; tattoo-flash icons alone on empty paper (cliche symbols, no space or atmosphere); generic fantasy volcano; storybook ceiba; the literal singer.
v5 (2026-10-23): 5 new pictures per song built on these traits, keeping each song's winning style. Dem Cyaan moved to amber-ink-mist (#18 by downloads), with light in darkness and rings.
```

## 17. Transitions and speed ramps (2026-10-25) - same text as README.txt
```
TRANSITIONS AND SPEED IN THE FILMCRAFT EDITS - what Justice taught (2026-10-25)
Justice: "you are pretty lazy with transitions, it seems you only like to do a flash transition." The first edits were all dissolve 30 plus a lone flash/glitch/leak. Don't do that again.

1. SPEED RAMPS - automatic, inside FilmCraft (2026-10-27: they were OFF in fc.py unless a cut list said `ramp on` - fixed: now ON for every build and each clip keeps its cut length, so SongMap cuts stay on the beat. Star Trek\README.txt rule 1) (never re-time clips in Comfort: Justice wants FilmCraft to own speed)
- Problem he saw: "a slow down and then rapid acceleration" at joins. Cause: H3 keyframe clips ease into their pinned last frame and ease out of their first one. Measured 2026-10-25: the last 20-30 % of most clips is nearly still.
- Every fc.py build now measures each clip (A:\artcraft\FilmCraft\ramp.py: ffmpeg at 128x72 on his PC, cached in projects\<song>\_motion\, zero tokens) and speeds the stalls up (up to 3x, fastest rush eased to 0.85x) with gradual slopes like Premiere speed-ramp handles. It is built as short constant-speed pieces with frame blending, editable in FilmCraft (Speed/Duration). FilmCraft 0.10 stores Time Remapping keyframes but does not render them (tested), so don't use those.
- Clips come out about 15-25 % shorter (the dead time is gone). Plan more clips per song to fill the length.
- To check a ramp, read projects\<song>\<song>.ramps.txt: one line per clip, motion as rendered -> after (. still, - = + * # moving). Don't watch the video for this.
- Justice can still name a spot: a line `speed 7.5-9.4 160` under the clip line (clip seconds, percent). `noramp` at the end of a clip line keeps that clip as rendered; `ramp off` or `ramp 0.6` (strength) for the whole edit.

2. CHOOSING A TRANSITION
- CHAINED clips (B starts on A's last frame) are one continuous camera move, so any blend there is invisible: use dissolve 12-16. At most one or two chained joins per song get an ACCENT that means something on that beat: light_sweep when light arrives, cross_zoom 20-24 (strength 30-40) when the camera goes through an opening, glow when fire flares. Never a flash on a chained join.
- NEW-SCENE joins carry the edit. Choose from what the two shots share (match-cut practice; Insta360 and Vidpros transition guides; CapCut 2026 trends):
  a) MOTION CONTINUES (match on movement): whip 12-18, push 20-30, directional_blur_transition, travel_motion. direction = the side the camera is moving toward (camera rises -> direction=north, glides left -> west). Push-in into push-in = zoom-through: cross_zoom 18-30 (center=x,y in pixels = the point you push toward) or zoom_blur.
  b) SHAPE OR LIGHT MATCHES (graphic match): a lit window becomes a falling glowing drop, stars become a dew glint, a speaker cone becomes the next circle. Let the light carry it: luma_fade (dark/ink parts go first; `invert` = bright parts first), additive_dissolve, flare, ray, glow, light_leak in the song's colour (color=#rrggbb).
  c) MATERIAL OF THE WORLD: water -> wave, liquid_distortion. Mist or smoke -> blur_dissolve (blur 60-100). Ink -> luma_fade. Old paint or paper -> film_dissolve, grunge (edge_color in the palette), burn_alpha. Print -> chroma_leak (ink misregistration), stripe. Riot or digital energy -> glitch, vhs_damage, earthquake.
  d) ENERGY OF THE MUSIC: loud transitions (flash 4-8 frames, glitch 8-14, earthquake 10-15, chroma_leak) only on a hard hit or drop, at most one per ~30 s. Soft passages get luma fades, soft wipes and dissolves of 30-48 frames.
  e) TIME PASSING or a new chapter: dip_to_black 30-60, or dip_to_color in the song's palette.
- LENGTHS at 60 fps: whips, glitches and swipes 0.2-0.5 s (12-30 frames); match, mask and luma transitions 0.5-1 s (30-60). Reggae one-drop is about 70-80 BPM, so one beat = 45-51 frames and half a beat = about 24: fit lengths to a beat or half beat.
- VARIETY: never the same visible transition twice in a row (the invisible chained dissolves don't count). One family per song does most of the work (palette below) plus one surprise.
- DATED (1980s-90s wipes, avoid unless it's a deliberate joke): star_wipe, iris_*, heart and star shapes, cube_spin, page_turn, spin_3d, checker_wipe, venetian_blinds, flip_over.
- Concert edits start with fadein 18-30 and end with fadeout 40-60.

3. PALETTE PER SONG (start here)
- Ciudad Fantasma (aged tempera fable): luma_fade, film_dissolve, grunge (edge_color=#3a2414), blur_dissolve for ghostliness, light_sweep for warm dawn. No digital glitch.
- Cruzando Fronteras (orange-blue riso etching): chroma_leak and glitch (riso misregistration), stripe in riso orange, whip or push in the crossing direction, cross_zoom on the bass, linear_wipe as a line being crossed.
- Real Herbalist (luminous anime film): light_sweep, flare, glow, warm light_leak, wave or liquid_distortion for smoke, cross_zoom for dreamy push-ins.
- Dem Cyaan (amber ink mist): luma_fade (ink spreading), blur_dissolve (mist), glow or burn_chroma for fire, dip_to_color amber.
- Sentimientos (airy gouache minimalist): additive_dissolve, soft_wipe (a brush wash, feather 400+), shape_dissolve circles from the centre (rings), wave, long dissolves.
- Lily Pad (painterly pond into space): wave, liquid_distortion, ray (light shafts), cross_zoom into space, glow for stars.

4. HOW TO WRITE IT
- Before choosing, read how A ends and how B starts: the summary line of each clip's prompt in out\video_info\<clip>\_manifest.json (camera move, what fills the frame).
- In the clip's Comfort job: "fc_in": "luma_fade 40 invert" (it lands in the cut list). Or edit projects\<song>\<song>.txt and queue fc_<song>.json.
- Params go after the frames: `> whip 15 direction=east blur=90`, `> light_leak 30 color=#ffb070 amount=60`, `> cross_zoom 24 center=960,540 strength=35`, `> shape_dissolve 48 shape=circle order=center_out`. All 112 FilmCraft transitions with their params and defaults are listed in A:\artcraft\FilmCraft\transitions.txt.
```

## 18. Overseer (2026-10-27) - the local AI in charge of song-video production
process_inbox_once() calls overseer_tick() before each job: it runs Star Trek\Overseer\overseer.py tick (feeds the next
batch, checks pictures and shots with the local vision AI, re-makes failures, builds). Full description: Star Trek\README.txt
rule 7. Agent tool star_trek (comfort_agent.py) lets the local AI chat control it. Never block it with wait loops.
