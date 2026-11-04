"""ramp.py - smooth speed ramps for FilmCraft (Justice 2026-10-25).

AI keyframe clips ease into their pinned last frame and ease out of their first one, so a chain of them
plays slow-down ... lurch ... slow-down at every join. ramp measures how fast each clip moves (cheap:
ffmpeg decodes it at 128x72 and this file compares the frames; cached next to the cut list), then builds a
smooth speed curve that evens the motion out: stalls play faster, rushes play slower, with gradual slopes
like Premiere's speed-ramp handles. It speeds up the stalls (up to 3x) and only eases the fastest rush a
little, so a clip comes out a bit shorter - the dead time is gone - and keeps its first and last frames.

fc.py turns the curve into short constant-speed pieces on the timeline with frame blending (FilmCraft 0.10
stores Time Remapping keyframes but does not render them - tested 2026-10-25), so every piece stays
editable in FilmCraft with Speed/Duration.

  python ramp.py <video> [more videos]      print the motion line and the planned speeds (no changes)
"""
import array, json, math, os, subprocess, sys
from operator import sub

W, H, LAG = 128, 72, 2
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BARS = " .:-=+*#%@"

# defaults: ramps run on EVERY build and keep each clip's cut length (cut list: `ramp off`, `ramp 0.6` = strength,
# `ramp free` = old behaviour that lets clips get shorter)
STRENGTH = 0.85     # 1 = make motion fully even, 0 = leave as rendered
LO, HI = 0.85, 3.0  # slowest / fastest playback the ramp may use
TARGET = 0.6        # motion level the stalls are brought up to (share of the clip that moves slower)
SLOPE = 0.35        # seconds: how gradual the speed changes are (Gaussian sigma on the curve)
PIECE = 0.25        # seconds per constant-speed piece on the timeline
EVEN = 1.12         # leave a clip alone if no part needs more than +-12 %


def ffmpeg():
    p = os.environ.get("FFMPEG")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    d = r"A:\ClaudeComfy\venv\Lib\site-packages\imageio_ffmpeg\binaries"
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().startswith("ffmpeg") and f.lower().endswith(".exe"):
                return os.path.join(d, f)
    return "ffmpeg"


def _grad(f):
    return sum(map(abs, map(sub, f[1:], f[:-1]))) + sum(map(abs, map(sub, f[W:], f[:-W])))


def motion(path, cache=None):
    """Per-frame motion of the whole file (about pixels per frame at 128x72). Cached by size+mtime."""
    st = os.stat(path)
    key = [st.st_size, int(st.st_mtime)]
    cf = None
    if cache:
        os.makedirs(cache, exist_ok=True)
        cf = os.path.join(cache, os.path.basename(path) + ".motion.json")
        try:
            with open(cf) as fh:
                d = json.load(fh)
            if d.get("key") == key:
                return d["m"]
        except (OSError, ValueError):
            pass
    cmd = [ffmpeg(), "-v", "error", "-i", path, "-an", "-sn", "-vf",
           "scale=%d:%d:flags=area,format=gray16le" % (W, H), "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True, creationflags=NOWIN)
    if r.returncode:
        raise RuntimeError("ffmpeg: " + r.stderr.decode(errors="replace")[-300:])
    raw, F = r.stdout, W * H * 2
    n = len(raw) // F
    if n < LAG + 2:
        raise RuntimeError("too few frames in " + path)
    try:
        import numpy as np
        a = np.frombuffer(raw[:n * F], dtype="<u2").reshape(n, H, W).astype(np.float32)
        g = (np.abs(np.diff(a, axis=2)).sum((1, 2)) + np.abs(np.diff(a, axis=1)).sum((1, 2))).tolist()
        d = np.abs(a[LAG:] - a[:-LAG]).sum((1, 2)).tolist()
    except ImportError:
        fr = [array.array("H", raw[i * F:(i + 1) * F]) for i in range(n)]
        if sys.byteorder != "little":
            for f in fr:
                f.byteswap()
        step, gk = 6, {}
        for i in list(range(0, n, step)) + [n - 1]:
            gk[i] = _grad(fr[i])
        g = []
        for i in range(n):
            i0 = (i // step) * step
            i1 = min(i0 + step, n - 1)
            t = 0 if i1 == i0 else (i - i0) / (i1 - i0)
            g.append(gk[i0] * (1 - t) + gk[i1] * t)
        d = [sum(map(abs, map(sub, fr[i], fr[i - LAG]))) for i in range(LAG, n)]
    # change between frames i-1 and i+1, divided by the picture's own detail = how far it moved
    m = []
    for i in range(n):
        k = min(max(i - 1, 0), len(d) - 1)
        m.append(round(d[k] / max(g[i], 1.0) / LAG * 1000, 3))
    if cf:
        with open(cf, "w") as fh:
            json.dump({"key": key, "m": m}, fh)
    return m


def gauss(x, sigma):
    if sigma < 0.5:
        return list(x)
    r = int(3 * sigma)
    k = [math.exp(-0.5 * (i / sigma) ** 2) for i in range(-r, r + 1)]
    n, out = len(x), []
    for i in range(n):
        s = w = 0.0
        for j, kv in enumerate(k):
            t = min(max(i + j - r, 0), n - 1)   # hold the edge value
            s += x[t] * kv
            w += kv
        out.append(s / w)
    return out


def curve(m, fps, a=0.0, b=None, strength=STRENGTH, overrides=()):
    """Speed for every source frame of [a, b] seconds (1 = as rendered).
    overrides: [(a, b, speed)] in clip seconds, Justice's own fixes; they win over the auto curve.
    Returns the speeds, or None when the clip is already even."""
    i0 = int(round(a * fps))
    i1 = len(m) if b is None else min(len(m), int(round(b * fps)))
    n = i1 - i0
    if n < fps:
        return None
    x = gauss(m[i0:i1], 0.10 * fps)
    ref = sorted(x)[int(n * TARGET)]
    r = [1.0] * n
    if strength > 0 and ref > 0:
        floor = 0.05 * ref
        r = [min(HI, max(LO, (ref / max(v, floor)) ** strength)) for v in x]
    for oa, ob, sp in overrides:
        for i in range(max(0, int(oa * fps) - i0), min(n, int(ob * fps) - i0)):
            r[i] = sp
    r = [math.exp(v) for v in gauss([math.log(v) for v in r], SLOPE * fps)]
    if not overrides and max(abs(math.log(v)) for v in r) < math.log(EVEN):
        return None
    return r


def keep_length(r):
    """Same curve, same total length (Justice 2026-10-27): stalls still play faster and rushes slower, but the clip
    keeps exactly its cut length on the timeline, so cuts placed on SongMap's beats stay on the beat."""
    if not r:
        return r
    k = sum(1.0 / v for v in r) / len(r)
    return [v * k for v in r]


def pieces(r, fps, head=0, tail=0):
    """Speed curve -> [(src_start, src_frames, timeline_frames, speed)], source in (fractional) frames,
    timeline in whole frames. head/tail: minimum length of the first/last piece (transitions sit there)."""
    n = len(r)
    T = [0.0]
    for v in r:
        T.append(T[-1] + 1.0 / v)
    total = int(round(T[-1]))
    seg = max(2, int(round(PIECE * fps)))
    bounds = [0]
    t = max(seg, head)
    while t < total - max(tail, seg // 2):
        bounds.append(t)
        t += seg
    bounds.append(total)

    def src_at(tt):
        tt = tt * T[-1] / total
        lo_, hi_ = 0, n
        while hi_ - lo_ > 1:
            mid = (lo_ + hi_) // 2
            if T[mid] <= tt:
                lo_ = mid
            else:
                hi_ = mid
        span = T[lo_ + 1] - T[lo_]
        return lo_ + ((tt - T[lo_]) / span if span else 0)

    S = [src_at(b_) for b_ in bounds]
    S[0], S[-1] = 0.0, float(n)
    out = []
    for k in range(len(bounds) - 1):
        src, tl = S[k + 1] - S[k], bounds[k + 1] - bounds[k]
        if out and abs(out[-1][1] / out[-1][2] / (src / tl) - 1) < 0.025:   # same speed: one piece
            p = out.pop()
            out.append((p[0], p[1] + src, p[2] + tl, 0))
        else:
            out.append((S[k], src, tl, 0))
    return [(s0, sn, tl, sn / tl) for s0, sn, tl, _ in out]


def spark(v, width=48):
    if not v:
        return ""
    n = len(v)
    cols = [sum(v[i * n // width:max(i * n // width + 1, (i + 1) * n // width)]) /
            max(1, max(i * n // width + 1, (i + 1) * n // width) - i * n // width) for i in range(width)]
    med = sorted(cols)[width // 2] or 1
    return "".join(BARS[min(len(BARS) - 1, int(c / med * 4.5))] for c in cols)


def describe(m, r, fps):
    """One-line before/after for the report: motion line as rendered, and after the ramp."""
    if r is None:
        return "even       |%s|" % spark(m)
    pos, T = [], 0.0
    for v in r:
        pos.append(T)
        T += 1.0 / v
    w = 48
    cols = [[] for _ in range(w)]
    for i, p_ in enumerate(pos):       # motion per timeline frame after the ramp
        cols[min(w - 1, int(p_ / T * w))].append(m[i] * r[i])
    after = [sum(c) / len(c) if c else 0 for c in cols]
    return "%.2f-%.2fx len %.0f%% |%s| -> |%s|" % (min(r), max(r), 100 * T / len(r), spark(m[:len(r)]), spark(after, w))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        mm = motion(p)
        fps = 60.0
        rr = curve(mm, fps)
        print(os.path.basename(p), describe(mm, rr, fps))
        if rr:
            print("   pieces:", " ".join("%.0f%%/%d" % (sp * 100, tl) for _, _, tl, sp in pieces(rr, fps, 30, 30)))
