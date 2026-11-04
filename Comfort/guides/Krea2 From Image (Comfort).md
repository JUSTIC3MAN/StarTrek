# Krea2 From Image (Comfort)
Reads a reference image with the local Qwen3-VL image-to-prompt (Justice's Krea workflow's "Image to prompt" group) and renders a new image from that prompt in one pass. The generate_from_image tool does the same.

## Settings
- img.image - the reference image (run_workflow images={"img.image": "file.png"})
- gen.prompt - the instruction to the describer. Keep the default instruction and add a change after it: "\n\nCreative direction: recompose as a wide 16:9 landscape, keep the style". Thinking mode must stay ON (gen.thinking=true) - with it off, this encoder returns empty text.
- lat.width / lat.height - output size (multiples of 16, 1-2 MP)
- The written prompt is saved in the job's _texts.txt - show it to Justice so he can reuse it.
