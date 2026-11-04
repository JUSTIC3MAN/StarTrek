# Krea 2 Identity Edit (ClaudeComfy)
Edits an existing image with a plain-English instruction while keeping the person/object identical (Krea 2 Turbo + identity-edit LoRA v1.2). ONLY use when Justice asks for an edit.

## Settings
- 72.image - the image being edited (run_workflow images={"72.image": "file.png"})
- 84.prompt - the edit instruction
- 79.ref_boost - fidelity dial: 4 = strong likeness (default), 1 = classic, above 10 over-copies (removals start failing), below 1 = more freedom
- 83.aspect_ratio - "1:1 (Square)", "2:3 (Portrait Photo)", "3:2 (Photo)", "3:4 (Portrait Standard)", "4:3 (Standard)", "9:16 (Portrait Widescreen)", "16:9 (Widescreen)", "21:9 (Ultrawide)"
- 83.megapixels - 1 is the sweet spot; higher only for single-subject edits
- 53.steps - 10 balanced; 8 = follows the instruction harder; 12 = more face detail. 53.seed random.

## Prompting
Write the edit as an instruction about the SAME subject: "Show this same young man standing upright in a full-body front view... Keep his face, warm brown skin, short twisted dreadlocks and outfit exactly the same." "Relight the scene with warm golden-hour sunlight." "Change her outfit to a red raincoat."
If a distinctive face comes out generic, append: "Preserve the exact facial identity - distinguishing features: ..." and list them.
