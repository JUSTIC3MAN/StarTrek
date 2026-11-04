LYRICS INBOX

Drop a song in this folder (MP3, WAV, M4A, FLAC, or a video).
Its lyrics appear next to it as  <song>.txt  - and  <song>.lrc  with timings.

Who does the work:
  - Subtitle Studio, while it's open (Start.bat).
  - Otherwise Lyrics.bat, one folder up. Leave its window open; it only uses
    the GPU while a song is being done and frees it a few minutes after.

While a song is running you'll see  <song>.working  with how far along it is.
If one fails, the reason is in  <song>.error.txt.  Drop the song in again
(or save over it) to retry.

Better results:
  hints.txt            names and slang to listen for, used for every song
  <song>.hints.txt     the same for one song; rough lyrics work here too

For Claude:  bash lyrics.sh "<song file>"   prints the lyrics (bash lyrics.sh -h for more).
