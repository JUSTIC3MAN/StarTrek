# H3 Keyframe Chain (Comfort)
One continuous H3 clip WITH audio that starts exactly on one picture and ends exactly on another. Same model chain as "H3 Reference Video (Comfort)" (DaSiWa Hybrid v3 int8, DMAD 4-step turbo LoRA 1.0, er_sde/beta 8 steps, SLA sparse attention). Built 2026-10-20 for chaining: clip N ends on picture N+1 and clip N+1 starts on it, so the clips join without a jump.

## Settings
- pic1.image - first frame (<Picture 1>), pinned at frame 0 (key1.frame_idx)
- pic2.image - last frame (<Picture 2>), pinned at the last frame (key2.frame_idx = -1)
- ref.prompt - REF2VA prompt, one continuous [Shot 1] with no cuts (below)
- ref.length - frames on the 17k+5 grid: 158 = 6.6 s, 175 = 7.3 s, 192 = 8 s, 209 = 8.7 s, 226 = 9.4 s, 243 = 10.1 s, 260 = 10.8 s, 277 = 11.5 s, 294 = 12.25 s, 311 = 13 s, 362 = 15 s
- ref.width / ref.height - 1376x768. Render the pictures at exactly this size.
- Output: mp4 h264 crf 16 with audio.

## Planning the pictures (Justice's rules, 2026-10-20)
- Every clip is longer than 6 s, and the lengths vary.
- Plan the pictures as a chain: write all of them up front, each one from the previous picture, and render them in ONE batch job (one-at-a-time leaves the GPU idle and is too slow for Justice), keeping the subject's position, facing and direction of travel, the camera side (no crossing the 180-degree line) and the landmarks, so that one continuous camera move in the clip's time can get from one to the next.
- Make in-between pictures for actions (e.g. a separate picture of her stepping into the window) instead of asking one clip to jump between unrelated compositions.

## Prompt (official REF2VA format)
subject_definitions: <Subject N> lines for the character and style, citing the pictures; "<Picture 1> is the first frame of [Shot 1], showing ..."; "<Picture 2> is the last frame of [Shot 1], showing ..."
summary: [keyframe completion + reference generation] ...
retention_analysis: one line per subject and per picture ("<Picture 2> ([Shot 1] last frame): fully_preserved - ...")
detailed_description: style sentence, then [Shot 1] The shot begins from <Picture 1> ... one continuous camera move ... the camera is still moving as the shot ends on <Picture 2>. No cut or transition occurs.
overall_soundscape / non_diegetic_music (N/A when the clips will be joined - each generation would start its own score)

## Joining
Join in order with a 0.5 s video dissolve plus a 0.5 s audio crossfade at each boundary (both sides of the join are the same pinned picture, so the dissolve doesn't show).
- 2026-10-20 lantern film (4 chained clips 8/10/7.3/12.25 s, 153/206/133/266 s render): joins with 0.5 s dissolve were invisible. Clips whose move is a forward glide or a tilt (k1->k2, k2->k3) stayed continuous. Clips that needed the camera to orbit to a very different angle around her (k3->k4 quarter arc, k4->k5 side to directly behind) got a hard cut mid-clip instead (3.08 s, 6.08 s). For orbits and big angle changes, add an in-between keyframe partway round so each clip only has to move a short way.
