"""Song sections: SongFormer's segments (or a lyric/energy fallback), snapped to bars, numbered and described."""
from __future__ import annotations

import re

import numpy as np

from .features import energy_word, pmean_db

NAMES = {"pre-chorus": "pre-chorus", "prechorus": "pre-chorus", "inst": "inst", "instrumental": "inst"}


def clean_raw(raw: list[dict], duration: float) -> list[dict]:
    segs = []
    for s in raw:
        a, e = float(s["start"]), min(float(s["end"]), duration)
        lab = NAMES.get(str(s["label"]).lower(), str(s["label"]).lower())
        if lab == "end" or e - a < 0.05:
            continue
        segs.append({"start": a, "end": e, "label": lab})
    # short silences fold into the neighbour
    out = []
    for s in segs:
        if s["label"] == "silence" and s["end"] - s["start"] < 1.5 and out:
            out[-1]["end"] = s["end"]
            continue
        out.append(s)
    if out and out[0]["label"] == "silence" and out[0]["end"] - out[0]["start"] < 1.5 and len(out) > 1:
        out[1]["start"] = 0.0
        out = out[1:]
    return out


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9áéíóúñü ]+", "", t.lower()).strip()


def fallback(grid, lines: list[dict], events: list[dict]) -> list[dict]:
    """No SongFormer: vocal blocks become sections; repeated lyrics = chorus."""
    bar_s = grid.bpb * grid.period
    blocks: list[list[dict]] = []
    for ln in lines:
        if blocks and ln["s"] - blocks[-1][-1]["e"] < 1.5 * bar_s:
            blocks[-1].append(ln)
        else:
            blocks.append([ln])
    if not blocks:
        cuts = [0.0] + [e["t"] for e in events if e["kind"] in ("drop", "lift", "stop") and e["strength"] >= 2]
        cuts = sorted({grid.snap(t) for t in cuts})
        return [{"start": a, "end": b, "label": "part"} for a, b in zip(cuts, cuts[1:] + [grid.duration]) if b - a > bar_s]
    texts = [{_norm(l["text"]) for l in b} for b in blocks]
    rep = [any(i != j and len(texts[i] & texts[j]) >= 0.5 * max(1, len(texts[i])) for j in range(len(blocks)))
           for i in range(len(blocks))]
    segs = []
    if blocks[0][0]["s"] > bar_s:
        segs.append({"start": 0.0, "end": blocks[0][0]["s"], "label": "intro"})
    for k, b in enumerate(blocks):
        a, e = b[0]["s"], b[-1]["e"]
        segs.append({"start": a, "end": e, "label": "chorus" if rep[k] else "verse"})
        nxt = blocks[k + 1][0]["s"] if k + 1 < len(blocks) else grid.duration
        if nxt - e >= 2 * bar_s:
            segs.append({"start": e, "end": nxt, "label": "outro" if k + 1 == len(blocks) else "inst"})
    return segs


def finalize(segs: list[dict], grid, feat: dict, lines: list[dict]) -> list[dict]:
    if not segs:
        segs = [{"start": 0.0, "end": grid.duration, "label": "song"}]
    starts = [0.0] + [grid.snap(s["start"]) for s in segs[1:]]
    out = []
    for s, a, b in zip(segs, starts, starts[1:] + [grid.duration]):
        if b - a < 0.5 * grid.period:
            continue
        out.append({"label": s["label"], "start": round(a, 3), "end": round(b, 3)})
    # merge neighbours that ended up with the same label and touch after snapping, if one is tiny
    merged: list[dict] = []
    for s in out:
        if merged and merged[-1]["label"] == s["label"] and s["end"] - s["start"] < 2 * grid.bpb * grid.period:
            merged[-1]["end"] = s["end"]
        else:
            merged.append(s)
    counts: dict[str, int] = {}
    total = {s["label"]: sum(1 for x in merged if x["label"] == s["label"]) for s in merged}
    bars = feat["bars"]
    for s in merged:
        counts[s["label"]] = counts.get(s["label"], 0) + 1
        s["name"] = s["label"] if total[s["label"]] == 1 else f"{s['label']} {counts[s['label']]}"
        s["bar_from"] = max(1, grid.bar_of(s["start"] + 0.01)) if s["start"] > 0.01 else max(0, grid.bar_of(0.0))
        s["bar_to"] = grid.bar_of(max(s["start"], s["end"] - 0.05))
        inside = [b for b in bars if s["start"] - 0.01 <= b["t"] < s["end"] - 0.01]
        db = pmean_db(b["rms"] for b in inside) if inside else -60.0
        s["energy"] = energy_word(db, feat["q"])
        s["db"] = round(db, 1)
        dur = max(s["end"] - s["start"], 1e-3)
        cov = sum(max(0.0, min(s["end"], l["e"]) - max(s["start"], l["s"])) for l in lines)
        s["vocal"] = "yes" if cov / dur >= 0.15 else ("some" if cov > 0 else "-")
    return merged


def anchors(raw: list[dict]) -> list[float]:
    return [float(s["start"]) for s in raw[1:]]


def of_time(sections: list[dict], t: float) -> int:
    for i, s in enumerate(sections):
        if s["start"] - 1e-3 <= t < s["end"]:
            return i
    return len(sections) - 1 if sections and t >= sections[-1]["start"] else 0
