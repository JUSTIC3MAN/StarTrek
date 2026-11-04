# FilmCraft: Claude video editing (low-token)

Edit videos only through `fc.py`. Never call filmcraft-cli directly, list its commands, or inspect sequences or .fcproj files: those outputs run to thousands of tokens. Never read video files.

## Where it runs
- Windows (Claude Code on this PC): `python fc.py ...` uses `filmcraft-cli.exe` in this folder.
- Cowork Linux shell: `cd ~/mnt/FilmCraft && python3 fc.py ...`. This uses `tools/linux-0.10.0`. Windows paths are mapped through `MOUNTS` in fc.py; add an entry when a new folder is connected.

## Loop
1. `fc.py scan "<folder>"` → clips.tsv plus one line per clip: `c01 6.0 720x1280 24 a 10-21 name.mp4` (id, seconds, size, fps, audio, date). Newest first.
2. Write `cuts/<name>.txt`.
3. `fc.py build cuts/<name>.txt` → one line: `ok renders/<name>.mp4 ... | project renders/<name>.fcproj`.
4. Optional: `fc.py peek renders/<name>.mp4` → small PNG strip around each cut. Look only when needed.
5. To change the edit, edit one or two lines of the cut list and rebuild.

## Cut list
```
out renders/name.mp4     # also writes name.fcproj (opens in FilmCraft) and name.cuts.json
size 1080x1920@30        # optional; default = first clip
fit fill                 # fill | fit | none, for clips of a different size
fadein 15                # frames from black (video + audio)
clip c03                 # or a full path; optional trim in seconds: clip c03 1.5-6
> leak 18                # transition into the next clip: name + frames
clip c01 noramp         # noramp = keep this clip's speed exactly as rendered
speed 2.0-3.5 160        # that part of the clip above (clip seconds) at 160 %, smooth slopes
fadeout 20
text "KWOTE" 2.3-5.1 style=boss pos=lower-left   # title over the clip above (its seconds; 2.3- = to its end)
subs lyrics.srt style=lyrics                      # .srt -> Subtitle caption track, burned into the mp4
music Song.mp3                                    # the song on A2 from 0:00 (at=12.5 to shift; path relative to the cut list); no clips yet = build only saves the .fcproj
ramp off                 # speed ramps run by default (lengths kept); ramp off | ramp 0.6 (strength) | ramp free
```
Reorder = move the clip lines. Transitions also crossfade the audio.
Transition params go after the frames: `> whip 15 direction=east blur=90`, `> light_leak 30 color=#ffb070 amount=60`, `> cross_zoom 24 center=960,540 strength=35`, `> luma_fade 40 invert`, `reverse`. direction = north/east/south/west (the side the new picture enters from); choice names are case-free with _ for spaces (order=center_out). `transitions.txt` lists all 112 transitions with params and defaults; read it instead of asking filmcraft-cli.

## Speed ramps - ON for every build, clip lengths kept (Justice approved 2026-10-27; see Star Trek\README.txt rule 1)
Since 2026-10-27 ramps run by default and `ramp.keep_length` keeps each clip its cut length, so cuts stay on SongMap's beats (the 2026-10-26 FLORAL edits had them off: crawl into the last frame, lurch into the next clip). `ramp free` = the older shortening behaviour below.
A build with `ramp on` runs ramp.py on each clip: it measures motion (ffmpeg at 128x72, cached in `_motion/` beside the cut list), speeds up stalls (up to 3x, gradual slopes) and places each clip as constant-speed pieces with frame blending (FilmCraft 0.10 ignores Time Remapping keyframes when rendering). The clip's sound is placed under it at normal speed. Report: `<out>.ramps.txt`, one line per clip, motion before -> after. The build line ends with `N ramped`. `python3 ramp.py <video>` prints the same line for one file without building.

## Transition names
HOW TO CHOOSE: Comfort CLAUDE.md section 17 (A:\Ai projects\Comfort\CLAUDE.md) - motion match, graphic/light match, material, music energy, per-song palette. Chained joins = dissolve 12-16.
Aliases: fade/black, white, dissolve, film, vhs, leak, chroma, zoom, czoom, burn, blur, spin, lens.
Any FilmCraft id works: glitch flash whip push slide split stretch roll film_roll cross_zoom zoom_blur radial_blur directional_blur_transition light_leak chroma_leak light_sweep flare glow ray stripe solarize phosphor burn_chroma vhs_damage tv_power flicker earthquake chaos glass kaleidoscope liquid_distortion grunge cross_dissolve film_dissolve additive_dissolve blur_dissolve luma_fade mosaic_transition dip_to_black dip_to_white dip_to_color morph_cut spin_3d page_peel louver slice wave mirror_transition clock_wipe linear_wipe radial_wipe soft_wipe star_wipe neon_wipe panel_wipe.

## Rules
- Sources stay where they are (for example Comfort's output folder). Renders go only to `renders/`.
- Report each build as the one line fc.py prints.

## Song projects (2026-10-25)
Before building or reworking a song's cut list, read its SongMap sheet `projects\<song>\<song>.songmap.txt` once (BPM, beat/bar frames, sections, cue points, lyric lines on timestamps; see A:\Ai projects\Star Trek\SongMap\CLAUDE.md). No sheet yet: `bash "$HOME/mnt/Ai projects/Star Trek/SongMap/sm.sh" '<song.mp3 Windows path>'`.
One FilmCraft project per song in `projects\<song>\`: `<song>.txt` (cut list), `<song>.fcproj` (open in FilmCraft), `<song>.mp4` (render).
Songs: ciudad_fantasma, sentimientos, real_herbalist, cruzando_fronteras, dem_cyaan, lily_pad, conqueress, fauna, floral (the last three are Marie Vie: MP3, lyrics .txt/.srt/.lrc inside the project folder, song on A2 through the `music` line). Sequences are 1920x1080 @ 60 fps (concert screen). Clips are the `_stage60` versions from Comfort's `out\videos`.
To build a song's video: add `clip <full path>` / `> transition frames` lines to its cut list, then `python3 fc.py build projects/<song>/<song>.txt`. Build through Comfort (Windows, no time limit): drop `{"filmcraft_build": "projects/<song>/<song>.txt", "name": "fc_<song>"}` into A:\Ai projects\Star Trek\Comfort\inbox\fc_<song>.json; the result line lands in Comfort\out\fc_<song>\_done.txt. The Linux device shell kills background jobs and anything over 3 minutes, so don't build there.
MOUNTS now also maps A:\artcraft and A:\Ai projects; the first mapping whose folder is connected in the session wins.

## Whole-song music videos: shots.txt -> song_jobs.py -> song_cut.py (2026-10-27)
FIRST read Star Trek\README.txt (the whole page; it wins over this file). The shot list IS the artistic decision: no fixed shot length, one scene
per section, use only the moving part of each H3 shot, look at a contact sheet, and let the Overseer check every shot (never idle the GPU waiting for approval). (2026-10-27: a fixed 2 s rule made FLORAL a jumbled mess; those shot lists must be rewritten.)
Don't hand-type hundreds of cut lines or Comfort jobs. Per song write ONE shot list `projects\<song>\<song>.shots.txt`
(format in the song_jobs.py docstring; floral/fauna/conqueress are full examples): styles (LoRA, style words, palette,
trigger, look), `@ <second> <section>` anchors from the SongMap sheet, then one line per shot:
`LEN | SRC | TRANSITION | label | subject ; framing | motion`, LEN in bars (1, 0.5, 2), `s2.6` seconds, `*` = fill to the next @.
SRC = a style key (new picture + shot), `=label+1.8` (reuse a shot later into it), `run name:slot`, `clip file@sec`, `K@folder/pic.png`.
- `python3 song_jobs.py <song>` checks it (one line: shots, ASL, pictures, runs, hours) and writes `<song>.plan.json` + `_jobs\`;
  `--queue` puts the jobs in Comfort's inbox once (queued.txt). Per batch: picture job(s), H3 Reference Video runs (3 shots each),
  then a FilmCraft build. Queue names `z<batch><song letter>..` sort after older jobs; batch numbers decide which song finishes first.
- `song_cut.py` turns the plan into the cut list; fc.py reruns it at every build of a cut list whose first line says
  "built by song_cut.py", using every shot rendered so far (so queued builds grow as shots land). Shots longer than 4.88 s are slowed.
- `copy <path>` in a cut list (`#copy` in shots.txt) copies the finished video to the song's Preview folder after each build.
- To change shots: edit shots.txt and rerun song_jobs.py; jobs already queued are not re-queued (it says which changed).

## Titles and subtitles (2026-10-26)
Text lives in the cut list (every build rebuilds the project from scratch). Never add text through Krea or by generating video. fc.py only; filmcraft-cli/filmcraft.exe stay untouched.
- `text "WORDS" a-b style=<s> pos=<p> [prop=value ...]` under a clip: a-b = seconds from that clip's start on the timeline (`2.3-` / `2.3-end` = to its end; no range = whole clip). Goes on V2; overlapping titles stack on V3, V4. Any style prop can follow as an override: `size=120 tracking=150 fade=12,24 font=Impact font_style=Regular` (quote values with spaces). `pos=x,y` = left edge + baseline in 1920x1080 px. `\n` = new line. No ` #` inside the text (starts a comment).
- `subs <file.srt> style=lyrics [offset=s]`: path relative to the cut list, or a full path; cue times are sequence seconds (+offset). One Subtitle caption track per subs line, one style, burned into the mp4 (export setting `burnCaptions`); the track stays editable in FilmCraft.
- `titles.json` beside fc.py: named styles and positions. Positions (1920x1080, scaled for other sizes; margins 144 px sides, 120 px top, bottom baseline 948): lower-left, lower-third, center, top-left, top-right. Styles: `boss` (RMC name card: Impact, molten-gold gradient #ffe9a8->#b8650c, near-black 6 px outer stroke, soft shadow, tracking 200, size 140, fade 24/18 frames), `clean` (white Inter SemiBold 72, lower-third; the default), `lyrics` (subtitles: Inter 64 white, 4 px black outline, bottom).
- Fonts: every build checks each style's font against what FilmCraft sees and falls back to the style's `fallback`; the build line then ends with `| fonts: X missing->Inter (have: ...)`. On this PC FilmCraft sees Impact, Arial, Segoe UI, Franklin Gothic Medium, Bahnschrift (Regular only); not Bebas Neue, Oswald, Agency FB, Arial Narrow, Bahnschrift Condensed. Linux test builds always fall back (Windows fonts are only visible to the Windows build). `cuts/title_sampler.txt` = font sampler cut list (build it through Comfort, look at one frame).
- Text fades = cross_dissolve on the text clip's own edges (fades to transparent).
- To check a title, extract ONE frame: time = `<out>.cuts.json`[n-2] + seconds into clip n (n = clip number, n >= 2).

Confirmed graphics.set props (FilmCraft 0.10, UI units): font, font_style, size (px), align (left|center|right), tracking (1/1000 em; also pads after the last letter), leading, kerning, ligatures, baseline_shift, faux_bold, faux_italic, fill_color "#rrggbb", fill_kind ("Solid" | "Linear Gradient"), gradient_start, gradient_end, gradient_angle (90 = start colour at the top), stroke, stroke_color, stroke_width, stroke_type (Outer | Inner), stroke2, stroke2_color, stroke2_width, stroke2_type (a wider stroke2 shows as a ring outside stroke 1), background, background_opacity, shadow, shadow_color, shadow_opacity (%), shadow_angle, shadow_distance, shadow_size, shadow_blur, position [x,y] (point text: alignment point on the first baseline), scale, rotation, opacity (%). Not props: corner_radius, shadow_softness, shadow_spread. graphics.list gives localBounds (line box around the baseline) used for positioning.
captions.setStyle keys: font, size, color "#rrggbb[aa]", background, backgroundColor "#rrggbbaa", align left|center|right, anchor top|middle|bottom, margin 0..0.45 (fraction of frame height), lineSpacing, outline, outlineColor.
Since 2026-10-27 evening (see Star Trek\README.txt rule 7): `K>label` = a new picture made with Krea 2 edit from that shot's
picture (other angles of the same scene); `#build overseer` = no build jobs, the Overseer builds once a batch is checked;
`#people <who>` = the people this song may show (the Overseer's people check; default one tiny far-off woman); `#prefix a` = job-name start; `#inpoint 1.2` = default in-point (the Overseer measures each shot's own); `--batch N` queues
one batch. song_cut.py reads projects\<song>\_review.json (the Overseer's best take, in- and out-point per shot).
