# Subtitle Animator

Type your lyrics, pick a font and some effects, hit Export. You get a single
**transparent ProRes 4444 .mov** — drag it straight onto your timeline in After
Effects or Premiere and it sits over your footage as a layer. No green screen,
no keying, no matte.

Built for music videos. No audio analysis, no song file needed — you type the
lyrics and set the tempo yourself.

---

## Start it

**Windows** — double-click **`Start.bat`**.

**Mac / Linux** — `./start.sh` (run `chmod +x start.sh` once first).

Your browser opens automatically. Leave the black console window open while you
work; closing it shuts the app down.

### What you need installed

| | Needed for | Get it |
|---|---|---|
| **Python 3** | running the app at all | [python.org/downloads](https://www.python.org/downloads/) — tick **"Add python.exe to PATH"** |
| **ffmpeg** | `.mov` export | `winget install Gyan.FFmpeg`, then reopen the app |

Without ffmpeg everything still works — you just export a **PNG sequence**
instead, which After Effects imports natively (File ▸ Import ▸ File, tick
*PNG Sequence*). If you'd rather not use a package manager, drop `ffmpeg.exe`
into the `bin` folder here and it'll be found.

---

## The workflow

1. **Type your lyrics** in the text box, top left. One line per line.
2. **Pick a preset** from the dropdown at the top to get in the neighbourhood,
   then adjust.
3. **Scrub or hit play** to check the timing. Space bar toggles playback.
4. Click **Still…** above the preview and load a frame grab from your actual
   video — now you're judging the text against the real background instead of a
   checkerboard.
5. **Export** — top right. Set the file name and format in the *Output* bar
   below the preview first. The file lands in the `output` folder, and the
   green confirmation has an **Open folder** button.

Everything you interact with sits along the top — preset and Export in the
header, transport and output settings in the two bars under it. The preview
gets all the remaining space and scales itself to fit, so you shouldn't ever
need to zoom your browser.

If it still feels tight: **Zoom** (second bar) switches the preview between Fit
and fixed percentages, and the **☰** button top left — or the **Tab** key —
hides the control panel entirely for a full-width preview.

### Importing into After Effects

File ▸ Import ▸ File ▸ pick the `.mov`. If AE asks about alpha interpretation,
choose **Straight – Unmatted**. Drop it above your footage. That's it.

Premiere is the same — import and drag onto a video track above your clip.

---

## The effects

### Write-on — letters drawn left to right

Instead of the words appearing all at once, each letter is drawn on stroke by
stroke, left to right, like it's being handwritten.

- **Write speed** — letters per second. 18 reads as brisk handwriting. Drop to
  5 for a slow deliberate scrawl; push past 40 and it snaps on almost instantly.
- **Stroke overlap** — at `1`, each letter finishes exactly as the next starts.
  Above `1` several letters are drawing at once, which flows more like real
  handwriting than a strict one-at-a-time queue.
- **Pen edge softness** — feathers the leading edge so you don't see a hard
  wipe line. A few pixels is usually enough.

Pairs beautifully with the `Bebas Neue` and `Righteous` fonts.

### Flag wave

Displaces the text column by column so it ripples like cloth.

- **Anchored at** is the setting that matters most. Anchoring the left edge
  means the text barely moves at the "flagpole" and swings hard at the free
  end — that asymmetry is what makes your eye read *flag* instead of *generic
  wobble*. Set it to *Nowhere* for an even ripple.
- **Second wave** mixes in a slower out-of-sync ripple so the motion never
  looks like a clean sine curve.
- **Light & shade** darkens the folds and highlights the crests. This is what
  sells the 3D — try turning it to 0 and back to see how much work it's doing.
- **Perspective squash** stretches and compresses each column as it turns away
  from camera.

### Colour

- **Solid** — one colour.
- **Gradient** — as many stops as you want. **Gradient sweep** slides it
  through the letters over time; set it to 0 to hold still. The gradient is
  locked to the text block, so it doesn't slide around when letters pop.
- **Rainbow cycle** — hues roll over time. **Hue spread** sets how far apart
  neighbouring letters sit on the colour wheel; **cycle speed** how fast the
  whole thing rotates. Set spread to 0 and the whole line changes colour
  together.
- **Palette** — cycle a fixed set of swatches per letter, word, or line.
  Right-click a swatch to delete it.

### Outline

In **Colour & Outline**, under the fill controls. On by default at 9px black,
which is what keeps white text readable over busy footage — the single most
useful setting in the app.

**Outline thickness** goes up to 80px. Over dark or simple footage 4–8px is
plenty; over bright, busy, or fast-cutting footage go 12–16px. Set the fill to
white and the outline to black and it will read against literally anything.

The outline is a separate layer from the fill, so a gradient or rainbow fill
doesn't drag the outline colour with it — the edge stays exactly the colour you
picked.

### Rises and exits

**Animate Out** controls how the text leaves. **Rise up** lifts it off the top
of frame, and **travel distance** goes to 2600px.

Distances in context — the frame is 1080px tall at HD, 2160px at 4K:

| Travel | What it does to centred text |
|---|---|
| ~270 | drifts up a quarter of the frame |
| ~540 | carries it from centre to the top edge |
| 900+ | lifts it clean off the top |
| 2600 | off screen even at 4K |

The **Rise & Vanish** preset is built exactly on this: the words slide up into
place, hold, then lift out of frame. **Lift Off** does the same thing letter by
letter so the line peels upward.

Set **Applies to** and **Stagger** to control whether the whole line leaves at
once or rolls out letter by letter.

### Beat pop

A scale punch on every beat, with a damped spring settle.

Set **BPM** to your track's tempo and the text locks to the kick. **Settle
speed** high snaps back instantly; low keeps it wobbling into the next beat.
**Hit every** lets you punch on every 2nd or 4th beat instead. If the first hit
lands early or late against your audio, nudge **beat offset**.

Set **Applies to** to *Per letter* with a small **ripple delay** and the punch
rolls across the line instead of hitting all at once.

### Entrances

Fade, pop (with overshoot), scale, slide from four directions, drop-and-spin,
blur-into-focus, and write-on. All of them can trigger per letter, per word,
per line, all at once, or in random order.

---

## Presets

Nineteen starting points in the header dropdown. They never touch your text or
resolution, so you can audition all of them against your actual lyrics.

| | |
|---|---|
| **Clean Caption** | Plain white, black outline, quiet fade. The safe one. |
| **Bold Impact** | Huge Anton, 15px outline, hard offset shadow, overshoot pop. |
| **Trap Punch** | Archivo Black, heavy outline, hits on a 140 BPM kick. |
| **Bass Drop** | Enormous type, cyan glow, a violent slam every 4th beat. |
| **Hyperpop** | Rainbow Bungee, magenta glow, letters popping at 160 BPM. |
| **Retro Bounce** | Pastel palette, hard shadow, letters drop and spin in. |
| **Drill Stencil** | Black Ops One, red offset shadow, slides in from the right. |
| **Rise & Vanish** | Slides up into place, holds, then lifts out of frame. |
| **Lift Off** | Same idea letter by letter — the line peels upward. |
| **Silk Banner** | Gold gradient on a slow heavy flag wave. |
| **Flag Wave** | Sunset gradient, faster ripple. |
| **Ink & Wave** | Write-on and flag wave together, rainbow fill. |
| **Write On** | Clean handwriting reveal, Bebas Neue. |
| **Signature** | Slow, deliberate, soft-edged pen. Very deliberate pacing. |
| **Rainbow Cycle** | Hues rolling through every letter. |
| **Chrome Sweep** | Brushed metal with the highlight sliding through. |
| **Neon Sign** | Monoton tube lettering with a magenta glow and a slow pulse. |
| **Cinematic Wide** | Thin, hugely tracked, blurs into focus and fades out. |
| **Ghost Fade** | Soft blur-in, letters rise away at the end. |

Presets only change the clip length when they need room for an exit to play out
— **Rise & Vanish**, **Bass Drop**, **Silk Banner**, **Signature** and
**Cinematic Wide** set their own.

---

## Batching a whole song

Leave a blank line between blocks in the text box, tick **One file per block**,
and you get a separate numbered `.mov` for each — `verse_01.mov`, `verse_02.mov`
and so on, all with identical styling. Drop the whole folder into AE at once and
slide each one to its cue.

```
WE RUN THE NIGHT

UNTIL THE MORNING COMES

AND NOTHING ELSE MATTERS
```

→ three files.

---

## Fonts

30 display faces, all **SIL Open Font License or Apache 2.0** — free to use in
commercial work, including released music videos. They load from Google Fonts
automatically.

To work offline, run this once:

```
python download_fonts.py
```

It caches every font into the `fonts` folder (~15 MB) and the app picks them up
on next launch. Delete `fonts/fonts.css` to go back to loading from Google.

Grouped by feel:

- **Condensed** — Anton, Bebas Neue, Oswald, Fjalla One, Teko, Staatliches, Big Shoulders
- **Heavy** — Archivo Black, Montserrat, Inter, Poppins, Chivo, Syne, Unbounded, Passion One
- **Display** — Alfa Slab One, Ultra, Titan One, Lilita One, Bowlby One, Luckiest Guy, Shrikhand, Sigmar One, Black Ops One, Righteous
- **Retro** — Bungee, Bungee Inline, Monoton, Rubik Mono One

---

## Saving a look

**Save look** writes every setting to a `.json` file. **Load look** brings it
back. Handy for keeping one consistent style across a whole video, or reusing a
style between songs. The text isn't overwritten when you switch presets, so you
can audition looks against your actual lyrics.

---

## Formats

| Format | When to use it |
|---|---|
| **ProRes 4444** | Default. Real alpha channel, great quality, sane file size. |
| **ProRes 4444 XQ** | Maximum quality. Noticeably bigger files; you rarely need it for text. |
| **QuickTime Animation** | Mathematically lossless. Very large files, but universally compatible. |
| **PNG sequence** | No ffmpeg required. A folder of numbered transparent frames. |

---

## Notes

- **Preview quality** in the top bar defaults to *Full*, which is pixel-identical
  to the export. Drop it to *Fast* only if scrubbing stutters on long lines —
  export is always rendered at full quality regardless.
- Export speed is roughly 5–20 frames/sec at 1080p depending on the effects.
  The flag wave is the expensive one, since it redraws the text column by column.
- Everything runs locally on your machine. Nothing is uploaded anywhere.
- **Right-click** a colour swatch to remove it.

## If something breaks

**"Python isn't installed"** — install from python.org and make sure you tick
*Add python.exe to PATH* during setup.

**Fonts all look like Impact** — the app couldn't reach Google Fonts. Run
`python download_fonts.py` once, then reload.

**Export button does nothing** — check the black console window for an error,
and confirm the Format dropdown isn't stuck on a greyed-out option.

**Text is cut off at the edges** — lower **Wrap width** in Text & Layout, or
reduce the font size.
