# SongMap - operating manual for Claude
Read this first in any session that uses SongMap. SongMap turns a song file into a timing sheet for FilmCraft edits:
beats, bars, BPM, sections (intro/verse/chorus/bridge/inst/outro), lyrics on timestamps, musical changes and
rhymes. Everything runs on Justice's GPU. Claude never reads audio, never transcribes, never analyses music itself:
it queues a song, gets one line back, then reads the sheet. Justice's rules: low tokens, one call per task,
no computer use, no test files he didn't ask for.

## 1. Run it (device_bash, timeout_ms 180000)
`SM="$HOME/mnt/Ai projects/Star Trek/SongMap"` (if only Star Trek is connected: `$HOME/mnt/Star Trek/SongMap`; `ls $HOME/mnt` once).
- One song (Windows path):        `bash "$SM/sm.sh" 'A:\Music\MarieVie\FLORAL.mp3'`
- A whole folder:                 `bash "$SM/sm.sh" 'A:\Music\MarieVie'`
- Known lyrics (aligned, not guessed): add `-l 'A:\path\lyrics.txt'` (one song per call).
- Also copy results somewhere:    add `-c 'A:\some\folder'`.
- Still working (exit 4):         `bash "$SM/sm.sh" -w 170` - never re-queue the song.
- Status:                         `bash "$SM/sm.sh"`
Prints one line per song: `OK FLORAL 128s | 76.0 BPM 4/bar 79 bars | 9 sections | 41 lyric lines | <sheet path> | copied to ...`
Exit 0 done, 2 failed (reason on the line), 3 SongMap not running -> ask Justice ONCE to double-click
`SongMap.bat` in A:\Ai projects\Star Trek\SongMap (queued songs start by themselves), 4 still working.
Time (measured 2026-10-26, RTX 4090): about 80 s for one 4-min song (lyrics ~65 s, sections ~8 s, beats ~2 s); two songs in one call ~2 min, because models load once per batch. Queue several songs in ONE sm.sh call.

## 2. Read the result
`out\<song>\<song>.songmap.txt` (also copied into `FilmCraft\projects\<song>\` when that project exists).
About 2-3k tokens. Read it once per song when planning or changing that song's cut list; don't re-read it for small edits.
The `.songmap.json` beside it has every beat and word time: read it only to snap one exact cut, with a narrow
python one-liner (never cat it). Lyrics: `<song>.lyrics.txt` (plain), `.lrc` (timed), `.srt` (for the cut list `subs` line).

Sheet layout: header (TEMPO, FRAMES @60 = beat / half beat / bar in frames, SOURCES, CHECK), SECTIONS table
(start, end, bars, name, energy low/mid/high, vocal, rhyme scheme), CUE POINTS (*** = strongest cut or big
transition), TIMELINE (time, bar.beat, lyric line, [rhyme letter], internal rhymes, `>>` musical changes), BAR STARTS.
- CHECK `OK` = bar numbers are reliable. `FIXED` = SongMap moved the grid half a bar (reggae one-drop: beat 3
  heard as 'one'). `LOOSE` = trust the times, not the bar numbers.
- Changes come from the full mix: DROP / LIFT (dB vs the previous 2 bars), STOP (near silence, beats),
  BUILD (4+ rising bars), low end in/out (bass + kick), percussion thins out / kicks in, highs in/out, vocal in/out.
- Rhyme letters are approximate (CMU dictionary for English, Spanish stress rules, a Patois respelling map).

## 3. Using it in FilmCraft (see FilmCraft\CLAUDE.md)
- The song sits on A2 from 0:00 through the cut list `music <song>.mp3` line, so sheet times = timeline seconds.
- Clip lengths: make each clip end on a cue time or a bar start (clip seconds = difference of sheet times).
- Transition lengths in frames: use the header's beat / half-beat frames (at 60 fps). Big transitions on *** cues;
  chained joins stay dissolve 12-16 (Comfort CLAUDE.md section 17); STOP = hard cut or flash on the return;
  BUILD = speed or zoom rising into the peak bar; DROP = cut to a calmer, wider shot; vocal in = new subject.
- Match picture content to the lyric lines of that section (Comfort song briefs), never act the lyrics out literally.

## 4. How it works (for changes)
- `SongMap.bat` -> `songmap.py` watcher (light, heartbeat `.alive.watcher`) -> starts `songmap.py --worker` when
  the inbox has songs; the worker exits after `idle_exit_seconds` (180) so the GPU is free for ComfyUI.
  Before a batch it waits while Comfort's status says running (max 15 min) and asks ComfyUI to unload its models.
- Inbox: an audio file, or `.json` `{"song"|"songs"|"folder", "lyrics", "copy_to"}`. Results: `out\<song>\`,
  one line per job in `jobs\done\<job>.txt` / `jobs\failed\`. `status.txt` = one line. Log: `logs\songmap.log`.
- Lyrics: `sm_lyrics.py` runs with Subtitle Studio's venv (path in config.json), with SongMap's HF_HOME/TORCH_HOME
  removed from its environment so it uses Subtitle Studio's own model cache (never download Qwen twice). It only imports
  Subtitle Studio's modules and drives them its own way: the isolated vocal is cut into pieces of at most 20 s at the
  gaps between phrases (Subtitle Studio's 100 s pieces made Qwen3-ASR loop on sung hooks: FLORAL gave 223 looped
  lines), Qwen's max_new_tokens is capped at 384, a looping piece is split and heard again, and one rule runs over the
  whole song at the end: no 3+ words less than 70 ms apart - piled-up words are spread with their neighbours to at
  least 0.17 s per word over the voiced time (repair_density). Log line per song: logs\lyrics_<time>.detail.log.
- Beat grid: Beat This! runs without DBN (madmom won't install on Python 3.12), so grid.clean_beats drops stray hits
  and fills skipped beats, and bar starts follow the majority phase of the nearby tracked downbeats.
- Deploying changes from a cloud session: device_commit_files once wrote an older copy of a re-staged file. Stage from a
  new folder each time and compare md5sum on both sides. A running worker keeps its code until it exits (180 s idle);
  sm_lyrics.py is started fresh for every batch.
- Old note: `sm_lyrics.py` and Subtitle Studio's modules:
  BS-RoFormer vocal -> Qwen3-ASR 1.7B -> Qwen3-ForcedAligner; known lyrics go through Subtitle Studio's
  `Worker._place_lyrics`. It also writes `mix.wav` (44.1 kHz) used for everything else.
- Beats: Beat This! (`final0`, CPJKU, ISMIR 2024). Sections: SongFormer (ASLP-lab, HF `ASLP-lab/SongFormer`,
  models\SongFormer, transformers 4.51.1). If SongFormer fails, sections come from lyric blocks + energy and the
  sheet says `sections: fallback`. No stem separation for the music: changes are measured on the full mix.
- Code: `smlib/` grid.py (bars, bar.beat, one-drop check), features.py (per-beat levels), changes.py, sections.py,
  rhyme.py, sheet.py (the text layout), models.py, analyze.py. Setup: `setup.bat` (venv, torch cu128 pinned in
  constraints.txt, requirements.txt resolved for Windows / Python 3.12), `tools\fetch_models.py`, `tools\check.py`
  -> `setup_check.txt`.
