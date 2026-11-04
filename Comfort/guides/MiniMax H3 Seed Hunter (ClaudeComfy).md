# MiniMax H3 Seed Hunter (ClaudeComfy)
REF2VA (reference-to-video with audio) by foxydits: renders three quick low-res previews with different seeds, then upscales the one Justice picks. ONLY works inside ComfyUI's own window: its sampler/VAE wiring is created by ComfyUI's interface, so Comfort cannot run it (tested: the converted copy is missing those connections). For videos from Comfort use make_video.

## What can be set from Comfort
- 365.prompt - REF2VA prompt (H3 Prompt IDE), structure below
- 22:23.value - video length in seconds (3 default)
- 22:9.aspect_ratio - e.g. "9:16 (Portrait Widescreen)", "16:9 (Widescreen)"; 22:9.megapixels - 0.4 preview size (0.98 ~ 1344x768)
- 16.seed - first-pass seed; 22:8.value - total steps (6); 22:6.sampler_name (er_sde)
- Reference images/videos/audio are loaded in the Fantastic H3 Media Loader in ComfyUI's UI, and the Enable Preview / Enable Upscale switches are UI toggles - those can't be changed from Comfort.

## REF2VA prompt structure
subject_definitions: <Subject 1> is ... (who/what appears; use <Picture N> for frame anchors, <Video N> for pacing, <Audio N> for sound references)
summary: one line of what happens
retention_analysis: what must stay identical from the references (or N/A)
detailed_description: [Shot 1] ... [Shot 2] At 00:02.000 ...
overall_soundscape: ...
non_diegetic_music: ...
