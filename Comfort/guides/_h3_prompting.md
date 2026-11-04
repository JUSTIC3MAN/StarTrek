# Prompting MiniMax H3 (video + audio) - official structure

Source: MiniMax's VIDEO_PROMPT_WRITING_GUIDE (base) and the DaSiWa H3 Director docs. H3 generates picture AND sound from one prompt, so describe both.

## Size
Width and height must be multiples of 32 (1376x768 for 16:9, 768x1376 for 9:16, 1024x1024 square). Duration 2-15 s.

## Modes
- T2VA: text only (no alignment line).
- I2VA: starts from a first-frame image.
- FL2VA: goes from a first-frame image to a last-frame image (single shot unless asked otherwise).
- L2VA: ends on a last-frame image; invent a plausible opening.

## Required structure (field names exactly, in this order)
Line 1 (I2VA / FL2VA / L2VA only), then ONE blank line:
- I2VA: For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
- FL2VA: How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the 0.00-second mark of the target video; <Picture 2> (from [Shot 1]) aligns with the 5.00-second mark of the target video.
- L2VA: <Picture 1> (from [Shot N]) aligns with the 5.00-second mark of the target video.   (N = last shot; the time = duration with two decimals)

integrated_multimodal_description: the picture + action + speech, shot by shot.
overall_soundscape: 1-4 English sentences: ambience, sounds of physical actions, non-verbal human sounds, for the whole clip. Do not repeat dialogue or music. N/A only if silence is requested.
non_diegetic_music: 1-3 English sentences: instruments, tempo, rhythm, dynamic changes. No mood words or explanations. N/A if no score.

## Shots and timing
- First shot: [Shot 1] with NO timestamp.
- Later shots: [Shot 2] At 00:03.500, the camera cuts to ...  (MM:SS.mmm, strictly increasing, inside the duration).
- Cut phrases: "the camera cuts to", "the shot cuts to", "the shot changes to". Dissolves/fades only if asked.
- Small framing changes are camera moves, not cuts. A 5 s clip usually wants 1-2 shots.

## Camera vocabulary (write as a clause inside the sentence)
Zoom In/Out, Push In/Pull Out, Pan Left/Right, Truck Left/Right, Tilt Up/Down, Pedestal Up/Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly/Strongly, POV, Roll Clockwise/Counterclockwise. Add "with small/large amplitude" and "at slow/fast speed" when it matters.
Example: The camera pushes in with small amplitude at slow speed toward the singer's face.

## Speech and singing
- Speaker IDs (S1), (S2); same ID across shots; only for characters who actually speak or sing.
- Introduce the speaker outside the tag (age, voice, accent), then: (S1) says: <d>[English] I get off at the next station.</d>
- Keep the user's words exactly. Voiceover: "says in an off-screen voiceover" and state that on-screen lips stay closed.
- Rapping/singing works the same way: (S1) raps: <d>[English] exact lyric line</d>

## On-screen text
Exact words in double quotes: a neon sign reading "OPEN".

## Avoid
A timestamp on Shot 1; rewording dialogue; describing FL2VA reference images as static pictures (describe the motion between them); cuts for tiny framing changes; dialogue repeated in the soundscape; mood words in the music line.

## Example (T2VA, 5 s)
integrated_multimodal_description: [Shot 1] A lone astronaut floats above a neon-lit cyberpunk city at night, rain streaking across the visor as holographic billboards reflect in it. [Shot 2] At 00:03.000, the camera pushes in with small amplitude at slow speed toward the visor as a vast holographic dragon rises through the clouds behind, lighting the scene in pulses of crimson.
overall_soundscape: Rain ticks on metal and glass, a distant city hum rises and falls, and a low synthetic wind sweeps past.
non_diegetic_music: A pulsing dark synthwave beat enters at 00:02.000 and swells into a heavy crescendo as the dragon appears.
