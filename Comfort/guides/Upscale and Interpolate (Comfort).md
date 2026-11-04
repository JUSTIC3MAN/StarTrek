# Upscale and Interpolate (Comfort)
RTX VSR to 1920x1080, then RIFE 4.26 x2 (24 -> 48 fps), mp4 with the clip's audio. For the concert screen use "Stage 1080p60 (Comfort)" instead (true 60 fps).
interp.multiplier and save.frame_rate change together (frame_rate = 24 x multiplier).

## Upscaler: NVIDIA RTX Video Super Resolution (not SeedVR2)
DaSiWa "RTX Upscaler & Refiner" node (nvvfx) on the 4090's tensor cores, to exactly 1920x1080 (Center Crop trims about 0.4% per side of the slightly-wider-than-16:9 1376x768 source). Clean and temporally stable; it doesn't invent detail.
SeedVR2 was dropped 2026-10-25 (Justice: "35 minutes for 10 seconds is a waste"). Measured on the same 10 s Sentimientos clip at 60 fps: SeedVR2 7B about 29 min (RAM-bound decode, cancelled) vs RTX VSR 29 SECONDS. The old graphs are kept as *.seedvr2.api.json.retired in comfort_api; never use them unless Justice asks.

## Settings
- load.video - full Windows path of the source mp4.
- rtx.width / rtx.height - 1920x1080 (3840x2160 for a 4K screen). rtx.upscale_quality - Ultra (default) / High / Medium / Low.
- rtx.denoise / rtx.deblur - optional extra NVIDIA passes, off by default.
- To cancel any running job: the "Cancel job" button in the Comfort app, or create an empty file inbox\_CANCEL.

## Job
{"workflow": "Upscale and Interpolate (Comfort)", "name": "<clip>_hd", "set": {"load.video": "A:\\Ai projects\\Comfort\\out\\videos\\<clip>.mp4"}, "free_after": true}
