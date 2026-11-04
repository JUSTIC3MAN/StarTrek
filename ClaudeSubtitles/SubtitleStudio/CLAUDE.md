# Subtitle Studio - operating manual for Claude
Read this first in any session that opens this folder. Justice's rules: no test files or extra steps he didn't ask for, no computer use, one call per task; his songs folder is A:\Music\ras manuel. Keep it current when you change the Lyrics inbox.

## 1. Lyrics from MP3s (the low-token way)
Subtitle Studio can turn any song into a lyric sheet on Justice's GPU: BS-RoFormer pulls the vocal off the
beat, Qwen3-ASR 1.7B hears the words (English, Spanish, mixed), Qwen3-ForcedAligner times them. Claude never
transcribes anything itself and never reads audio: it drops files and reads a one-line answer.

The device shell is a Linux VM: it can NOT reach the app's port or launch Windows programs. Talk to it only
through files, with `Lyrics/lyrics.sh`. Do NOT use computer use to start anything.

| Windows path | Device shell path (device_bash) |
|---|---|
| A:\Ai projects\ClaudeSubtitles\SubtitleStudio | `$HOME/mnt/ClaudeSubtitles/SubtitleStudio` (or `$HOME/mnt/SubtitleStudio` if only that folder is connected; `ls $HOME/mnt` once) |

## 2. One call per request (device_bash, timeout_ms 180000)
- **A folder of songs** (Justice connects it to the chat; it shows up under `$HOME/mnt/<folder name>`):
  `bash "$SS/Lyrics/lyrics.sh" -w 170 "$HOME/mnt/<folder>"`
  Writes `<Song Title>.txt` (just the lyrics, nothing else) into that folder. Prints ONE line, e.g.
  `3/5 done, 2 to go - now: Dem Cyan.mp3 (55% Transcribing...). Run the same command again to keep waiting.`
  Repeat the identical command until it says `5/5 done`. Don't cat the text files unless he asks to see them.
- **One song, lyrics in the chat:** `bash "$SS/Lyrics/lyrics.sh" -w 170 "<song.mp3>"` prints the sheet.
  `-t` prints the timed `.lrc` instead.
- **Status:** `bash "$SS/Lyrics/lyrics.sh"`.

Exit codes: 0 finished, 2 failed (reason printed), 3 PC side not running, 4 still working (run again).
Exit 3 = nothing on the PC is watching the inbox. Ask Justice once to double-click **Lyrics.bat** in the
SubtitleStudio folder (or to open Subtitle Studio with Start.bat); the songs already queued run as soon as it starts.

Timing on the 4090: the first song of a session also loads the models (~20-40 s), then roughly 30-60 s per
3-minute song.

## 3. Inbox sheet (internal; folder mode strips the title/artist lines and names the file after the title)
```
Song Title
Artist: Artist Name

lyric line (about one bar)
lyric line

next section after a pause of 2 s or more
```
Title/artist come from the MP3 tags, else from the file name with `(Official Video)`, `[videoID]`,
`- @channel`, producer credits stripped. In folder mode a song with no artist in its name gets the folder's
name as artist when other songs in that folder carry the same artist. A `.txt` that already sat beside a
song (newer than the song) is never overwritten; the summary counts it as "already had a .txt".

## 4. How it works (for changes)
- `Lyrics\` is the inbox. A song in it with no up-to-date `<song>.txt` gets done. While running,
  `<song>.working` holds e.g. `42% Isolating the vocal... [headless 1234]`; failures write `<song>.error.txt`.
  `<song>.lrc` = the same lines with timestamps. Folder mode copies songs into the inbox and copies each
  finished `.txt` back beside the original (the inbox keeps the copies; the device shell can't delete).
- Who does the work: Subtitle Studio while it's open (`server.py` -> `lyricsfile.start_in_studio`, through the
  editor's GPU queue, job kind `lyricsfile` in `studio/pipeline.py`), otherwise `Lyrics.bat` -> `lyrics.py`,
  which stays light and starts `lyrics.py --worker` only when a song is waiting; the worker exits 3 minutes after
  the last song, so the GPU is free for ComfyUI.
- Heartbeats: `Lyrics\.alive.studio` / `.alive.headless` = `<unix time> <pid>`, rewritten every 1-3 s.
  A claim whose owner's heartbeat is stale is taken over.
- `Lyrics\hints.txt` (every song) and `<song>.hints.txt` (one song): names and slang passed to Qwen3-ASR as context.
- Line breaking: `LINE_CHARS` 60, `LINE_WORDS` 14, `LINE_PAUSE` 0.5 s, `SECTION_GAP` 2.0 s in `studio/lyricsfile.py`.
- Test one file by hand on the PC: `venv\Scripts\python lyrics.py "path\to\song.mp3"`. Log: `lyrics.log`.
