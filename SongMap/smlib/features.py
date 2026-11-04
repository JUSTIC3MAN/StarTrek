"""Full-mix levels per beat and per bar: loudness, low end (bass + kick), highs, percussive hits, vocal cover."""
from __future__ import annotations

import numpy as np

SR = 22050
HOP = 512


def _db(p: np.ndarray, ref: float) -> np.ndarray:
    return 10.0 * np.log10(np.maximum(p, 1e-12) / ref)


def _pmean_db(vals) -> float:
    v = np.asarray(list(vals), dtype=float)
    return float(10.0 * np.log10(np.mean(10.0 ** (v / 10.0)))) if v.size else -120.0


def levels(mono: np.ndarray, sr: int, grid, lines: list[dict]) -> dict:
    import librosa
    import soxr

    y = mono.astype(np.float32)
    if sr != SR:
        y = soxr.resample(y, sr, SR).astype(np.float32)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP)) ** 2
    f = librosa.fft_frequencies(sr=SR, n_fft=2048)
    tot = S.sum(0)
    low = S[(f >= 30) & (f < 150)].sum(0)
    high = S[(f >= 5000) & (f < 11000)].sum(0)
    mel = librosa.feature.melspectrogram(S=S, sr=SR, n_mels=96)
    onset = librosa.onset.onset_strength(S=librosa.power_to_db(mel, ref=np.max), sr=SR)
    ft = librosa.frames_to_time(np.arange(S.shape[1]), sr=SR, hop_length=HOP)

    b = grid.beats
    edges = np.append(b, min(b[-1] + grid.period, grid.duration))
    ix = np.searchsorted(ft, edges)

    def per_beat(x: np.ndarray) -> np.ndarray:
        n = len(x)
        return np.array([x[min(a, n - 1):max(min(e, n), min(a, n - 1) + 1)].mean() for a, e in zip(ix[:-1], ix[1:])])

    ref = float(tot.max()) or 1.0
    beat = {
        "rms": _db(per_beat(tot), ref),
        "low": _db(per_beat(low), ref),
        "high": _db(per_beat(high), ref),
        "onset": per_beat(onset),
    }

    # vocal cover per beat from the lyric word timings
    grid_t = np.zeros(int(grid.duration * 100) + 2, dtype=bool)          # 10 ms vocal mask
    for ln in lines:
        for w in ln["words"]:
            grid_t[int(w["s"] * 100):int(w["e"] * 100) + 1] = True
    cs = np.concatenate([[0], np.cumsum(grid_t)])
    ia = np.clip((edges[:-1] * 100).astype(int), 0, len(grid_t))
    ib = np.clip((edges[1:] * 100).astype(int), 0, len(grid_t))
    beat["vocal"] = (cs[ib] - cs[ia]) / np.maximum(ib - ia, 1)

    bars = []
    down = list(grid.down) + [len(b)]
    for n, (i, j) in enumerate(zip(down[:-1], down[1:]), start=1):
        j = max(j, i + 1)
        bars.append({
            "n": n, "t": float(b[i]), "beats": j - i,
            "rms": _pmean_db(beat["rms"][i:j]), "low": _pmean_db(beat["low"][i:j]),
            "high": _pmean_db(beat["high"][i:j]), "onset": float(np.mean(beat["onset"][i:j])),
            "vocal": float(np.mean(beat["vocal"][i:j])),
        })
    bar_rms = np.array([x["rms"] for x in bars]) if bars else np.array([0.0])
    return {
        "beat": beat, "bars": bars,
        "med_beat": float(np.median(beat["rms"])),
        "q": (float(np.percentile(bar_rms, 33)), float(np.percentile(bar_rms, 67))),
    }


def energy_word(db: float, q: tuple[float, float]) -> str:
    return "low" if db < q[0] else ("high" if db > q[1] else "mid")


def pmean_db(vals) -> float:
    return _pmean_db(vals)
