STAR TREK - Justice's music-video production (A:\Ai projects\Star Trek)
Read this whole page before any song-video work. It is the single source: where any other file disagrees, this page wins.

!!! EVERY FINISHED SHOT GOES INTO FILMCRAFT, PLACED PROPERLY, WITH A TRANSITION. NO EXCEPTIONS. !!!
The moment a shot finishes rendering it is placed in the song's FilmCraft project (FilmCraft\projects\<song>\<song>.fcproj):
at its SongMap time from the shot list, its static end cut and the rest slowed to fill its slot, the clip audio cut, and a
real transition on the cut into it and out of it (rule 3). Then the edit is rebuilt and copied to Preview
(when depends on the Overseer level, see OVERSEER LEVELS: strict = after every shot; light/off = once, when the whole song
is placed, or whenever Justice asks).
A shot that is rendered but not in the project, sits at the wrong time, or joins its neighbour with a hard cut is a FAILURE:
fix it before anything else. Whoever finishes or checks shots (the Overseer, Claude, the interface) confirms it from the
build line: "N clips ... N-1 transitions". Never tell Justice a shot is done until it is placed this way.

THE GOAL
Finished music videos for Justice's songs and the artists he works with (Marie Vie, Iration Studio), played on the
screen behind the musicians at concerts. Each one is a real, properly edited music video: beautiful and aesthetic, in
the song's own art style, cut to the music, a smooth transition on every cut, nothing janky, static or "AI-looking".
All the work runs on this PC (RTX 4090) and keeps running without Claude: Claude plans and fixes, the local AI checks
and produces.

WHAT "DONE" LOOKS LIKE
- The song's FilmCraft project (FilmCraft\projects\<song>\<song>.fcproj) holds the WHOLE song on the audio track and
  every clip on the video track at its SongMap time, a transition on every cut, no clip audio.
- The rendered edit is in Preview\<Artist - Song>\ (1080p 60 fps).
- Every generated shot is also in Preview\<Artist - Song>\ as its own file, named by what it shows.

THE PROCESS (one song)
1. SongMap      MP3 -> SongMap\out\<Song>\<Song>.songmap.txt: bars, sections, lyrics on timestamps, drops.
                Every timing decision comes from this sheet.
2. Look         Justice picks the art style from a varied set of Krea 2 pictures (a different style in each).
                The picked look is used for the whole song.
3. Shot list    FilmCraft\projects\<song>\<song>.shots.txt (format: FilmCraft\song_jobs.py docstring and
                FilmCraft\CLAUDE.md). Each section is ONE scene (one place, one light): a master picture and its other
                angles made from it (K>label = Krea 2 edit). Shot length comes from the music: long moving shots in
                intro, verses and outro, faster in choruses; the scene changes on drops and section changes. Lyrics
                as metaphor, never acted out.
4. Generate     song_jobs.py queues it in Comfort: Krea 2 pictures -> MiniMax H3 video -> automatic 1080p60 finish.
5. Place        The moment a shot exists it goes into the FilmCraft project at its SongMap time (song_cut.py + fc.py,
                rebuilt by the Overseer) and into Preview as its own file. A static end is cut and the rest slowed to
                fill the time; fc.py speed-ramps every clip so the joins keep an even tempo.
6. Check        The Overseer (the local AI, Overseer\) checks the pictures and shots at the level Justice picked
                (OVERSEER LEVELS below): strict, light or off.
7. Talk         Justice works with the local AI in the Star Trek interface: "Open Star Trek.bat"
                (http://127.0.0.1:8790/startrek) - latest edit, every decision, and a chat that can redo a shot,
                trim it, set a transition and rebuild.

OVERSEER LEVELS (Justice, 2026-11-03) - Overseer\level.txt holds one word for every song: strict | light | off.
A third word in Overseer\songs.txt overrides it for one song ("floral auto strict"). Change it only when Justice says.
- strict  The Overseer exactly as it ran before 2026-11-03 (never stricter): the vision AI judges every picture and every
          video (people, glitches, frozen, style, beauty), the edit is rebuilt after every shot and watched, up to
          2 re-renders per run right away. Best checking, slowest: on FLORAL it cost about 2 h 20 min.
- light   Claude's recommendation, the default. The GPU only generates. Kept: the quick vision check of each picture
          before it becomes a video (people, wrong framing, style; up to 2 re-makes) and the free ffmpeg motion trims of
          every shot (stray frames, frozen start, frozen end). Not done: vision review of the videos, rebuild after every
          shot, watching the edit. ONE build when the whole song is placed and no re-render is waiting. At most 1
          re-render per run, only for a hard failure (frozen/broken), queued after every first-pass job ("zz" names).
- off     The Overseer does nothing for that song (same as mode off in songs.txt).
Any level, on request: "python Overseer\overseer.py build <song>" (or the interface's rebuild) builds the edit now.

JUSTICE'S HARD RULES
1. Do exactly what he says, at the scope he says it. A fix for one shot touches only that shot; "one generation"
   means one generation.
2. His picks are locked. Never remove or swap a shot he chose; fix it instead (e.g. cut the static end, slow to fit).
3. Every cut has a real transition, chosen by what the two shots share: motion -> cross_zoom / push / whip;
   light -> luma_fade / flare / light_leak; print or paper -> film_dissolve; mist or water -> blur_dissolve / wave.
   Loud ones (flash, glitch, whip) only on a hard hit, at most one per ~30 s. NEVER THE SAME SHOT TWICE IN AN EDIT.
   Not in a row, not later in the song, not as a stand-in while another shot renders (2026-10-27: the meteor showed twice).
   A moment that comes back gets a NEW picture from another angle (K>label, e.g. from behind the woman looking up as the
   meteor comes down). The tools enforce it: song_jobs.py refuses '=label' repeats, song_cut.py places a source only once,
   and a shot that is not ready is held by the shot before it (slowed), never covered by another shot.
4. Only the song is heard: the clips' own audio is always cut.
5. Shot length is an artistic choice from the song, never a fixed number. A shot moves the whole time it is on screen.
6. Art: no photoreal look; styles grounded in what is popular on art sites; Justice picks.
7. The GPU never idles waiting on Claude or on an approval: the Overseer keeps producing. Justice can pause it
   (the interface, or an Overseer\PAUSE file). Comfort Watchdog.vbs keeps Comfort running whenever it is not paused.
8. Check before you claim or act. Comfort is generating ONLY if Comfort\heartbeat.txt was written in the last 60 s
   (Comfort rewrites it every 5 s) AND the last 'flow'/'job' line in Comfort\comfort.log has no OK/FAILED after it.
   A 'flow ...' line alone proves nothing (2026-10-27: Claude called Comfort dead from log silence while a 7-min job was
   running, then tried to open it by controlling Justice's PC - guesses and wasted tokens). Silence in the
   log during a job is normal; only the heartbeat says alive or dead. Stale heartbeat = Comfort is DOWN: say so plainly.
   Comfort starts Comfort\Comfort Watchdog.vbs itself (and the watchdog runs at Windows login): it restarts Comfort.exe
   within ~2 min unless Overseer\PAUSE exists. Still stale after 3 min: ASK Justice to open Comfort ("Open Star Trek.bat").
   NEVER take control of Justice's PC (screenshots, clicks) to open or fix Comfort: it burns tokens; asking is the step.
   Read the log also before cancelling (an empty Comfort\inbox\_CANCEL file cancels WHATEVER job is running).
9. Few Claude tokens: read Overseer\report_<song>.txt and the last log lines, not big files; no wait loops; pictures go
   to Preview, never into the chat.
10. When Justice asks what is finished, list only files he can open and where they are. Answer his question in plain
   text before running any tool.

WHERE THINGS ARE
SongMap\                    song -> timing sheet.          ClaudeSubtitles\SubtitleStudio   lyrics on timestamps.
Comfort\                    the GPU jobs: inbox\ (one file per job, sorted order), out\videos\ (every video),
                            out\video_info\<job>\, comfort.log. How to write jobs: Comfort\CLAUDE.md.
ClaudeComfy\                ComfyUI and its models (Comfort drives it).
FilmCraft\                  fc.py (build), song_jobs.py (shot list -> jobs), song_cut.py (plan -> cut list), ramp.py,
                            transitions.txt (all 112). Cut-list and shot-list syntax: FilmCraft\CLAUDE.md.
Overseer\                   overseer.py (runs inside Comfort between jobs), rules.txt (the local AI's standards),
                            songs.txt (songs in production: auto / check / off), report_<song>.txt, logs\, sheets\.
Preview\<Artist - Song>\    what Justice opens.
CHANGELOG.txt               history and the reasons behind the rules (background only).

NOW (2026-10-27)
- Conqueress v3 (Marie Vie): NEW one-minute cut in production under the Overseer (songs.txt: conqueress_v3 auto,
  conqueress off). FilmCraft\projects\conqueress_v3 (intro to end of verse 1, 0-57.8 s, song trimmed with a fade-out:
  #musicfull off). Opening = one generation conq_v3_shot_a01_one (Preview\Marie Vie - Conqueress\a01 new.mp4); new meteor
  b08 (4.9 s, new Krea 2 picture from the chorus 1 master); new chorus 2 and verse 1 scenes. Edit: Preview\Marie Vie -
  Conqueress\Conqueress v3 (one minute).mp4. Old conq_v2 jobs are held (_hold_* in Comfort\inbox).
- FLORAL and FAUNA: held (_hold_* in Comfort\inbox). Their shot lists use the old fixed 2-second cutting: rewrite
  them by THE PROCESS before adding them to Overseer\songs.txt.
- Sentimientos (Ras Manuel), 2026-11-02: finishing the whole song (3:28). FilmCraft\projects\sentimientos\sentimientos.shots.txt:
  Justice's approved edit (Comfort\out\videos\sentimientos_v2_edit150.mp4, placed noramp) from 0 to 108.4 s - that file has picture only
  to 1:48.9, the rest is black - then new scenes in the same airy gouache style: verse 3 end kites, chorus 5 waterfall of color, chorus 6
  flowers opening (batch 2), inst 1 birds from the house, inst 2 under the lake, verse 4 lanterns, verse 5 fireflies to dawn (batch 1). Overseer\songs.txt: sentimientos auto. Edit: Preview\Ras Manuel - Sentimientos\Sentimientos (full song).mp4.
  Subtitles: the Caprasimo karaoke style Justice picked can't be made in FilmCraft's caption track, so after the build it is burned over
  that edit with ffmpeg/libass: projects\sentimientos\sentimientos.subs.ass, fonts in A:\finished\sentimientos_style_tests\fonts ->
  A:\finished\sentimientos_full_subtitulado.mp4.
