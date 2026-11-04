READ CLAUDE.md FIRST - it is the current manual (job formats, workflows, story-film pipeline and transition rules in section 14, token rules in section 15). The notes below are older.

OUTPUT LAYOUT (2026-10-20): all videos go to out\videos\<job name>.mp4; their json/info go to out\video_info\<job name>\. Image jobs stay in out\<job name>\. Don't join clips unless Justice asks.

VIDEO DEFAULT (Justice, 2026-10-20): always make videos with the multi-image workflow "H3 Keyframe Chain (Comfort)" (the Seed Hunter Reference-to-Video path: pictures pinned as first/last frame) and write each clip prompt as the transition from one picture to the next. Do NOT default to the DaSiWa workflow (make_video / "MiniMax H3 Director (Comfort)") - only when Justice asks for DaSiWa by name.

COMFORT - batch prompts into ClaudeComfy (Krea 2)
==================================================
Double-click "Start Comfort.bat" and leave the window open. It watches inbox\ and
starts ClaudeComfy (port 8189) by itself if it isn't running.

Drop a job file into inbox\ (.txt or .json). Results go to out\<job name>\:
  NN-K_<words>.png   the images (NN = prompt number, K = variant)
  _sheet.jpg         contact sheet of the whole batch
  _done.txt          one-line summary + file list (sizes, seeds)
  _manifest.json     full prompts, seeds, settings (re-run any image exactly)
status.txt = what Comfort is doing now. comfort.log = history.
Finished job files move to jobs\done\ (or jobs\failed\ with an .error.txt).

JOB FILE (.txt) - one prompt per line; # lines set options for the lines below them
  #name pillars_v1          output folder name (default = file name)
  #preset prop_tall         size + default style (see presets.json, or: comfort.py presets)
  #style be_iso             style suffix(es) from styles.json, comma-separated; "none" = off
  #n 2                      images per prompt (each gets its own seed)
  #seed 1234                fixed base seed (variant K uses seed+K-1); "random" = default
  #size 1344x768            exact generation size (overrides preset aspect/mp)
  #aspect 21:9  #mp 1.5     generation size by aspect + megapixels (multiples of 16)
  #final 3840x1600          exact output size (upscale model + lanczos fit); "none" = off
  #upscale 4x-UltraSharpV2.safetensors   upscale model used for #final
  #lora Krea2\KNPV3_1.safetensors:0.8     extra LoRA(s) for krea, ; separated
  #wf edit  #image out\pillars_v1\01-1_cracked-ancient-pillar.png   Identity Edit
  #boost 4                  edit fidelity (ref_boost)
  #pass2 off                skip the 0.2 refine pass (krea)
  // comment
  [n=4 seed=7 preset=prop label=pillar_a] per-line options in brackets before a prompt

JSON job: {"name":"x","preset":"prop","n":2,"prompts":["...", {"prompt":"...","seed":5}]}

Workflows (settings in config.json):
  krea = "Krea 2 RedCraft (ClaudeComfy)": RedCraft Krea2 fp8 + Krea2T-Enhancer 1.5,
         pass 1 linear/euler simple 8 steps cfg 1, pass 2 res_2s bong_tangent denoise 0.2 eta 0.9
  edit = "Krea 2 Identity Edit (ClaudeComfy)": Krea2 turbo + identity_edit v1.2 LoRA,
         ref_boost 4, euler simple 10 steps cfg 1, source aspect at 1 MP


SONG ART FOR MUSIC VIDEOS - what Justice taught (2026-10-23)
Folders: songs\<Artist - Song>\  ->  lyrics.txt, brief.md (analysis, concept, prompts, lyric behind each picture), images\v1..v4\

0. FIND THE STYLE FIRST: A STYLE ROUND (Justice, 2026-10-27)
- To find a song's art style, the 5 pictures are 5 DIFFERENT art styles - never 5 pictures in one style. Five
  pictures in one style is not a choice of style, it is redundant.
- NEVER THE SAME SCENE IN EVERY PICTURE (Justice, 2026-10-28: Talawa v1 drew one scene 15 times - "never do that again").
  Every picture takes its inspiration from a DIFFERENT part of the lyrics (intro, each verse, chorus, outro), so he gets
  a real range of options: different subjects and moments AND a different style in each. Write the lyric line and its
  time behind every picture in brief.md. Each is a best attempt: its own tuned style sentence, the palette and light that
  suit that style and that moment, its LoRA + trigger. He may ask for more than 5 (Talawa: 15).
- Take the 5 from different families (anime film, oil/impasto, watercolour/gouache, print, ink, textile/craft,
  graphic poster), grounded in the ilkerzgi download ranking and matched to the song. Never photoreal, never tattoo flash.
  One .txt job per song: [label=<style> lora=<style>-comfy.safetensors:1.1] per line (example: jobs\done\*_styles_v2.txt).
- Only after he picks a style: the 5-picture storyboard (keyframes) in that one style, then the video clips.
- PREVIEW: copy every song picture set to A:\Ai projects\Star Trek\Preview\<Artist - Song>\ as "<version> <style> <n>.png"
  (device_bash cp: zero image tokens) and tell him it is there. Pictures go to Preview, not into the chat
  (an image Claude reads costs about 1,500 tokens and is re-sent with every later call); look at _sheet.jpg once per set
  only to catch problems.

1. EACH SONG IS ITS OWN PROJECT
- Analyse only that song's lyrics, give it its own art style, and never blend songs into one analysis or prompt.
- 5 pictures per song at 1376x768 (= H3 video size). Justice picks which ones go to video.

2. ART IS AN EXTENDED METAPHOR
- Make the viewer FEEL the song's specific details without literally showing the subject. His example: a dying butterfly can stand for the death of a child, the loss of innocence, without showing a body. Learn the principle; don't reuse butterflies.
- Don't act the lyrics out. v1 showed the singer at a border fence, holding fire, crossing a river: "terrible".
- Don't put Rasta men or the artist in every frame. A figure only appears where it serves the image, as a silhouette or fragment (a sneaker, raised hands).
- Keep the song's own identity and world. The metaphor has to come from the song's culture and scene, not an unrelated nature documentary. v2 used sea turtle hatchlings for a border song and bees for a weed song: rejected. Real Herbalist is a marijuana song, so show smoke, the leaf, the chalice, jars and haze.
- It is for a music video and stage projection, so every frame must be cool and aesthetic, like an album cover or a still from a great music video.
- Metaphor objects that worked: empty clothes billowing on a line (ghost town), a marimba played by the wind, a bell rope swinging alone, lit windows in an empty street, smoke forming mountains, smoke turning into a galaxy, glowing jars as lanterns, a sneaker stepping over a border line, fence shadows on a sound system, a map tearing off a wall, colour rings radiating from a small figure, cupped hands holding a small sun.

3. ART STYLE: NO PHOTOREALISM, AND NOTHING FROM THIN AIR
- Ultra-realistic or photographic looks were rejected (v1-v3).
- Ground the style in data, then match it to the song's mood:
  a) Rankings of the 1,500+ Krea 2 style LoRAs (ilkerzgi) by downloads and likes:
     https://huggingface.co/api/models?author=ilkerzgi&sort=downloads&direction=-1&limit=60   (also sort=likes)
  b) Community surveys, e.g. Creative Boom's top illustrators of 2026 (voted by 1,000+ creatives): flat gouache, graphic print, detailed ink.
- v4 results:
  WORKED ("much better"): luminous-anime-film (Real Herbalist, #1 by downloads), orange-blue-riso-etching (Cruzando Fronteras), aged-tempera-fable (Ciudad Fantasma), airy-gouache-minimalist (Sentimientos).
  FAILED ("terrible"): bold-flash-tattoo (Dem Cyaan). Don't use tattoo flash. Its designs also sat small in empty cream paper, which is wrong for a 16:9 video frame.

4. KREA 2 PROMPTING THAT WORKED
- Style LoRA: use a Comfort download job to put <name>-comfy.safetensors in ComfyUI\models\loras (URL https://huggingface.co/ilkerzgi/<repo>/resolve/main/<name>-comfy.safetensors), then put  #lora <name>-comfy.safetensors:1.1  in the job and the trigger phrase (e.g. "luminous anime film style") at the END of every prompt.
- One fixed style sentence, reused word for word in all 5 prompts of a song, placed right after the subject.
- Order: subject + action -> style sentence -> composition (camera, framing, where things sit, what stays empty) -> lighting -> concrete colours -> "no people, no text, no watermark".
- Write a lyric anchor for every picture (the line it comes from) in brief.md.
- Negative prompts do nothing. Say what you want. "No people" helps, but Krea still adds hands sometimes.
- NUDITY RISK: Krea painted nude figures twice ("bodies painted as thin washes of color", "a mural of musicians and dancers"). Always state the clothing for any figure, even painted ones ("fully clothed musicians in long skirts and white shirts"). That fixed it.
- Shapes formed by other things (hills forming a woman's face in profile) usually don't come out. Use direct objects.
- Job setup: one .txt job per song, #size 1376x768, #n 1, #seed random, #style none, [label=x] per line. Queue all songs (and any downloads as 0_*.json) in one call. About 55 s per 5-picture job on the 4090.

5. PROCESS
- When the direction changes, send Justice a short concept list per song before rendering.
- Finish the whole set, then let him judge. No re-rolls midway.
- Check _sheet.jpg. Open a full image only when you suspect a problem (nudity, hands). Report problems plainly: which picture, what went wrong, and the fix.
- When asked "why this style", answer with sources and data, never taste alone.

6. WHAT JUSTICE PICKED (after v4) AND WHY IT WORKS
Picks are in songs\<song>\picks\ (prefix = version). Liked: Ciudad v4 ropa/campana/mural/ventanas and v1 watercolor mapa/viento/firma; Fronteras v4 linea/reja/manos; Herbalist v4 frascos/aros and v3 aros; Sentimientos all of v4 (gouache), v2 pastel gota/tormenta/raices/danza, v1 adentro. Dem Cyaan: nothing (Baroque v1, volcano v2 and tattoo v4 all failed).
What the picks share:
- LIGHT IS THE SUBJECT: glowing windows, jars glowing like lanterns, rings of light in dark water, a light burst behind the crowd, a little sun in cupped hands, roots lit from inside.
- ABSENCE / IMPLIED PRESENCE: empty clothes on the line, a bell ringing alone, lit windows in an empty street, a sneaker or raised hands instead of a person, faceless crowned men instead of a named politician.
- RINGS, RIPPLES, RIBBONS radiating outward (drop, dance on the lake, figure on the hill, smoke rings, ribbons of voices). This is sound and vibration made visible, and it animates well.
- ONE CLEAR IDEA PER FRAME with calm negative space and a strong focal point (a vanishing point down the street, a centred ring, a tiny figure in a vast field).
- A HAND-MADE SURFACE: tempera cracks, watercolour bleed, riso grain and misregistration, pastel strokes, gouache paper, painted anime light. Never a photo look.
- A TIGHT PALETTE per song: two riso inks, muted tempera, blue-green on black, soft pastel gouache.
- Figures: tiny in vast space, a lone figure in one strong colour (a woman in a red dress in the wind), or satirical allegory. Never the artist acting the lyrics.
- BUILT-IN MOTION for the video stage: wind in cloth and hair, ripples, smoke, a swinging rope.
What failed: photoreal; nature-documentary swaps; tattoo-flash icons alone on empty paper (cliche symbols, no space or atmosphere); generic fantasy volcano; storybook ceiba; the literal singer.
v5 (2026-10-23): 5 new pictures per song built on these traits, keeping each song's winning style. Dem Cyaan moved to amber-ink-mist (#18 by downloads), with light in darkness and rings.


VIDEO FINISHING (2026-10-23): workflow "Upscale and Interpolate (Comfort)" = SeedVR2 7B upscale to 1080p, then RIFE 4.26 x2 to 48 fps, audio kept. Job: {"workflow": "Upscale and Interpolate (Comfort)", "name": "<clip>_hd", "set": {"load.video": "A:\\...\\<clip>.mp4"}, "free_after": true}. Details: guides\Upscale and Interpolate (Comfort).md

STAGE SCREEN (2026-10-25): clips for the concert screen use "Stage 1080p60 (Comfort)" (true 60 fps for 60 Hz screens, 1080p). Job: {"workflow": "Stage 1080p60 (Comfort)", "name": "<clip>_stage60", "set": {"load.video": "A:\\...\\<clip>.mp4"}, "free_after": true}

UPSCALER CHANGE (2026-10-25): SeedVR2 is retired (about 29 min per 10 s clip). Both video finishing workflows now use NVIDIA RTX Video Super Resolution (DaSiWa RTX Upscaler & Refiner) to 1920x1080: 29 s for a 10 s clip at 60 fps. Concert screen = "Stage 1080p60 (Comfort)". Cancel a running job: Cancel job button in the app, or an empty file inbox\_CANCEL.

ALL FUTURE VIDEOS (2026-10-25): every video job automatically queues <clip>_stage60 = 1920x1080 60 fps with audio (Stage 1080p60). That is the version for the concert screen. Skip for one job with "stage": false.

TRANSITIONS AND SPEED IN THE FILMCRAFT EDITS - what Justice taught (2026-10-25)
Justice: "you are pretty lazy with transitions, it seems you only like to do a flash transition." The first edits were all dissolve 30 plus a lone flash/glitch/leak. Don't do that again.

1. SPEED RAMPS - automatic, inside FilmCraft (2026-10-27: they were OFF in fc.py unless a cut list said `ramp on` - fixed: now ON for every build and each clip keeps its cut length, so SongMap cuts stay on the beat. Star Trek\README.txt rule 1) (never re-time clips in Comfort: Justice wants FilmCraft to own speed)
- Problem he saw: "a slow down and then rapid acceleration" at joins. Cause: H3 keyframe clips ease into their pinned last frame and ease out of their first one. Measured 2026-10-25: the last 20-30 % of most clips is nearly still.
- Every fc.py build now measures each clip (A:\artcraft\FilmCraft\ramp.py: ffmpeg at 128x72 on his PC, cached in projects\<song>\_motion\, zero tokens) and speeds the stalls up (up to 3x, fastest rush eased to 0.85x) with gradual slopes like Premiere speed-ramp handles. It is built as short constant-speed pieces with frame blending, editable in FilmCraft (Speed/Duration). FilmCraft 0.10 stores Time Remapping keyframes but does not render them (tested), so don't use those.
- Clips come out about 15-25 % shorter (the dead time is gone). Plan more clips per song to fill the length.
- To check a ramp, read projects\<song>\<song>.ramps.txt: one line per clip, motion as rendered -> after (. still, - = + * # moving). Don't watch the video for this.
- Justice can still name a spot: a line `speed 7.5-9.4 160` under the clip line (clip seconds, percent). `noramp` at the end of a clip line keeps that clip as rendered; `ramp off` or `ramp 0.6` (strength) for the whole edit.

2. CHOOSING A TRANSITION
- CHAINED clips (B starts on A's last frame) are one continuous camera move, so any blend there is invisible: use dissolve 12-16. At most one or two chained joins per song get an ACCENT that means something on that beat: light_sweep when light arrives, cross_zoom 20-24 (strength 30-40) when the camera goes through an opening, glow when fire flares. Never a flash on a chained join.
- NEW-SCENE joins carry the edit. Choose from what the two shots share (match-cut practice; Insta360 and Vidpros transition guides; CapCut 2026 trends):
  a) MOTION CONTINUES (match on movement): whip 12-18, push 20-30, directional_blur_transition, travel_motion. direction = the side the camera is moving toward (camera rises -> direction=north, glides left -> west). Push-in into push-in = zoom-through: cross_zoom 18-30 (center=x,y in pixels = the point you push toward) or zoom_blur.
  b) SHAPE OR LIGHT MATCHES (graphic match): a lit window becomes a falling glowing drop, stars become a dew glint, a speaker cone becomes the next circle. Let the light carry it: luma_fade (dark/ink parts go first; `invert` = bright parts first), additive_dissolve, flare, ray, glow, light_leak in the song's colour (color=#rrggbb).
  c) MATERIAL OF THE WORLD: water -> wave, liquid_distortion. Mist or smoke -> blur_dissolve (blur 60-100). Ink -> luma_fade. Old paint or paper -> film_dissolve, grunge (edge_color in the palette), burn_alpha. Print -> chroma_leak (ink misregistration), stripe. Riot or digital energy -> glitch, vhs_damage, earthquake.
  d) ENERGY OF THE MUSIC: loud transitions (flash 4-8 frames, glitch 8-14, earthquake 10-15, chroma_leak) only on a hard hit or drop, at most one per ~30 s. Soft passages get luma fades, soft wipes and dissolves of 30-48 frames.
  e) TIME PASSING or a new chapter: dip_to_black 30-60, or dip_to_color in the song's palette.
- LENGTHS at 60 fps: whips, glitches and swipes 0.2-0.5 s (12-30 frames); match, mask and luma transitions 0.5-1 s (30-60). Reggae one-drop is about 70-80 BPM, so one beat = 45-51 frames and half a beat = about 24: fit lengths to a beat or half beat.
- VARIETY: never the same visible transition twice in a row (the invisible chained dissolves don't count). One family per song does most of the work (palette below) plus one surprise.
- DATED (1980s-90s wipes, avoid unless it's a deliberate joke): star_wipe, iris_*, heart and star shapes, cube_spin, page_turn, spin_3d, checker_wipe, venetian_blinds, flip_over.
- Concert edits start with fadein 18-30 and end with fadeout 40-60.

3. PALETTE PER SONG (start here)
- Ciudad Fantasma (aged tempera fable): luma_fade, film_dissolve, grunge (edge_color=#3a2414), blur_dissolve for ghostliness, light_sweep for warm dawn. No digital glitch.
- Cruzando Fronteras (orange-blue riso etching): chroma_leak and glitch (riso misregistration), stripe in riso orange, whip or push in the crossing direction, cross_zoom on the bass, linear_wipe as a line being crossed.
- Real Herbalist (luminous anime film): light_sweep, flare, glow, warm light_leak, wave or liquid_distortion for smoke, cross_zoom for dreamy push-ins.
- Dem Cyaan (amber ink mist): luma_fade (ink spreading), blur_dissolve (mist), glow or burn_chroma for fire, dip_to_color amber.
- Sentimientos (airy gouache minimalist): additive_dissolve, soft_wipe (a brush wash, feather 400+), shape_dissolve circles from the centre (rings), wave, long dissolves.
- Lily Pad (painterly pond into space): wave, liquid_distortion, ray (light shafts), cross_zoom into space, glow for stars.

4. HOW TO WRITE IT
- Before choosing, read how A ends and how B starts: the summary line of each clip's prompt in out\video_info\<clip>\_manifest.json (camera move, what fills the frame).
- In the clip's Comfort job: "fc_in": "luma_fade 40 invert" (it lands in the cut list). Or edit projects\<song>\<song>.txt and queue fc_<song>.json.
- Params go after the frames: `> whip 15 direction=east blur=90`, `> light_leak 30 color=#ffb070 amount=60`, `> cross_zoom 24 center=960,540 strength=35`, `> shape_dissolve 48 shape=circle order=center_out`. All 112 FilmCraft transitions with their params and defaults are listed in A:\artcraft\FilmCraft\transitions.txt.
