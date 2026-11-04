# H3 Reference Video (Comfort)
REF2VA video WITH audio from up to 3 pictures, each pinned as the first frame of its shot. A clean single-pass rebuild of the stage-1 path of Justice's "MiniMax H3 Seed Hunter (ClaudeComfy)" (foxydits v2.5), which can't run outside ComfyUI's window: its sampler, sigmas and VAE are wired by an Anything Everywhere node, so its API export loses them and the pictures would only reach the text encoder. This copy wires them directly. Built 2026-10-20.

Same model chain as Seed Hunter: DaSiWa Hybrid v3 int8 + qwen3vl_32b nvfp4 encoder + int8 video VAE + fp32 audio VAE, comfy kitchen attention, Kijai DMAD 4-step turbo LoRA at 1.0, SLA block-sparse attention (keep 10%, from 0.2), er_sde / beta. No upscale pass, no preview picking: one finished video per run.

## Settings
- pic1.image / pic2.image / pic3.image - the pictures (run_workflow images={"pic1.image": "A:\\...png"}). They become <Picture 1>-<Picture 3> in the prompt. All three are required. Render them at the video size (1376x768) so nothing is cropped.
- ref.prompt - the REF2VA prompt (structure below). Max ~7000 characters.
- ref.width / ref.height - 1376x768 default (multiples of 32). ref.length - frames at 24 fps on the 17k+5 grid: 124 = 5 s, 243 = 10 s, 362 = 15 s (trained maximum).
- key1/key2/key3.frame_idx - the frame each picture is pinned at: 0 / 120 / 240 = shot starts at 0 s / 5 s / 10 s. Must match the [Shot N] cut times in the prompt (seconds x 24). -1 pins the last frame.
- sched.steps - 8 (Seed Hunter's note: single pass best at 1-2 MP, 6-10 steps with the turbo LoRA). lora.strength_model - 1.0.
- ref.ref_image_size - "max" (his setting; for 1376x768 pictures "match" is identical).
- Output: mp4 (h264, crf 16) with audio.

## Prompt (official MiniMax full-reference format, from DaSiWa-Nodes data/h3_forge.json)
subject_definitions:
<Subject 1> is the rendering style of <Picture 1>, <Picture 2> and <Picture 3>: ... (style or recurring things become <Subject N> lines citing their pictures)
<Picture 1> is the first frame of [Shot 1], showing ...
<Picture 2> is the first frame of [Shot 2], showing ...

summary:
[keyframe completion + reference generation] one or two sentences: duration, aspect, which subjects appear, the shot progression.

retention_analysis:
<Subject 1> (applies to every shot): fully_preserved - ...
<Picture 1> ([Shot 1] first frame): fully_preserved - the opening composition, lighting and positions.

detailed_description:
One sentence of overall visual style, then [Shot 1] The shot begins from <Picture 1>, ... / [Shot 2] At 00:05.000, the camera cuts to <Picture 2>, ... 350-500 words in total. One camera idea per shot (motion + amplitude + speed); say what changes during the shot, not a still frame.

overall_soundscape:
diegetic sound only, 1-4 sentences.

non_diegetic_music:
instruments, tempo, rhythm, dynamics - or N/A.

## Notes from runs
- 2026-10-20 cosmic_journey_ref_v1 (15 s, 3 pictures, 8 steps): 389 s on the 4090. Cut 1 landed exactly at 5.000 s; cut 2 came early at 9.04 s although the prompt said 00:10.000 and Picture 3 was pinned at frame 240. The pins fix each shot's composition, but the model still picks the exact cut frame.
- 2026-10-20 window_story_vid_v1 (15 s, 3 pictures, same character in all three): 388 s. Both cuts landed exactly at 5.000 s and 10.000 s. Character identity held across shots when all three pictures described her with the same wording.
- 2026-10-20 window_story_vid_v2 (flow version: key2 at frame 132 mid-shot, key3 at 228, dove wipe): the through-the-glass push-in worked as one continuous move, but pinning Picture 2 mid-shot at a different camera angle (side view after a from-behind move) forced a hard jump at 5.1 s instead of the camera arcing around. To let a move flow, keep a picture as a reference only (no keyN pin) when its angle differs from where the move is heading. The dove crossing the lens carried across the 8.5 s cut as a match-on-action, which reads smoother than a plain cut.
