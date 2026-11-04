"""Beat grid: tempo, bars, bar.beat positions, and the one-drop downbeat check."""
from __future__ import annotations

import numpy as np


def _nearest(arr: np.ndarray, x: float) -> int:
    i = int(np.searchsorted(arr, x))
    if i <= 0:
        return 0
    if i >= len(arr):
        return len(arr) - 1
    return i if abs(arr[i] - x) < abs(arr[i - 1] - x) else i - 1


def clean_beats(b: np.ndarray) -> tuple[np.ndarray, int]:
    """Beat This! without its DBN step sometimes skips a beat or adds a stray one.
    Drop strays (keep the hit nearer the grid), fill skipped beats evenly. Returns (beats, changes)."""
    d = np.diff(b)
    P = float(np.median(d))
    out = [float(b[0])]
    fixes = 0
    for t in map(float, b[1:]):
        recent = np.diff(out[-9:])
        recent = recent[(recent > 0.7 * P) & (recent < 1.3 * P)]
        p = float(np.median(recent)) if recent.size >= 4 else P
        gap = t - out[-1]
        if gap < 0.55 * p:                              # stray hit
            fixes += 1
            if len(out) >= 2 and abs(t - (out[-2] + p)) < abs(out[-1] - (out[-2] + p)):
                out[-1] = t
            continue
        m = int(round(gap / p))
        if m >= 2 and abs(gap - m * p) < 0.3 * p:       # skipped beat(s)
            base = out[-1]
            out += [base + q * gap / m for q in range(1, m)]
            fixes += m - 1
        out.append(t)
    return np.asarray(out), fixes


class Grid:
    """beats: every beat time (s). down: beat indices that start a bar (bar 1 = down[0])."""

    def __init__(self, beats, downbeats, duration: float, fps: int = 60):
        b = np.unique(np.round(np.asarray(beats, dtype=float), 4))
        b = b[(b >= 0) & (b <= duration + 0.5)]
        if len(b) < 8:
            raise ValueError(f"only {len(b)} beats found - is this a song?")
        b, self.fixed_beats = clean_beats(b)
        self.beats = b
        self.duration = float(duration)
        self.fps = fps
        d = np.diff(b)
        self.period = float(np.median(d))
        self.bpm = 60.0 / self.period
        if len(d) >= 16:
            loc = [60.0 / float(np.median(d[i:i + 8])) for i in range(0, len(d) - 7, 4)]
            self.bpm_lo, self.bpm_hi = float(np.percentile(loc, 5)), float(np.percentile(loc, 95))
        else:
            self.bpm_lo = self.bpm_hi = self.bpm
        di = []
        for t in np.asarray(downbeats, dtype=float):
            j = _nearest(b, float(t))
            if abs(b[j] - t) < 0.5 * self.period and (not di or j != di[-1]):
                di.append(j)
        self.bpb = self._meter(di)
        self.down = self._regular(sorted(set(di)))
        self.notes: list[str] = []
        self.shifted = 0

    # ------------------------------------------------------------ setup --
    def _meter(self, di: list[int]) -> int:
        if len(di) < 3:
            return 4
        vals, counts = np.unique(np.diff(di), return_counts=True)
        m = int(vals[int(np.argmax(counts))])
        return m if 2 <= m <= 8 else 4

    def _regular(self, di: list[int]) -> list[int]:
        """Bar starts every bpb beats. Where the bar falls in the beat count (the phase) follows the
        majority of the nearby tracked downbeats, so one stray downbeat can't make a 3- or 5-beat bar;
        a phase change that the tracker keeps showing becomes one short bar."""
        n, k = len(self.beats), self.bpb
        if not di:
            return list(range(0, n, k))
        di = np.asarray(di)
        ph = di % k

        def phase(i: int) -> int:
            j = int(np.searchsorted(di, i))
            near = ph[max(0, j - 4):j + 4]
            vals, cnt = np.unique(near, return_counts=True)
            return int(vals[int(np.argmax(cnt))])

        out: list[int] = []
        for i in range(n):
            if i % k == phase(i) and (not out or i - out[-1] >= 2):
                out.append(i)
        return out or list(range(0, n, k))

    def shift(self, k: int) -> None:
        """Move every bar start by k beats (one-drop fix: the tracker called beat 3 'one')."""
        n = len(self.beats)
        d = [i + k for i in self.down if 0 <= i + k < n]
        while d and d[0] - self.bpb >= 0:
            d.insert(0, d[0] - self.bpb)
        self.down = d
        self.shifted += k

    # -------------------------------------------------------- positions --
    def beat_pos(self, t: float) -> float:
        """Fractional beat index of time t (0 = first beat)."""
        b = self.beats
        if t <= b[0]:
            return (t - b[0]) / self.period
        if t >= b[-1]:
            return len(b) - 1 + (t - b[-1]) / self.period
        i = int(np.searchsorted(b, t)) - 1
        return i + (t - b[i]) / (b[i + 1] - b[i])

    def bar_beat(self, t: float) -> tuple[int, float]:
        """(bar, beat) with beat counted from 1. Bar 0 = pickup before bar 1."""
        x = self.beat_pos(t)
        k = int(np.searchsorted(self.down, x + 1e-6, side="right")) - 1
        if k < 0:
            return 0, x - (self.down[0] - self.bpb) + 1
        return k + 1, x - self.down[k] + 1

    def label(self, t: float) -> str:
        if t < self.beats[0] - 0.5 * self.period:
            return "-"
        x = self.beat_pos(t) + 0.25                   # a hair before a beat counts as that beat
        k = int(np.searchsorted(self.down, x, side="right")) - 1
        if k < 0:
            return f"0.{max(1, int(np.floor(x - (self.down[0] - self.bpb))) + 1)}"
        return f"{k + 1}.{int(np.floor(x - self.down[k])) + 1}"

    def bar_of(self, t: float) -> int:
        return self.bar_beat(t)[0]

    @property
    def bar_starts(self) -> list[float]:
        return [float(self.beats[i]) for i in self.down]

    def bar_span(self, n: int) -> tuple[float, float]:
        """Start/end seconds of bar n (1-based)."""
        s = self.bar_starts
        a = s[n - 1]
        e = s[n] if n < len(s) else min(self.duration, a + self.bpb * self.period)
        return a, e

    def snap(self, t: float, bar_reach: float = 1.0) -> float:
        """Snap a boundary to a bar start within bar_reach beats, else to the nearest beat."""
        if t <= 0.05:
            return 0.0
        x = self.beat_pos(t)
        dn = np.asarray(self.down, dtype=float)
        j = int(np.argmin(np.abs(dn - x)))
        if abs(dn[j] - x) <= bar_reach:
            return float(self.beats[self.down[j]])
        i = int(round(min(max(x, 0), len(self.beats) - 1)))
        return float(self.beats[i])

    # ------------------------------------------------------------ check --
    def check(self, anchors: list[float]) -> dict | None:
        """How many anchors (section starts) sit on a bar start now vs. with a half-bar shift."""
        anchors = [t for t in anchors if self.beats[0] + self.period < t < self.beats[-1] - self.period]
        if len(anchors) < 3 or self.bpb % 2:
            return None

        def hits(down: list[int]) -> int:
            ds = np.asarray(down, dtype=float)
            return sum(1 for t in anchors if float(np.min(np.abs(ds - self.beat_pos(t)))) <= 0.5)

        half = self.bpb // 2
        return {"n": len(anchors), "now": hits(self.down), "half": hits([i + half for i in self.down]), "k": half}

    # ----------------------------------------------------------- frames --
    def frames(self, beats: float = 1.0) -> float:
        return beats * self.period * self.fps
