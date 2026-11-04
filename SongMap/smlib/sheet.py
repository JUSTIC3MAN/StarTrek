"""The SongMap sheet: one compact text file per song for planning a FilmCraft edit, plus a JSON twin."""
from __future__ import annotations

import time

from . import rhyme as R
from .sections import of_time


def clock(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 60)}:{t % 60:05.2f}"


def _w(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 2] + ".."


def text(meta: dict, g, sections: list[dict], events: list[dict], cues: list[dict], lines: list[dict],
         rh: dict, check: str) -> str:
    fps = g.fps
    o: list[str] = []
    title = meta["title"] + (f" - {meta['artist']}" if meta.get("artist") else "")
    o.append(f"SONGMAP {meta['version']} | {title} | {clock(g.duration)} | made {time.strftime('%Y-%m-%d %H:%M')} "
             f"in {meta['seconds']:.0f}s")
    steady = (f"steady {g.bpm_lo:.1f}-{g.bpm_hi:.1f}" if g.bpm_hi - g.bpm_lo < 3
              else f"DRIFTS {g.bpm_lo:.1f}-{g.bpm_hi:.1f}")
    o.append(f"TEMPO {g.bpm:.1f} BPM ({steady}; half-time {g.bpm / 2:.1f}, double {g.bpm * 2:.1f}) | {g.bpb} beats/bar | "
             f"{len(g.down)} bars | bar 1 at {clock(g.bar_starts[0])}")
    o.append(f"FRAMES @{fps}: beat {g.frames():.1f} | half beat {g.frames(0.5):.1f} | bar {g.frames(g.bpb):.1f} | "
             f"2 bars {g.frames(2 * g.bpb):.1f}")
    o.append(f"SOURCES lyrics: {meta['lyrics_src']} | sections: {meta['sections_src']} | beats: Beat This! | "
             f"changes: full-mix levels | rhyme: approximate ({rh['rate'] * 100:.0f}% of line ends rhyme)")
    o.append(f"CHECK {check}")
    o.append("USE times = song seconds = FilmCraft timeline seconds when the song sits at 0:00 (cut list 'music' line). "
             "bar.beat counts from 1. Cut on a bar start for a clean change; transitions fit a beat or half beat.")
    o.append("")
    o.append("SECTIONS")
    o.append("  start     end       bars     name           energy  vocal  rhyme")
    for s in sections:
        il = [i for i, l in enumerate(lines) if s["start"] - 0.3 <= l["s"] < s["end"] - 0.3]
        sch = R.scheme([rh["letters"][i] for i in il]) if il else ""
        o.append(f"  {clock(s['start']):9} {clock(s['end']):9} {s['bar_from']:>3}-{s['bar_to']:<4} "
                 f"{_w(s['name'], 14):14} {s['energy']:7} {s['vocal']:6} {sch}")
    o.append("")
    o.append("CUE POINTS (*** = strongest place for a cut or a big transition)")
    for c in cues:
        o.append(f"  {clock(c['t']):9} {g.label(c['t']):>6}  {'*' * c['strength']:3}  {_w(c['text'], 80)}")
    o.append("")
    o.append("TIMELINE (time  bar.beat  lyric line  [rhyme letter]  internal rhymes;  >> = musical change)")
    items = [("l", l["s"], i) for i, l in enumerate(lines)] + \
            [("e", e["t"], k) for k, e in enumerate(events) if e["kind"] not in ("vocal_in",)]
    items.sort(key=lambda x: (x[1], 0 if x[0] == "e" else 1))
    cur = -1
    for kind, t, i in items:
        si = of_time(sections, t)
        while cur < si:
            cur += 1
            s = sections[cur]
            o.append(f"== {s['name'].upper()}  {clock(s['start'])}-{clock(s['end'])}  bars {s['bar_from']}-{s['bar_to']}"
                     f"  {s['energy']} energy ==")
        if kind == "l":
            l = lines[i]
            let = rh["letters"][i]
            intl = ("  int: " + ", ".join(rh["internal"][i])) if rh["internal"][i] else ""
            o.append(f"  {clock(t):9} {g.label(t):>6}  {_w(l['text'], 62)}" + (f"  [{let}]" if let else "") + intl)
        else:
            e = events[i]
            o.append(f"  {clock(t):9} {g.label(t):>6}  >> {e['text']}")
    while cur < len(sections) - 1:
        cur += 1
        s = sections[cur]
        o.append(f"== {s['name'].upper()}  {clock(s['start'])}-{clock(s['end'])}  bars {s['bar_from']}-{s['bar_to']}"
                 f"  {s['energy']} energy ==")
    o.append(f"  {clock(g.duration):9}         END")
    o.append("")
    o.append("BAR STARTS (bar=seconds)")
    bs = g.bar_starts
    row: list[str] = []
    for n, t in enumerate(bs, 1):
        row.append(f"{n}={t:.2f}")
        if len(row) == 10:
            o.append("  " + "  ".join(row))
            row = []
    if row:
        o.append("  " + "  ".join(row))
    o.append("")
    o.append(f"TIMING {meta['timing']}")
    o.append("Every beat and word time: the .songmap.json beside this file (read it only when snapping exact cuts).")
    return "\n".join(o) + "\n"


def data(meta: dict, g, sections, events, cues, lines, rh, check: str) -> dict:
    return {
        "version": meta["version"], "title": meta["title"], "artist": meta.get("artist", ""),
        "duration": round(g.duration, 3), "bpm": round(g.bpm, 2), "beats_per_bar": g.bpb, "fps": g.fps,
        "frames_per_beat": round(g.frames(), 2), "check": check, "sources": {k: meta[k] for k in ("lyrics_src", "sections_src")},
        "beats": [round(float(b), 3) for b in g.beats], "bar_starts": [round(t, 3) for t in g.bar_starts],
        "sections": sections, "events": events, "cues": cues,
        "lines": [{"start": round(l["s"], 3), "end": round(l["e"], 3), "pos": g.label(l["s"]), "text": l["text"],
                   "rhyme": rh["letters"][i], "internal": rh["internal"][i],
                   "words": [{"t": w["t"], "s": round(w["s"], 3), "e": round(w["e"], 3)} for w in l["words"]]}
                  for i, l in enumerate(lines)],
        "timing": meta["timing"],
    }
