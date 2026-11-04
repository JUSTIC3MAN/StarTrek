# Prompting Krea 2 (Justice's RedCraft finetune and stock Krea 2 Turbo)

Krea 2 reads the prompt with a Qwen3-VL language model, so it understands full sentences, relationships and positions. Write like a precise art director, not a tag list.

## Structure (one paragraph, about 40-120 words)
1. Subject and action: what it is and what it is doing ("A gnarled dead tree stump with a moaning knothole face...").
2. Style and medium, early: "hand-painted 2D game environment art", "35mm film photo", "risograph print, limited palette", "cel-shaded anime". Krea's own guidance: put style language early and keep the subject clear.
3. Composition and camera: framing (close-up, full body, wide establishing), angle (eye level, low angle, high three-quarter, top-down), lens feel, where things sit in the frame, what is left empty.
4. Environment and background.
5. Lighting: direction, softness, time of day ("light from the upper left, warm late-afternoon key, cool shadows").
6. Color and mood with concrete colors ("inky black, toxic lime green, bone white"), not vague words.

## Rules that matter on this setup
- Negative prompts do nothing (cfg 1, the negative is zeroed). To avoid something, describe the alternative or add a short "no text, no watermark".
- Text in the image: put the exact words in double quotes and say where they appear.
- Isolated objects for games: "isolated single object centred on a plain flat solid pure white background with no texture", "whole object in frame with margin".
- Sizes: multiples of 16, 1-2 megapixels. 1024x1024, 1376x768 (16:9), 768x1376 (9:16), 1536x864, 1152x1728 (2:3), 1728x1152 (3:2). Bigger only by upscaling an approved image.
- Same seed + same prompt = same image. When refining, change one thing at a time.
- RedCraft runs 8 steps + a 0.2 refine pass; ~5-20 s per image on the 4090.

## Example
A cracked ancient stone pillar standing on a square plinth, hand-painted 2D game environment art with soft painterly gradients, seen from an isometric three-quarter camera about 30 degrees above, moss cap on the broken top and creeping vines around the base, light from the upper left with lit top and left faces and darker right faces, muted grey-green palette, isolated on a plain flat solid pure white background, whole object in frame with margin, no text.
