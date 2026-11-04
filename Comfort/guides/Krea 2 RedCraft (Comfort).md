# Krea 2 RedCraft (Comfort)
Text-to-image with Justice's Krea 2 RedCraft setup - the main still-image workflow. The generate tool runs exactly this.

Same model and settings as his "Krea 2 RedCraft (ClaudeComfy)" workflow: redcraftHybridH3Krea2t fp8, Qwen3-VL-4B heretic encoder, Krea2T-Enhancer 1.5, pass 1 linear/euler + simple 8 steps cfg 1, pass 2 res_2s + bong_tangent at 0.2 denoise. (His original graph can't be auto-converted - one of its add-on nodes crashes ComfyUI's converter - so Comfort rebuilds the generation path. Not included: Civitai metadata saver, SeedVR2 upscaler, grain/sharpen and prompt-enhancer groups, which were off in his saved version.)

## Settings
- pos.text - the prompt (see prompt_guide krea2)
- lat.width / lat.height - size, multiples of 16, 1-2 MP (1376x768 default)
- s1.seed / s2.seed - set automatically (random) unless you pass seed
- s1.steps - 8 (more is not better on this turbo model)
- enh.strength - Krea2T enhancer strength 0-2 (1.5); lower = more literal, higher = punchier detail
- s2 (refine pass) denoise 0.2 - raise to 0.3 for more texture, 0 disables the effect

## Prompting
Natural-language paragraph: subject, style early, composition/camera, environment, lighting, palette. No negative prompt. Text in quotes.
