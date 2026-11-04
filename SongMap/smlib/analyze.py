"""One song: mix.wav + lyrics.json -> grid, sections, changes, rhymes -> sheet text + JSON."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from . import changes as C
from . import features as F
from . import rhyme as R
from . import sections as S
from . import sheet as SH
from .grid import Grid

VERSION = "1.0"


def load_mix(path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return y.mean(axis=1), int(sr)


def lyric_lines(lyr: dict | None) -> list[dict]:
    out = []
    for ln in (lyr or {}).get("lines", []):
        ws = [w for w in ln.get("words", []) if str(w.get("t", "")).strip()]
        if not ws:
            continue
        text = " ".join(str(w["t"]).strip() for w in ws)
        out.append({"s": float(ws[0]["s"]), "e": float(ws[-1]["e"]), "text": " ".join(text.split()),
                    "words": [{"t": str(w["t"]).strip(), "s": float(w["s"]), "e": float(w["e"])} for w in ws]})
    out.sort(key=lambda l: l["s"])
    return out


def run(mix: Path, lyr: dict | None, meta: dict, models, fps: int = 60, lyrics_note: str = "") -> tuple[str, dict, str]:
    """Returns (sheet text, sheet data, one-line summary)."""
    T = {}
    t0 = time.time()
    mono, sr = load_mix(mix)
    dur = len(mono) / sr
    lines = lyric_lines(lyr)

    t = time.time()
    beats, downs = models.beats(mono, sr)
    T["beats"] = time.time() - t
    g = Grid(beats, downs, dur, fps)

    t = time.time()
    raw, sec_src = [], "SongFormer"
    try:
        raw = S.clean_raw(models.sections(mono, sr), dur)
    except Exception as e:  # noqa: BLE001
        sec_src = f"fallback from lyrics + energy (SongFormer failed: {str(e)[:120]})"
    T["sections"] = time.time() - t

    # one-drop check: do SongFormer's section starts sit on bar starts, or half a bar off?
    check = "no check (needs 3+ section changes from SongFormer)"
    if raw:
        ck = g.check(S.anchors(raw))
        if ck:
            if ck["half"] >= ck["now"] + 2 and ck["half"] >= 0.6 * ck["n"]:
                g.shift(ck["k"])
                check = (f"FIXED bar grid moved {ck['k']} beats: the tracker had heard beat 3 as 'one' (one-drop); "
                         f"now {ck['half']}/{ck['n']} section starts land on a bar start")
            elif ck["now"] >= 0.5 * ck["n"]:
                check = f"OK {ck['now']}/{ck['n']} section starts land on a bar start"
            else:
                check = (f"LOOSE only {ck['now']}/{ck['n']} section starts land on a bar start "
                         f"({ck['half']}/{ck['n']} half a bar later) - trust times over bar numbers")

    t = time.time()
    feat = F.levels(mono, sr, g, lines)
    events = C.detect(g, feat, lines)
    segs = raw if raw else S.fallback(g, lines, events)
    secs = S.finalize(segs, g, feat, lines)
    cues = C.cues(events, secs, g)
    rh = R.analyze(lines, (lyr or {}).get("language", "English"))
    T["analysis"] = time.time() - t
    T["total"] = time.time() - t0 + meta.get("lyrics_seconds", 0.0)

    meta = dict(meta)
    meta["version"] = VERSION
    meta["sections_src"] = sec_src
    meta["seconds"] = T["total"]
    meta["timing"] = (f"lyrics {meta.get('lyrics_seconds', 0):.0f}s, beats {T['beats']:.0f}s, "
                      f"sections {T['sections']:.0f}s, analysis {T['analysis']:.0f}s")
    if not lines:
        meta["lyrics_src"] = "none" + (f" ({lyrics_note})" if lyrics_note else "")
    txt = SH.text(meta, g, secs, events, cues, lines, rh, check)
    js = SH.data(meta, g, secs, events, cues, lines, rh, check)
    summary = (f"{g.bpm:.1f} BPM {g.bpb}/bar {len(g.down)} bars | {len(secs)} sections | {len(lines)} lyric lines"
               + ("" if sec_src == "SongFormer" else " | sections FALLBACK") + ("" if lines else " | NO LYRICS")
               + (" | grid FIXED" if check.startswith("FIXED") else (" | grid LOOSE" if check.startswith("LOOSE") else "")))
    return txt, js, summary


def write(out_dir: Path, stem: str, txt: str, js: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{stem}.songmap.txt"
    p.write_text(txt, encoding="utf-8")
    (out_dir / f"{stem}.songmap.json").write_text(json.dumps(js, separators=(",", ":")), encoding="utf-8")
    return p
