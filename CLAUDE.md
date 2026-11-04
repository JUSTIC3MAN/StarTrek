# Star Trek — start here (for Claude)

1. **Not installed on this PC yet** (no `ClaudeComfy\ComfyUI\main.py`, no `FilmCraft\filmcraft-cli.exe`)? Follow
   [README.md](README.md). Justice runs `SETUP NEW PC.bat` himself, because it asks him for his Civitai key; help with errors from `setup\setup_log.txt`.
2. **Installed:** read [README.txt](README.txt), Justice's production rules and the single source; it wins over everything.
   Then read [OPERATING.md](OPERATING.md) for how the programs work together, and the manual of the program you are about to use:
   `Comfort\CLAUDE.md`, `FilmCraft\CLAUDE.md`, `SongMap\CLAUDE.md`, `ClaudeSubtitles\SubtitleStudio\CLAUDE.md`.

The design in one line: the local AI (the Overseer + Comfort's agent, Ollama qwen3.6:27b) runs and checks production on this PC.
Claude plans (shot lists, style rounds) and fixes, with as few tokens as possible. It talks to every program through files and
one-line results, and never takes control of Justice's screen. Don't change README.txt unless Justice asks.

## Claude Code (the terminal) on this PC — read this, it translates the manuals

The manuals were written for the **Claude desktop app**, whose shell is a Linux VM that sees the folders as `$HOME/mnt/...`.
It can't run Windows programs or reach local ports. **Claude Code runs directly on this Windows PC.** Its Bash tool is
Git Bash, and its PowerShell tool is there too. So:

- **Paths.** Where a manual says the desktop path, use the Git Bash path, or the Windows path in PowerShell / job files:

  | Manual (desktop app) | Claude Code, Git Bash | Windows |
  |---|---|---|
  | `$HOME/mnt/Star Trek` or `$HOME/mnt/Ai projects/Star Trek` | `/a/Ai projects/Star Trek` | `A:\Ai projects\Star Trek` |
  | `$HOME/mnt/Ai projects/Comfort`, `$HOME/mnt/Comfort` | `/a/Ai projects/Star Trek/Comfort` | `A:\Ai projects\Star Trek\Comfort` |
  | `$HOME/mnt/ClaudeComfy` | `/a/ClaudeComfy` | `A:\ClaudeComfy` (link to `Star Trek\ClaudeComfy`) |
  | `$HOME/mnt/FilmCraft` (`A:\artcraft\FilmCraft`) | `/a/Ai projects/Star Trek/FilmCraft` | `A:\Ai projects\Star Trek\FilmCraft` |
  | `$HOME/mnt/ClaudeSubtitles/SubtitleStudio` | `/a/Ai projects/Star Trek/ClaudeSubtitles/SubtitleStudio` | `A:\...\ClaudeSubtitles\SubtitleStudio` |

  Job files and cut lists keep Windows paths (`A:\\...` with doubled backslashes inside JSON), exactly as the manuals say.
- **Python.** Run Star Trek's scripts with ClaudeComfy's Python, which has every package they need:
  `PY="/a/ClaudeComfy/venv/Scripts/python.exe"`. There is no `python3` on Windows.
- **No 3-minute limit, Windows programs run.** FilmCraft builds run straight from here (`fc.py` uses `filmcraft-cli.exe`).
  The manuals' detour of building through a Comfort `filmcraft_build` job is only needed in the desktop app.
- **Still files first.** Claude Code could reach ports 8790, 8189 and 11434, but the file interfaces (inboxes,
  `status.txt`, `heartbeat.txt`, reports, one-line results) cost far fewer tokens. Keep using them.
- **Never take control of the screen**, and don't launch the GUI programs yourself. When Comfort (`Open Star Trek.bat`),
  SongMap (`SongMap\SongMap.bat`) or the lyrics inbox (`ClaudeSubtitles\SubtitleStudio\Lyrics.bat`) needs to be running, ask
  Justice to double-click it (README.txt rule 8). Queued work starts as soon as it runs.

### The everyday commands (one call each, Git Bash)

```bash
ST="/a/Ai projects/Star Trek"; PY="/a/ClaudeComfy/venv/Scripts/python.exe"
# Is Comfort alive? (README.txt rule 8: only a heartbeat younger than 60 s says so)
cd "$ST/Comfort"; echo "heartbeat $(( $(date +%s) - $(stat -c %Y heartbeat.txt) ))s ago"; cat status.txt; tail -3 comfort.log
# Overseer: status / build <song> / mode <song> auto|check|off / shots <song> [word] / setshots <song> <file> / pause / resume
"$PY" "$ST/Overseer/overseer.py" status
# A song's shot list -> Comfort jobs (check first, then queue)
cd "$ST/FilmCraft" && "$PY" song_jobs.py <song> && "$PY" song_jobs.py <song> --queue
# Build a FilmCraft edit (prints one line)
cd "$ST/FilmCraft" && "$PY" fc.py build projects/<song>/<song>.txt
# SongMap: song -> timing sheet (SongMap.bat must be running; exit 3 = ask Justice to start it, 4 = run again with -w 170)
bash "$ST/SongMap/sm.sh" 'A:\Music\Artist\Song.mp3'
# Lyrics for a folder of songs (Lyrics.bat or Subtitle Studio must be running)
bash "$ST/ClaudeSubtitles/SubtitleStudio/Lyrics/lyrics.sh" -w 170 "/a/Music/<folder>"
```
A Comfort job: write it under a dot-name in `$ST/Comfort/inbox/` and `mv` it to its real name. Then read
`out/<name>/_done.txt` (videos: `out/video_info/<name>/_done.txt`), as `Comfort\CLAUDE.md` sections 3-5 describe, with the Git Bash paths above.
Pictures go to `Preview\`, never into the chat.

Start Claude Code in this folder: double-click **`Claude Star Trek.bat`**, or run `claude` in `A:\Ai projects\Star Trek`.
