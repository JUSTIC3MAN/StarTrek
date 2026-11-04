"""SongMap -> Subtitle Studio bridge. Runs with Subtitle Studio's own Python (its venv) and changes nothing there.

  <SubtitleStudio>\\venv\\Scripts\\python.exe sm_lyrics.py <SubtitleStudio folder> <batch.json>

batch.json: [{"src": song file, "work": folder, "stem": name, "lyrics": known-lyrics .txt or null}, ...]
For each song, writes into its work folder:
  mix.wav (44.1 kHz stereo, used for beats and sections), lyrics.json (lines with word timings),
  <stem>.lyrics.txt / <stem>.lrc / <stem>.srt (Subtitle Studio's own formats), progress.txt while working,
  lyrics_error.txt if it failed.
Same engine as Subtitle Studio: BS-RoFormer vocal isolation -> Qwen3-ASR 1.7B -> Qwen3-ForcedAligner.
With known lyrics, Subtitle Studio's "place your lyrics" step puts those exact words on the timeline.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import time
import traceback
import types
from pathlib import Path

import numpy as np

MAX_CHUNK = 20.0      # seconds of vocal per recognition piece (Subtitle Studio uses 100 s: too long for sung hooks)
MIN_SPLIT = 5.0       # a looping piece is split in two and heard again, down to this length
log = logging.getLogger("songmap.lyrics")


# --------------------------------------------------------------- vocal pieces ---
def voiced_regions(wav: np.ndarray, sr: int, floor_db: float) -> list[tuple[float, float]]:
    """Stretches where the isolated vocal is above the floor; small gaps closed, blips dropped."""
    hop = sr // 20
    k = wav.size // hop
    if k < 2:
        return []
    rms = np.sqrt(np.mean(wav[:k * hop].reshape(k, hop).astype(np.float64) ** 2, axis=1))
    on = 20 * np.log10(np.maximum(rms, 1e-7)) > floor_db
    regs, i = [], 0
    while i < k:
        if on[i]:
            j = i
            while j < k and on[j]:
                j += 1
            regs.append([i * 0.05, j * 0.05])
            i = j
        else:
            i += 1
    merged: list[list[float]] = []
    for a, b in regs:
        if merged and a - merged[-1][1] < 0.5:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if b - a >= 0.2]


def vocal_chunks(wav: np.ndarray, sr: int, floor_db: float, split_chunks) -> list[tuple[float, float]]:
    """Pieces of at most MAX_CHUNK s that start and end in the gaps between phrases."""
    dur = wav.size / sr
    pieces: list[list[float]] = []
    for a, b in voiced_regions(wav, sr, floor_db):
        if b - a > MAX_CHUNK:                         # one long phrase run: cut at its quietest points
            for s, e in split_chunks(wav[int(a * sr):int(b * sr)], max_sec=MAX_CHUNK * 0.8, expand=MAX_CHUNK * 0.2):
                pieces.append([a + s, a + e])
        elif pieces and b - pieces[-1][0] <= MAX_CHUNK:
            pieces[-1][1] = b
        else:
            pieces.append([a, b])
    out = []
    for i, (a, b) in enumerate(pieces):              # a little air either side, never into the neighbour
        lo = 0.0 if i == 0 else (pieces[i - 1][1] + a) / 2
        hi = dur if i == len(pieces) - 1 else (b + pieces[i + 1][0]) / 2
        out.append((max(lo, a - 0.3), min(hi, b + 0.3)))
    return out


# ------------------------------------------------------------- loop guard ---
def _norm(w: str) -> str:
    return re.sub(r"[^\w']", "", w.lower())


def longest_repeat(words: list[str]) -> tuple[int, int, int]:
    """(count, n, start) of the longest run of one n-gram (n 2..12) repeated back to back."""
    best = (1, 0, 0)
    nw = [_norm(w) for w in words]
    for n in range(2, min(12, len(nw) // 2) + 1):
        i = 0
        while i + 2 * n <= len(nw):
            c = 1
            while i + (c + 1) * n <= len(nw) and nw[i + c * n:i + (c + 1) * n] == nw[i:i + n]:
                c += 1
            if c > best[0] or (c == best[0] and c > 1 and n > best[1]):
                best = (c, n, i)
            i += max(1, (c - 1) * n) if c > 1 else 1
    return best


def loopy(text: str, dur: float) -> bool:
    w = text.split()
    c, n, _ = longest_repeat(w)
    return len(w) / max(dur, 0.5) > 7.0 or (c >= 3 and c * n > max(6, dur * 1.6))


def collapse(text: str, dur: float) -> str:
    """Cut repeats of a phrase down to what could really be sung in this time."""
    w = text.split()
    for _ in range(8):
        c, n, i = longest_repeat(w)
        allowed = max(2, int(dur * 1.6 / max(n, 1)))
        if c < 3 or c <= allowed:
            break
        w = w[:i + allowed * n] + w[i + c * n:]
    return " ".join(w)


# ------------------------------------------------------------ word timing ---
def stacked(ws, s: float, e: float) -> bool:
    """The aligner gave up: words piled on one instant, or squeezed into a sliver of the piece."""
    if len(ws) < 4:
        return False
    st = np.array([w.s for w in ws])
    tight = float(np.mean(np.diff(st) < 0.03))
    span = ws[-1].e - ws[0].s
    return tight > 0.35 or span < 0.12 * (e - s)


def spread_voiced(Word, texts: list[str], regs: list[tuple[float, float]], s: float, e: float):
    """Lay words over the voiced parts of [s, e] by letter weight (when alignment failed)."""
    rs = [(max(a, s), min(b, e)) for a, b in regs if b > s and a < e] or [(s, e)]
    total = sum(b - a for a, b in rs)
    wts = np.array([max(1, len(t)) + 1.5 for t in texts], dtype=float)
    cum = np.concatenate([[0], np.cumsum(wts)]) / wts.sum() * total

    def at(u: float) -> float:
        for a, b in rs:
            if u <= b - a:
                return a + u
            u -= b - a
        return rs[-1][1]
    return [Word(t, at(cum[i]), at(cum[i] + 0.85 * (cum[i + 1] - cum[i]))) for i, t in enumerate(texts)]


def repair_density(Word, words: list, regs) -> tuple[list, int]:
    """One rule over the whole song: nobody sings 3+ words less than 70 ms apart. When the aligner piles
    words up like that, spread them - together with the words after them, until there is at least
    0.17 s per word (about 6 words/s) - over the voiced time before the next word."""
    w, fixed, i = list(words), 0, 0
    while i < len(w) - 2:
        j = i
        while j + 1 < len(w) and w[j + 1].s - w[j].s < 0.07:
            j += 1
        if j - i + 1 < 3:
            i += 1
            continue
        lo, k = w[i].s, j
        while True:
            hi = w[k + 1].s if k + 1 < len(w) else w[k].e + 0.25 * (k - i + 1)
            if hi - lo >= 0.17 * (k - i + 1) or k + 1 >= len(w):
                break
            k += 1
        w[i:k + 1] = spread_voiced(Word, [x.t for x in w[i:k + 1]], regs, lo, hi)
        fixed += 1
        i = k + 1
    return w, fixed


def transcribe_vocal(asr, wav: np.ndarray, context: str, report, A) -> tuple[list, list, str, str, dict]:
    """Qwen3-ASR + ForcedAligner over short vocal pieces, with loop and alignment guards.
    Returns (words, chunks, language, engine, stats)."""
    SR, Word = A.SR, A.Word
    floor = A.voice_floor(wav)
    chunks = vocal_chunks(wav, SR, floor, A.split_chunks)
    stats = {"pieces": len(chunks), "loops_fixed": 0, "retimed": 0}
    eng = asr.engine("qwen3-1.7b")
    eng.load(lambda f, m="": report(0.05 * f, m))
    if hasattr(eng.model, "max_new_tokens"):
        eng.model.max_new_tokens = 384               # a 20 s piece never needs more; stops runaway loops early
    report(0.06, "transcribing")
    parts = eng.transcribe(wav, chunks, None, context, lambda f, m="": report(0.06 + 0.5 * f, "transcribing"))

    def heard_again(p: dict, depth: int) -> list[dict]:
        dur = p["end"] - p["start"]
        if not loopy(p["text"], dur):
            return [p]
        if dur < 2 * MIN_SPLIT or depth >= 2:
            stats["loops_fixed"] += 1
            return [dict(p, text=collapse(p["text"], dur))]
        seg = wav[int(p["start"] * SR):int(p["end"] * SR)]
        halves = A.split_chunks(seg, max_sec=dur / 2, expand=dur / 4)
        sub = [(p["start"] + a, p["start"] + b) for a, b in halves]
        stats["loops_fixed"] += 1
        res = eng.transcribe(wav, sub, None, context, lambda f, m="": None)
        return [q for r in res for q in heard_again(r, depth + 1)]

    fixed = []
    for p in parts:
        fixed += heard_again(p, 0)
    parts = [p for p in fixed if p["text"].strip()]
    report(0.6, "placing every word in time")
    asr.aligner.load(lambda f, m="": report(0.6, m))
    regs = voiced_regions(wav, SR, floor)
    pieces = [(wav[int(p["start"] * SR):int(p["end"] * SR)], p["text"], p["lang"]) for p in parts]
    aligned = asr.aligner.align(pieces, [p["start"] for p in parts],
                                lambda f, m="": report(0.6 + 0.35 * f, "placing every word in time"))
    words = []
    for p, ws in zip(parts, aligned):
        if (not ws and p["text"].split()) or stacked(ws, p["start"], p["end"]):
            stats["retimed"] += 1
            ws = spread_voiced(Word, [w.t for w in ws] or p["text"].split(), regs, p["start"], p["end"])
        words += ws
    langs = [p["lang"] for p in parts if p.get("lang")]
    lang = max(set(langs), key=langs.count) if langs else "English"
    words, stats["runs_fixed"] = repair_density(Word, A.fix_times(words), regs)
    log.info("songmap lyrics: %d pieces, %d words, loops fixed %d, retimed %d, runs fixed %d", len(chunks), len(words),
             stats["loops_fixed"], stats["retimed"], stats.get("runs_fixed", 0))
    return A.fix_times(words), chunks, lang, "qwen3-1.7b", stats


def main() -> int:
    ss = Path(sys.argv[1]).resolve()
    batch_file = Path(sys.argv[2]).resolve()
    batch = json.loads(batch_file.read_text("utf-8"))
    sys.path.insert(0, str(ss))
    os.chdir(ss)
    logf = sys.argv[3] if len(sys.argv) > 3 else str(batch_file.with_suffix(".log"))
    logging.basicConfig(filename=logf, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from studio import lyricsfile as L
    from studio import media, separate
    from studio.asr import ASR, SR, free_gpu, split_chunks, voice_floor
    from studio.lines import Word, build_lines, fix_times, lines_to_json
    A = types.SimpleNamespace(SR=SR, Word=Word, split_chunks=split_chunks, voice_floor=voice_floor, fix_times=fix_times)

    asr = ASR()
    for item in batch:
        work = Path(item["work"])
        work.mkdir(parents=True, exist_ok=True)
        prog = work / "progress.txt"

        def report(f: float, m: str = "", _p=prog) -> None:
            try:
                _p.write_text(f"{int(max(0.0, min(1.0, f)) * 100)} {m}", "utf-8")
            except OSError:
                pass

        try:
            src = Path(item["src"])
            t0 = time.time()
            warnings: list[str] = []
            mix = work / "mix.wav"
            report(0.01, "reading the audio")
            media.extract_wav(src, mix, 44100, 2)
            analysis, used_sep = mix, False
            ok, why = separate.available()
            if ok:
                try:
                    report(0.05, "isolating the vocal")
                    analysis = separate.isolate_vocals(mix, work / "sep")
                    used_sep = True
                except Exception as e:  # noqa: BLE001
                    logging.exception("vocal isolation failed")
                    warnings.append(f"vocal isolation failed ({type(e).__name__}); used the full mix")
                free_gpu()
            else:
                warnings.append(f"vocal isolation unavailable ({why}); used the full mix")
            report(0.3, "preparing the vocal")
            wav = media.load_mono(analysis, SR)
            rep = lambda f, m="": report(0.3 + 0.6 * f, m or "transcribing")  # noqa: E731
            stats = {}
            try:
                words, chunks, lang, used, stats = transcribe_vocal(asr, wav, L.hints_for(src), rep, A)
            except Exception as e:  # noqa: BLE001
                logging.exception("SongMap's piecewise recognition failed; using Subtitle Studio's own")
                warnings.append(f"piecewise recognition failed ({type(e).__name__}); used Subtitle Studio's default")
                words, chunks, lang, used = asr.recognise(wav, "qwen3-1.7b", None, L.hints_for(src), rep)
            known = ""
            if item.get("lyrics"):
                known = Path(item["lyrics"]).read_text("utf-8-sig")
            if known.strip():
                from studio import pipeline
                report(0.92, "placing your lyrics")
                lines = pipeline.Worker._place_lyrics(
                    types.SimpleNamespace(asr=asr), None, known, words, chunks, lang, None, wav,
                    lambda f, m="": report(0.92 + 0.07 * f, "placing your lyrics"))
                mode = "your lyrics aligned"
            else:
                lines = lines_to_json(build_lines(words, max_chars=L.LINE_CHARS, max_words=L.LINE_WORDS,
                                                  pause=L.LINE_PAUSE)) if words else []
                mode = "transcribed"
            title, artist = L.song_info(src)
            r = {"lines": lines, "language": lang, "engine": used, "separated": used_sep,
                 "duration": round(wav.size / SR, 2), "seconds": round(time.time() - t0, 1),
                 "warnings": warnings, "title": title, "artist": artist, "mode": mode, "stats": stats}
            stem = item.get("stem") or src.stem
            (work / f"{stem}.lyrics.txt").write_text(L.format_txt(title, artist, r), "utf-8")
            (work / f"{stem}.lrc").write_text(L.format_lrc(title, artist, r), "utf-8")
            (work / f"{stem}.srt").write_text(L.format_srt(r), "utf-8")
            (work / "lyrics.json").write_text(json.dumps(r, ensure_ascii=False), "utf-8")
            report(1.0, "lyrics done")
        except Exception as e:  # noqa: BLE001
            logging.exception("song failed")
            (work / "lyrics_error.txt").write_text(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}", "utf-8")
        finally:
            shutil.rmtree(work / "sep", ignore_errors=True)
            try:
                free_gpu()
            except Exception:  # noqa: BLE001
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
