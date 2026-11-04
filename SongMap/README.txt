SONGMAP - your song's map for the video edit
==================================================
Give it a song (MP3, WAV, FLAC, M4A). On your GPU it works out:
  - BPM, every beat and every bar start
  - intro / verse / chorus / bridge / instrumental / outro, with their times
  - the lyrics on timestamps (Subtitle Studio's models: vocal split, Qwen3-ASR, word timing)
  - musical changes: drops, lifts, stops, builds, low end in and out, percussion in and out, vocal in and out
  - rhymes: end-rhyme letters per line and internal rhymes (approximate)
and writes one text sheet that Claude reads to place cuts and transitions on the music.

START IT
  Double-click SongMap.bat. The first time it installs itself (5-20 minutes, once).
  Leave the window open - Claude can then send it songs any time.
  About 2-3 minutes per song.

GIVE IT A SONG YOURSELF
  Drag songs (or a folder) onto SongMap.bat, or drop them into the "inbox" folder.

RESULTS
  out\<song>\<song>.songmap.txt     the sheet (open it in Notepad to see it)
  out\<song>\<song>.lyrics.txt      lyrics   (.lrc and .srt = timed versions)
  When FilmCraft has a project with the song's name, everything is also copied into
  FilmCraft\projects\<song>\.

KNOWN LYRICS
  Put the lyrics next to the song as <song>.lyrics.txt (or tell Claude where they are):
  SongMap then times those exact words instead of guessing them.

If something looks wrong: status.txt (one line) and logs\songmap.log.
