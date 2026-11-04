# MiniMax H3 Director (Comfort)
Video WITH audio from Justice's DaSiWa MiniMax H3 Director workflow (saved by him as "Working"). Use the make_video tool - it fills the Director correctly (mode, prompt, size, duration, start/end images).

- Modes: T2VA (text only), I2VA (start from an image), FL2VA (first + last frame), L2VA (end on an image).
- Model: DaSiWa Hybrid v3 int8 (non-turbo): res_multistep / simple / 25 steps, shift video 11, audio 4. Several minutes per clip.
- Size: multiples of 32 (H3 requirement); 1376x768 (16:9) default, 768x1376 vertical. Duration 2-15 s per take (5 s default).
- The prompt MUST use the H3 structure (prompt_guide topic "h3"): alignment line for image modes, integrated_multimodal_description with [Shot N] timing, overall_soundscape, non_diegetic_music.
- Output: an mp4 with sound in the job folder.

## Settings if you use run_workflow instead (node 2831 = Director)
2831.mode, 2831.prompt (+ raw external_prompt_overwrite), 2831.width, 2831.height, 2831.duration, 2831.frame_rate (24), 2831.timeline_data (reference images - let make_video build it). Sampling: 2827:2590.steps (25), 2827:2598.sampler_name (res_multistep), 2827:2692.shift_video (11) / shift_audio (4). LoRAs: 2826.stack_data.

- Measured on Justice's 4090: 10 s I2VA at 1376x768, 25 steps = about 12.5 minutes. Tell him the expected wait before starting long clips.
