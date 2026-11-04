# Stage 1080p60 (Comfort)
DEFAULT for anything played on the concert screen behind the musicians. RIFE 4.26 x5 at source size (24 -> 120 fps), keep every 2nd frame (60 fps, because screens and media servers run at 60 Hz and 48 fps on 60 Hz stutters), then RTX VSR to 1920x1080, mp4 with the clip's audio.
RIFE in ComfyUI computes each in-between frame directly from the two real frames (t = 0.2/0.4/0.6/0.8), not recursively, so x5 doesn't stack errors. At 24 -> 60, 4 of every 5 shown frames are in-betweens; that's the 2.5 ratio, the same for any method.
interp.multiplier 5 + sel.select_every_nth 2 + save.frame_rate 60 belong together.

## Upscaler: NVIDIA RTX Video Super Resolution (not SeedVR2)
DaSiWa "RTX Upscaler & Refiner" node (nvvfx) on the 4090's tensor cores, to exactly 1920x1080 (Center Crop trims about 0.4% per side of the slightly-wider-than-16:9 1376x768 source). Clean and temporally stable; it doesn't invent detail.
SeedVR2 was dropped 2026-10-25 (Justice: "35 minutes for 10 seconds is a waste"). Measured on the same 10 s Sentimientos clip at 60 fps: SeedVR2 7B about 29 min (RAM-bound decode, cancelled) vs RTX VSR 29 SECONDS. The old graphs are kept as *.seedvr2.api.json.retired in comfort_api; never use them unless Justice asks.

## Settings
- load.video - full Windows path of the source mp4.
- rtx.width / rtx.height - 1920x1080 (3840x2160 for a 4K screen). rtx.upscale_quality - Ultra (default) / High / Medium / Low.
- rtx.denoise / rtx.deblur - optional extra NVIDIA passes, off by default.
- To cancel any running job: the "Cancel job" button in the Comfort app, or create an empty file inbox\_CANCEL.

## Job
{"workflow": "Stage 1080p60 (Comfort)", "name": "<clip>_stage60", "set": {"load.video": "A:\\Ai projects\\Comfort\\out\\videos\\<clip>.mp4"}, "free_after": true}
10 s clip: 29 s on the 4090 (2026-10-25).
