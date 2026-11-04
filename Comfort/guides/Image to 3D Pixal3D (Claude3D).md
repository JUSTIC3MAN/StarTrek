# Image to 3D Pixal3D (Claude3D)
Turns one character or object image into a textured 3D model (.glb) with Pixal3D (or TRELLIS.2), native ComfyUI nodes. Takes a few minutes; uses most of the 4090's VRAM.

## Settings
- 122.image - the input picture (run_workflow images={"122.image": "file.png"}). Best input: one subject, full body, facing front, plain background.
- 316.value - false = Pixal3D (default, sticks closest to the picture), true = TRELLIS.2
- 248.switch - true = remove the background first (default); false only for clean cutouts
- 186.target_face_count - mesh size, default 120000 (game-friendly); 700000 = maximum detail
- 288.value - texture size, default 4096
- Seeds are randomised per run.

## Outputs
A .glb (model with baked color, normal and AO maps) plus renders: view_front, view_three_quarter, view_side, view_back, view_clay (untextured), and input (the cut-out the model saw).

## Prep
If the picture has props, scenery or several characters, first run "Krea 2 Identity Edit (ClaudeComfy)" to redraw the subject alone, full body, facing front, arms slightly away from the body, on white. See A:\Ai projects\Claude3D\CLAUDE.md.
