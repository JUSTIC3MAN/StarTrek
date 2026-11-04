"""Musical changes from the full mix: stops, drops, lifts, builds, low end / percussion / highs in and out,
and vocal entries from the lyric timings. Each event: {t, kind, text, strength 1-3}."""
from __future__ import annotations

import numpy as np

from .features import pmean_db


def detect(grid, feat: dict, lines: list[dict]) -> list[dict]:
    ev: list[dict] = []
    bpb = grid.bpb
    br = feat["beat"]["rms"]
    n = len(br)

    # ---- stops / quiet stretches (beat level) -------------------------------------------------
    quiet = br < feat["med_beat"] - 18.0
    loud = np.where(~quiet)[0]
    if loud.size:
        first, last = int(loud[0]), int(loud[-1])
        i = first
        while i <= last:
            if quiet[i]:
                j = i
                while j <= last and quiet[j]:
                    j += 1
                L = j - i
                t = float(grid.beats[i])
                if L <= 2 * bpb:
                    ev.append({"t": t, "kind": "stop", "strength": 3,
                               "text": f"STOP {L} beat{'s' if L > 1 else ''}, back in at {grid.label(float(grid.beats[min(j, n - 1)]))}"})
                else:
                    ev.append({"t": t, "kind": "quiet", "strength": 2, "text": f"near silence {L / bpb:.0f} bars"})
                i = j
            else:
                i += 1

    # ---- bar-level changes ---------------------------------------------------------------------
    bars = feat["bars"]
    last_bar = {}
    for i in range(2, len(bars)):
        p = bars[i - 2:i]
        cur = bars[i]
        nxt = bars[i + 1] if i + 1 < len(bars) else cur
        prms, plow, phigh = pmean_db(b["rms"] for b in p), pmean_db(b["low"] for b in p), pmean_db(b["high"] for b in p)
        pon = float(np.mean([b["onset"] for b in p]))
        d, dn = cur["rms"] - prms, nxt["rms"] - prms
        dl, dln = cur["low"] - plow, nxt["low"] - plow
        dh, dhn = cur["high"] - phigh, nxt["high"] - phigh
        ro = cur["onset"] / max(pon, 1e-6)
        ron = nxt["onset"] / max(pon, 1e-6)

        def held(a: float, b: float) -> bool:          # the change lasts into the next bar
            return np.sign(a) == np.sign(b) and abs(b) >= 0.5 * abs(a)

        parts, kinds, s = [], [], 1
        if abs(d) >= 6 and held(d, dn):
            kinds.append("drop" if d < 0 else "lift")
            parts.append(f"{'DROP' if d < 0 else 'LIFT'} {d:+.0f} dB")
            s = 3 if abs(d) >= 9 else 2
        if abs(dl) >= 10 and held(dl, dln):
            kinds.append("low")
            parts.append("low end out" if dl < 0 else "low end in")
            s = max(s, 2)
        if (ro <= 0.5 and ron <= 0.7) or (ro >= 2.0 and ron >= 1.4):
            kinds.append("perc")
            parts.append("percussion thins out" if ro < 1 else "percussion kicks in")
            s = max(s, 2)
        if abs(dh) >= 10 and held(dh, dhn):
            kinds.append("high")
            parts.append("highs out" if dh < 0 else "highs in")
        if not parts:
            continue
        if all(last_bar.get(k, -9) >= i - 2 for k in kinds):      # same change already reported
            continue
        for k in kinds:
            last_bar[k] = i
        ev.append({"t": cur["t"], "kind": kinds[0], "strength": s, "text": ", ".join(parts)})

    # ---- builds: 4+ bars rising, at least +5 dB ----------------------------------------------
    r = [b["rms"] for b in bars]
    i = 0
    while i < len(r) - 3:
        j = i
        while j + 1 < len(r) and r[j + 1] >= r[j] - 0.5:
            j += 1
        if j - i >= 3 and r[j] - r[i] >= 5:
            ev.append({"t": bars[i]["t"], "kind": "build", "strength": 2,
                       "text": f"BUILD bars {bars[i]['n']}-{bars[j]['n']} ({r[j] - r[i]:+.0f} dB), peaks at {bars[j]['n']}.1"})
            i = j
        i += 1

    # ---- vocal in / out ---------------------------------------------------------------------
    bar_s = grid.bpb * grid.period
    if lines:
        ev.append({"t": lines[0]["s"], "kind": "vocal_in", "strength": 2, "text": "vocal in"})
        for a, b in zip(lines[:-1], lines[1:]):
            gap = b["s"] - a["e"]
            if gap >= 2 * bar_s:
                ev.append({"t": a["e"], "kind": "vocal_out", "strength": 1, "text": f"vocal out ({gap / bar_s:.0f} bars)"})
                ev.append({"t": b["s"], "kind": "vocal_in", "strength": 2, "text": "vocal in"})
        ev.append({"t": lines[-1]["e"], "kind": "vocal_out", "strength": 1, "text": "last vocal"})

    ev.sort(key=lambda e: e["t"])
    return ev


def cues(events: list[dict], sections: list[dict], grid, limit: int = 20) -> list[dict]:
    """Shortlist of the best cut / transition moments, in time order."""
    c = [{"t": s["start"], "strength": 3, "text": f"{s['name']} starts"} for s in sections[1:]]
    c += [{"t": e["t"], "strength": e["strength"], "text": e["text"]} for e in events
          if e["strength"] >= 2 and e["kind"] != "vocal_out"]
    c.sort(key=lambda x: x["t"])
    merged: list[dict] = []
    for x in c:
        if merged and x["t"] - merged[-1]["t"] <= grid.period * 1.01:
            m = merged[-1]
            m["strength"] = max(m["strength"], x["strength"])
            if x["text"] not in m["text"]:
                m["text"] += "; " + x["text"]
        else:
            merged.append(dict(x))
    if len(merged) > limit:
        keep = sorted(sorted(merged, key=lambda x: -x["strength"])[:limit], key=lambda x: x["t"])
        merged = keep
    return merged
