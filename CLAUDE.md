# Star Trek — start here (for Claude)

1. **Not installed on this PC yet** (no `ClaudeComfy\ComfyUI\main.py`, no `FilmCraft\filmcraft-cli.exe`)? Follow
   [README.md](README.md) — the new-PC setup — step by step. Run the commands yourself; ask Justice only where it says ASK.
2. **Installed:** read [README.txt](README.txt) (Justice's production rules, the single source) and
   [OPERATING.md](OPERATING.md) (how the programs work together and how to operate them). Then the manual of the program
   you are about to use: `Comfort\CLAUDE.md`, `FilmCraft\CLAUDE.md`, `SongMap\CLAUDE.md`,
   `ClaudeSubtitles\SubtitleStudio\CLAUDE.md`.

The design in one line: the local AI (Overseer + its planner + Comfort agent, Ollama qwen3.6:27b) runs everything on this
PC, new songs included (MP3 into Overseer\new_songs\ -> finished edit, Overseer\planner.py); Claude is optional and plans or fixes with as few tokens as possible, talks to every program through files, and never takes control
of Justice's screen.

Don't change README.txt unless Justice asks. Keep both PCs in step with git (`git pull` before, commit + push after);
media (`Comfort\out`, `Preview`) is not in git.
