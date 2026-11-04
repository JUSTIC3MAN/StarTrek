#!/usr/bin/env python3
"""song_cut.py - FilmCraft cut list from a song plan (projects/<song>/<song>.plan.json), Justice 2026-10-27.

  python song_cut.py <song> [--partial]
The plan (written by song_jobs.py from <song>.shots.txt) lists every shot in timeline order:
  {"t", "e", "run", "slot", "off", "tr", "label"}  one shot of a Comfort "H3 Reference Video" run
                                                  (3 shots of 5 s: slot 0/1/2, used from the plan's inpoint (#inpoint, default 0.4 s) + off)
  {"t", "e", "clip", "a", "tr", "label"}         a finished clip from its second a
Each shot plays from song time t to e, so every cut lands where the plan put it (SongMap bars). A shot longer
than its 4.6 s of video is slowed to fit (speed line). --partial stops before the first shot whose video isn't
rendered yet. fc.py build reruns this (partial) for any cut list whose first line says 'built by song_cut.py',
so a queued build always uses every shot rendered so far. Ramps run by default in fc.py (lengths kept)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def write(pdir, song, partial=False):
    import fc
    plan = json.load(open(os.path.join(pdir, song + ".plan.json"), encoding="utf-8"))
    V = plan["videos"]
    try:                                        # the overseer's verdicts: best take, in- and out-point of each shot
        use = json.load(open(os.path.join(pdir, "_review.json"), encoding="utf-8")).get("use", {})
    except Exception:
        use = {}
    lines = [f"# built by song_cut.py from {song}.plan.json - edit {song}.shots.txt and rerun song_jobs.py, not this file",
             f"out {plan['out']}", "size 1920x1080@60", f"fadein {plan.get('fadein', 24)}",
             "clipaudio off", "musicfull " + ("on" if plan.get("musicfull", True) else "off")]            # only the song is heard; the whole song sits in the project
    def place(s, ln):                            # -> (dict, None) or (None, why not)
        sp = None
        if "clip" in s:
            src, a = V + "\\" + s["clip"], float(s.get("a", 0))
            b, key = a + ln, (s["clip"], round(a))
        else:
            u = use.get(f"{s['run']}:{s['slot']}") or {}
            if use and not u:                     # the overseer has not passed this shot (or rejected it): never place it
                return None, f"{s['run']}:{s['slot']} (not passed yet)"
            run, slot = u.get("run", s["run"]), u.get("slot", s["slot"])
            src, key = V + "\\" + run + "_stage60.mp4", (run, slot)
            lo, hi = 5 * slot + float(u.get("in", plan.get("inpoint", 0.4))), 5 * slot + min(float(u.get("out", 4.98)), 99.0 if u.get("one") else float(plan.get("tail", 4.98)))   # #tail cuts H3's slow stop; the rest is slowed to fit
            a = lo + float(s.get("off", 0))
            if a + ln > hi:
                a = max(lo, hi - ln)
            b = a + ln
            if b > hi + 1e-6:                       # longer than the rendered shot: slow it to fit
                b, sp = hi, (hi - a) / ln
        if not os.path.exists(fc.to_local(src)):
            return None, os.path.basename(src)
        return {"src": src, "a": a, "b": b, "sp": sp, "key": key}, None

    # NO REPEATS (Justice 2026-10-27, README rule 3): a source is placed once per edit. A shot that is not ready (or would
    # repeat another) is never covered by another shot: the shot before it holds longer (slowed) while it renders.
    used, segs, missing, held = set(), [], "", 0
    for s in plan["shots"]:
        r, why = place(s, s["e"] - s["t"])
        if r and r["key"] in used:
            r, why = None, f"{s['label']} would repeat a shot already in the edit"
        if r:
            used.add(r["key"])
            segs.append({"s": s, "t": s["t"], "e": s["e"]})
            continue
        if not partial:
            sys.exit(f"{s['label']}: {why} (use --partial)")
        if segs and s["e"] - segs[-1]["t"] <= 7.6:  # hold the shot before it (at most ~7.5 s on screen)
            segs[-1]["e"], held = s["e"], held + 1
            continue
        missing = why
        break
    end, n, slowed = 0.0, 0, 0
    for g in segs:
        s, ln = g["s"], round(g["e"] - g["t"], 3)
        r, _ = place(s, ln)
        W = plan.get("within") or []                # #within: the transition family for cuts inside a scene
        tr = s.get("tr") or (W[n % len(W)] if W else "")
        if tr and n:
            lines.append(f"> {tr}")
        nr = " noramp" if ("clip" in s and ln > 30) else ""     # a finished edit (over 30 s) keeps its own timing: no ramp
        lines.append(f"clip {r['src']} {r['a']:.3f}-{r['b']:.3f}{nr}   # {s.get('label', '')} @{g['t']:.2f}" + ("  (holding for the next shot)" if g["e"] != s["e"] else ""))
        if r["sp"]:
            lines.append(f"speed {r['a']:.3f}-{r['b']:.3f} {r['sp'] * 100:.1f}")
            slowed += 1
        lines += s.get("text", [])                  # titles over this clip (shots.txt: text <label> ...)
        end, n = g["e"], n + 1
    lines += [f"fadeout {plan.get('fadeout', 60)}", f"music {plan['music']}"]
    lines += [f"copy {c}" for c in plan.get("copy", [])]
    open(os.path.join(pdir, song + ".txt"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    return (f"song_cut {song}: {n} shots to {end:.2f}s of {plan['shots'][-1]['e']:.2f}s"
            + (f", {slowed} slowed" if slowed else "") + (f", {held} not ready (held by the shot before)" if held else "")
            + (f" (next: {missing})" if missing else ""))


def copy_pictures(pdir, song):
    """Windows builds only: every new picture of the plan into the song's Preview folder as <label>.png (once)."""
    import re, shutil
    plan = json.load(open(os.path.join(pdir, song + ".plan.json"), encoding="utf-8"))
    dest, n = plan.get("pic_copy"), 0
    if not dest or os.name != "nt":
        return ""
    os.makedirs(dest, exist_ok=True)
    for d in plan.get("pic_dirs", []):
        if os.path.isdir(d):
            for f in os.listdir(d):
                t = os.path.join(dest, re.sub(r"^\d+-\d+_", "", f))
                if f.endswith(".png") and not os.path.exists(t):
                    shutil.copyfile(os.path.join(d, f), t)
                    n += 1
    return f" | {n} new pictures to Preview" if n else ""


if __name__ == "__main__":
    song = sys.argv[1]
    print(write(os.path.join(HERE, "projects", song), song, "--partial" in sys.argv))
