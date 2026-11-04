# Star Trek — HOW IT WORKS AND HOW TO OPERATE IT

New PC? Install first: [README.md](README.md). The production rules — what a finished video must be, the Overseer levels,
Justice's hard rules — are in **[README.txt](README.txt)**. That page wins wherever anything else disagrees; this page
explains the machine around it.

## The design: the local AI does the work, Claude is optional

Star Trek runs with no Claude at all. Drop in an MP3 and the local AI plans, generates, checks and edits the whole video
(next section). When Claude is there, it spends few tokens: it can plan or rework a song by hand and fix tools.

- **The PC does the production.** Every generation, check, edit and render runs on the local GPU (built on an RTX 4090).
- **The local AI is in charge of production.** That is `qwen3.6:27b` in Ollama, used by both the Overseer and Comfort's agent.
  The **Overseer** runs inside Comfort between jobs. It feeds the next batch so the GPU never sits idle, checks pictures
  and shots at the level Justice picked, re-makes failures, places every shot in the song's FilmCraft project and builds
  the edit. **FilmCraft is driven entirely by text cut lists through `fc.py`**, so the Overseer and Claude can both run it
  without touching the FilmCraft window. Justice talks to the local AI in the **Star Trek interface**, not in a Claude chat.
- **Claude (optional) plans and fixes.** The local planner writes a new song's style round and shot list by itself;
  Claude can write or rework one by hand, change tools when something is wrong, and answer Justice. It never babysits renders, never reads videos or big files, never transcribes or analyses
  audio itself, and never runs wait loops. Each tool answers Claude with **one line** (`fc.py build` → `ok renders/x.mp4 …`,
  `sm.sh` → `OK Song 128s | 76 BPM …`, Overseer → `report_<song>.txt`).
- **Every program talks through files**: an inbox folder in, a one-line result or report out. That is how the Overseer,
  Claude and Justice's interface all control the same programs without stepping on each other.

## A new song with no Claude: drop the MP3 in

1. Put the song in **`Overseer\new_songs\`**, named **`Artist - Title.mp3`** (or say *"new song A:\Music\X\Song.mp3"* in the
   Star Trek interface chat). Comfort must be running (`Open Star Trek.bat`).
2. The Overseer takes it from there with the local AI (`Overseer\planner.py`, one step per tick). Progress shows in the
   interface under the song's name and in `Overseer\logs\<song>.log`. It goes through:
   - **SongMap**: the project folder `FilmCraft\projects\<song>\` with the MP3, and the timing sheet. SongMap is started automatically.
   - **Style round**: the local AI writes N pictures (6 by default), each in a **different** installed Krea 2 style and from a
     **different** part of the lyrics, following README.txt and Comfort\CLAUDE.md section 16. Comfort renders them into
     `Preview\<Artist - Title>\` as "styles v1 …png", and the brief is written to `Comfort\songs\<Artist - Title>\brief.md`.
   - **Pick**: Justice picks the look: *"pick <song> <label>"* in the chat (the labels are in the file names), or the label in
     `Overseer\plans\<song>.pick.txt`. No pick after **30 minutes**: the vision AI scores every picture and takes the
     best, so the GPU never waits.
   - **Shot list**: the local AI writes `FilmCraft\projects\<song>\<song>.shots.txt` for the whole song from the SongMap
     sheet. That means one scene per section, shot lengths from the music, a real transition on every cut and every shot a
     new picture. `song_jobs.py` checks it, and any error goes back to the AI (up to 4 tries).
   - **Production**: the jobs are queued and the song is set to `auto` in `songs.txt`. From here it's the normal Overseer:
     pictures → checks → H3 videos → 1080p60 → placed in FilmCraft at their SongMap times → edit built →
     `Preview\<Artist - Title>\<Artist - Title> (full song).mp4`.
3. Change course any time in the chat: *"restyle <song>"* (a new style round), *"replan <song>"* (a new shot list),
   *"planstatus"*. Or redo, trim or change the transition of one shot the usual way.

Settings in `Overseer\planner.json`: `styles_count`, `pick_wait_minutes`, `max_tries`, `model` (empty = Comfort's model;
on a 32 GB card try `qwen3.6:35b`), `people` (who may appear; empty = the local AI decides per song).
If a song says **STUCK** (no valid shot list after 4 tries): *"replan <song>"*, or have Claude fix the shot list.

## The programs and how they connect

```
 song.mp3 ──► SongMap ──────────► <Song>.songmap.txt   (bars, sections, lyrics on timestamps, drops, rhymes)
                 │  uses Subtitle Studio's lyric models
                 ▼
 Claude writes FilmCraft\projects\<song>\<song>.shots.txt   (the creative plan, from the sheet + README.txt rules)
                 │
 FilmCraft\song_jobs.py ──► Comfort\inbox\  (one job file per picture / video / build, in sorted order)
                 │
 Comfort  ──► ComfyUI (ClaudeComfy, port 8189): Krea 2 pictures ► MiniMax H3 video ► Stage 1080p60 finish
   │          results: Comfort\out\videos\<job>.mp4, out\video_info\<job>\_done.txt
   │
   └─ between jobs: Overseer tick (local AI, Ollama) ── checks ► re-makes ► _review.json ► song_cut.py ► fc.py build
                                                                                       ▼
                                FilmCraft\projects\<song>\<song>.fcproj + render ► Preview\<Artist - Song>\
```

| Folder | What it is | Manual for Claude |
|---|---|---|
| `Comfort\` | Justice's own program: drives ComfyUI by inbox jobs, runs the local AI agent, the Overseer and the Star Trek interface (`Comfort.exe` → `comfort_app.py`, port 8790) | `Comfort\CLAUDE.md` |
| `ClaudeComfy\` | ComfyUI v0.39.2 + custom nodes + models + workflows (`ComfyUI\user\default\comfort_api\*.api.json` are the ones Comfort runs) | `ClaudeComfy\READ ME.txt`, `Comfort\guides\*.md` |
| `Overseer\` | `overseer.py` (tick / status / pause / resume / build), `rules.txt` (what the local AI judges by), `songs.txt` (auto / check / off per song), `level.txt` (strict / light / off), `report_<song>.txt`, `logs\`, `sheets\`, `startrek.html` (the interface) | README.txt + top of `overseer.py` |
| `FilmCraft\` | `fc.py` (cut list → FilmCraft project + render, speed ramps, transitions, titles, subtitles), `song_jobs.py` (shot list → Comfort jobs), `song_cut.py` (plan + Overseer verdicts → cut list), `ramp.py`, `transitions.txt` (all 112), `titles.json`, `projects\<song>\` | `FilmCraft\CLAUDE.md` |
| `SongMap\` | MP3 → timing sheet (`sm.sh` from a Linux shell, `SongMap.bat` on Windows) | `SongMap\CLAUDE.md` |
| `ClaudeSubtitles\SubtitleStudio\` | Lyrics on timestamps (Qwen3-ASR), caption editor and export; `Lyrics\` inbox for lyric sheets | `ClaudeSubtitles\SubtitleStudio\CLAUDE.md` |
| `ClaudeSubtitles\` (root) | Subtitle Animator: typed lyrics → transparent ProRes overlay | `ClaudeSubtitles\README.md` |
| `Preview\<Artist - Song>\` | What Justice opens: the latest edit and every shot as its own file | — |

## Daily operation

| Do this | How |
|---|---|
| Start everything | Double-click **`Open Star Trek.bat`**. It starts Comfort if needed (Comfort starts Ollama, ComfyUI and its watchdog), then opens http://127.0.0.1:8790/startrek |
| Talk to the local AI | The Star Trek interface: latest edit, every decision, and a chat that can redo a shot, trim it, set a transition and rebuild. Comfort's own window (Agent tab) is the general-purpose local AI chat |
| Pause production | The interface's pause, or create an empty file `Overseer\PAUSE` (the watchdog then leaves Comfort closed). Delete it to resume |
| Choose which songs run | `Overseer\songs.txt`: `<song> auto` (keep producing), `check` (only check), `off`. Optional third word = level for that song |
| Choose how much the local AI checks | `Overseer\level.txt`: `strict` / `light` (default) / `off` — exact meaning in README.txt, OVERSEER LEVELS |
| Build an edit now | `python Overseer\overseer.py build <song>` (or the interface's rebuild) |
| Is Comfort alive? | Only `Comfort\heartbeat.txt` written in the last 60 s says so (README.txt rule 8). Log silence during a job is normal |
| Analyse a new song | Drop the MP3 on `SongMap\SongMap.bat` (or into `SongMap\inbox\`); sheet in `SongMap\out\<Song>\` and copied into its FilmCraft project |
| Lyrics for a folder of songs | `ClaudeSubtitles\SubtitleStudio\Lyrics.bat`, drop songs into its `Lyrics\` folder |
| Open an edit in FilmCraft | `FilmCraft\filmcraft.exe`, open `FilmCraft\projects\<song>\<song>.fcproj` (fc.py rebuilds it from the cut list, so make lasting changes in the cut list) |

## One song, start to finish (who does what)

1. **SongMap** makes the sheet (automatic for a dropped MP3).
2. **Look:** a style round of Krea 2 pictures, each one a different art style. The local planner writes it, or Claude
   does by hand (`Comfort\CLAUDE.md` section 16). Justice picks; with no pick, the vision AI picks after 30 minutes.
3. **Shot list** `FilmCraft\projects\<song>\<song>.shots.txt`: written by the local planner from the sheet and the
   README.txt process, checked by `song_jobs.py`. Claude can write or rework it instead, which costs Claude tokens only here.
4. **Comfort + Overseer** take it from there with no Claude: pictures → checks → videos → 1080p60 finish → placed at their
   SongMap times with a transition on every cut → built → copied to Preview.
5. **Justice** watches the edit in the interface or in Preview and asks for changes in the interface chat (redo, trim,
   transition, replan, restyle).

## How Claude reaches the programs

- **Claude Code running on this Windows PC:** run the Python tools directly, e.g. `python FilmCraft\fc.py build <cut list>`,
  `python Overseer\overseer.py status`, and write job files into `Comfort\inbox\`.
- **Claude desktop app with the Star Trek folder connected** (the device shell is a Linux VM): it can't reach the ports or
  start Windows programs, so it talks to everything through files. The folder shows up as `$HOME/mnt/Star Trek`. Older
  paths in the manuals (`$HOME/mnt/Ai projects/Comfort`, `A:\artcraft\FilmCraft`, `A:\Ai projects\Comfort`) are the same
  folders; the setup recreates those links. SongMap: `bash "$HOME/mnt/Star Trek/SongMap/sm.sh" 'A:\Music\X\Song.mp3'`.
  Lyrics: `bash "$HOME/mnt/Star Trek/ClaudeSubtitles/SubtitleStudio/Lyrics/lyrics.sh" -w 170 <folder>`.
  Builds longer than 3 minutes go through a Comfort `filmcraft_build` job, not the device shell.
- **Never** take control of Justice's screen to open or fix something; ask him to double-click the program.

## Token rules for Claude (from README.txt rule 9 and the manuals)

Read `Overseer\report_<song>.txt` and the last lines of a log, not whole files. Read a SongMap sheet once per song.
Never read `.fcproj` files, videos or `filmcraft-cli` output. One command per task; no wait loops on renders. Pictures go
to Preview, never into the chat. When Justice asks what is finished, list only files he can open and say where they are.

## When something is wrong

| Symptom | Look at |
|---|---|
| Nothing is generating | `Comfort\heartbeat.txt` age, then the last lines of `Comfort\comfort.log`; `Overseer\PAUSE` present? song `off` in songs.txt? |
| A song stopped | `Overseer\report_<song>.txt`, then `Overseer\logs\<song>.log` (last lines) |
| A build failed | the one line `fc.py` printed; `FilmCraft\projects\<song>\<song>.ramps.txt` for speed ramps |
| ComfyUI node or model error | `ClaudeComfy\ComfyUI\` console/log; missing model: `A:\ClaudeComfy\venv\Scripts\python.exe setup\download_models.py --list` |
| SongMap / Subtitle Studio | `SongMap\status.txt`, `SongMap\logs\songmap.log`; `ClaudeSubtitles\SubtitleStudio\lyrics.log` |

History and the reasons behind each rule: `CHANGELOG.txt` (background only).
