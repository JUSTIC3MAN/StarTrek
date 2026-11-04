"""
lyricsfile.py - the Lyrics inbox: drop a song in SubtitleStudio/Lyrics, get its
lyrics back as plain text beside it.

The whole interface is files, so anything that can copy a file and read one
(Claude, a script, you in Explorer) can use the recogniser without the editor.

  Lyrics/<song>.mp3         you drop this in (any audio or video file)
  Lyrics/<song>.working     while it runs: one line, e.g. "42% Isolating the vocal..."
  Lyrics/<song>.txt         the lyrics: a one-line header, then the lines,
                            a blank line between sections
  Lyrics/<song>.lrc         the same lines with timestamps (synced-lyrics format)
  Lyrics/<song>.error.txt   if it failed, why
  Lyrics/hints.txt          names and slang to listen for, every song
  Lyrics/<song>.hints.txt   the same for one song (rough lyrics work here too)

Whoever is running does the work: Subtitle Studio while it's open (through its
GPU queue, with the models the editor already has loaded), otherwise Lyrics.bat.
A song is claimed by creating <song>.working exclusively, so it is never done
twice, and a claim left behind by a closed window is recognised and taken over.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from . import media, separate
from .asr import ASR, SR, free_gpu
from .lines import build_lines, lines_to_json

log = logging.getLogger("studio.lyrics")

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "Lyrics"

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".opus", ".wma", ".aif", ".aiff",
             ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"}

LINE_CHARS = 60      # about one bar of rap (captions use 42)
LINE_WORDS = 14
LINE_PAUSE = 0.5     # a breath this long starts a new line
SECTION_GAP = 2.0    # a gap this long between lines starts a new section
STALE_LOCK = 15 * 60 # backstop: a claim untouched this long is abandoned
ALIVE_WITHIN = 20    # an .alive file older than this means that side is closed

ENGINE_NAME = {"qwen3-1.7b": "Qwen3-ASR 1.7B", "qwen3-0.6b": "Qwen3-ASR 0.6B",
               "whisper-turbo": "Whisper large-v3-turbo"}

Report = Callable[[float, str], None]


def _noop(_f: float, _m: str) -> None:
    pass


# ------------------------------------------------------------ the files ---

def paths(audio: Path) -> tuple[Path, Path, Path, Path]:
    """(lyrics .txt, timed .lrc, .error.txt, .working) for one song."""
    return (audio.with_suffix(".txt"), audio.with_suffix(".lrc"),
            audio.with_name(audio.stem + ".error.txt"), audio.with_name(audio.stem + ".working"))


def _retry(fn, tries: int = 15, wait: float = 0.2):
    """Windows refuses to replace/delete a file another program has open for a moment."""
    for i in range(tries):
        try:
            return fn()
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(wait)


def _write(p: Path, text: str) -> None:
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    _retry(lambda: os.replace(tmp, p))


def _up_to_date(result: Path, audio: Path) -> bool:
    try:
        return result.stat().st_mtime >= audio.stat().st_mtime - 0.001
    except OSError:
        return False


# ------------------------------------------------------ who is running ---

def beat(mode: str) -> None:
    """Say this side is up: Lyrics/.alive.<mode> holds '<unix time> <pid>'."""
    try:
        INBOX.mkdir(exist_ok=True)
        with open(INBOX / f".alive.{mode}", "w", encoding="utf-8", newline="\n") as f:
            f.write(f"{int(time.time())} {os.getpid()}\n")
    except OSError:
        pass


def _alive_info(mode: str) -> tuple[float, int] | None:
    try:
        t, pid = (INBOX / f".alive.{mode}").read_text("utf-8").split()[:2]
        return float(t), int(pid)
    except (OSError, ValueError):
        return None


def alive(mode: str) -> bool:
    a = _alive_info(mode)
    return bool(a) and time.time() - a[0] < ALIVE_WITHIN


OWNER_TAG = re.compile(r"\[(\w+) (\d+)\]\s*$")


def lock_stale(work: Path) -> bool:
    """A claim is dead when the window that made it has closed (or restarted)."""
    try:
        st = work.stat()
        text = work.read_text("utf-8")
    except OSError:
        return True
    if time.time() - st.st_mtime > STALE_LOCK:
        return True
    m = OWNER_TAG.search(text)
    if not m:
        return False
    a = _alive_info(m.group(1))
    return not a or time.time() - a[0] >= ALIVE_WITHIN or a[1] != int(m.group(2))


def candidates() -> list[Path]:
    """Songs in the inbox with no up-to-date result and no live claim, oldest first."""
    if not INBOX.is_dir():
        return []
    out = []
    try:
        entries = list(os.scandir(INBOX))
    except OSError:
        return []
    for e in entries:
        try:
            if not e.is_file() or e.name.startswith((".", "~")):
                continue
            p = Path(e.path)
            if p.suffix.lower() not in AUDIO_EXT:
                continue
            txt, _, err, work = paths(p)
            if _up_to_date(txt, p) or _up_to_date(err, p):
                continue
            if work.exists() and not lock_stale(work):
                continue
            out.append((e.stat().st_mtime, p))
        except OSError:
            continue
    return [p for _, p in sorted(out)]


class Settled:
    """A file has arrived once its size and time hold still for a second and it opens."""

    def __init__(self):
        self.seen: dict[Path, tuple[tuple, float]] = {}

    def ready(self, p: Path) -> bool:
        try:
            st = p.stat()
        except OSError:
            self.seen.pop(p, None)
            return False
        sig = (st.st_size, st.st_mtime)
        prev = self.seen.get(p)
        now = time.time()
        if not prev or prev[0] != sig:
            self.seen[p] = (sig, now)
            return False
        if now - prev[1] < 1.0 or st.st_size == 0:
            return False
        try:
            with open(p, "rb") as f:
                f.read(1)
        except OSError:
            return False
        return True


def claim(p: Path, owner: str) -> bool:
    """Create <song>.working exclusively. owner is '<mode> <pid>' of the window doing the work."""
    work = paths(p)[3]
    try:
        if work.exists() and lock_stale(work):
            _retry(lambda: work.unlink(missing_ok=True))
        fd = os.open(work, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"0% Starting... [{owner}]\n")
    return True


def release(p: Path) -> None:
    try:
        _retry(lambda: paths(p)[3].unlink(missing_ok=True))
    except OSError:
        log.warning("could not remove %s", paths(p)[3])


class Progress:
    """report(fraction, message) -> rewrites <song>.working, at most twice a second."""

    def __init__(self, p: Path, owner: str):
        self.work = paths(p)[3]
        self.owner = owner
        self.msg = "Starting..."
        self.last = 0.0

    def __call__(self, f: float, msg: str = "") -> None:
        if msg:
            self.msg = msg
        now = time.time()
        if now - self.last < 0.5:
            return
        self.last = now
        try:
            with open(self.work, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(f"{int(max(0.0, min(1.0, f)) * 100)}% {self.msg} [{self.owner}]\n")
        except OSError:
            pass


def hints_for(p: Path) -> str:
    """Context for the recogniser: Lyrics/hints.txt + <song>.hints.txt, '#' lines skipped."""
    parts: list[str] = []
    for h in (INBOX / "hints.txt", p.with_name(p.stem + ".hints.txt")):
        try:
            text = h.read_text("utf-8-sig")
        except OSError:
            continue
        parts += [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    return "\n".join(parts)[:6000]


# ------------------------------------------------------------ the work ---

def transcribe_file(asr: ASR, src: Path, context: str = "", report: Report = _noop,
                    engine: str = "qwen3-1.7b", language: str | None = None, isolate: bool = True) -> dict:
    """Song file -> lyric lines with word timings. Same engine as the editor:
    BS-RoFormer vocal isolation, Qwen3-ASR, Qwen3-ForcedAligner (Whisper as fallback)."""
    if not media.FFMPEG:
        raise RuntimeError("ffmpeg was not found. Install it with:  winget install Gyan.FFmpeg")
    t0 = time.time()
    warnings: list[str] = []
    work = Path(tempfile.mkdtemp(prefix="sslyrics_"))
    try:
        analysis: Path = src
        used_sep = False
        if isolate:
            ok, why = separate.available()
            if not ok:
                warnings.append(f"vocal isolation unavailable ({why}); used the full mix")
            else:
                try:
                    report(0.02, "Reading the audio...")
                    mix = work / "mix.wav"
                    media.extract_wav(src, mix, 44100, 2)
                    report(0.05, "Isolating the vocal...")
                    analysis = separate.isolate_vocals(mix, work)
                    used_sep = True
                except Exception as e:  # noqa: BLE001
                    log.exception("vocal isolation failed")
                    warnings.append(f"vocal isolation failed ({type(e).__name__}); used the full mix")
                    analysis = src
                free_gpu()
        report(0.30, "Preparing audio for recognition...")
        wav = media.load_mono(analysis, SR)
        if wav.size < SR // 2:
            raise RuntimeError("No audio found in this file.")
        words, _chunks, lang, used = asr.recognise(wav, engine, language, context,
                                                   lambda f, m: report(0.30 + 0.69 * f, m))
        if used != engine:
            warnings.append("Qwen3-ASR could not run, so Whisper was used (reason in studio.log / lyrics.log)")
        lines = build_lines(words, max_chars=LINE_CHARS, max_words=LINE_WORDS, pause=LINE_PAUSE) if words else []
        return {"lines": lines_to_json(lines), "language": lang, "engine": used, "separated": used_sep,
                "duration": round(wav.size / SR, 2), "seconds": round(time.time() - t0, 1),
                "warnings": warnings}
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------- output ---

def _clock(t: float) -> str:
    t = int(round(max(0.0, t)))
    return f"{t // 60}:{t % 60:02d}"


def _lrc_stamp(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    m, cs = divmod(cs, 6000)
    return f"[{m:02d}:{cs // 100:02d}.{cs % 100:02d}]"


def _text(line: dict) -> str:
    return " ".join(w["t"] for w in line.get("words", []))


_YT_ID = re.compile(r"\s*\[[A-Za-z0-9_-]{11}\]")
_JUNK = re.compile(r"\s*[(\[{][^)\]}]*\b(official|oficial|video|v[ií]deo|audio|lyrics?|letra|visuali[sz]er"
                   r"|hd|4k|remaster(ed)?|prod|productions?|producciones|producido)\b[^)\]}]*[)\]}]", re.I)


def _clean(s: str) -> str:
    s = _JUNK.sub("", _YT_ID.sub("", s or ""))
    return re.sub(r"\s+", " ", s).strip(" -_–—|")


def song_info(p: Path) -> tuple[str, str]:
    """(title, artist) from the file's tags, else from an 'Artist - Title (Official Video) [id]' name."""
    tags: dict[str, str] = {}
    if media.FFPROBE:
        try:
            import json
            r = media.run([media.FFPROBE, "-v", "error", "-print_format", "json", "-show_entries",
                           "format_tags", str(p)], timeout=30)
            raw = (json.loads(r.stdout.decode("utf-8", "replace") or "{}").get("format") or {}).get("tags") or {}
            tags = {k.lower(): str(v) for k, v in raw.items()}
        except Exception:  # noqa: BLE001
            pass
    title = _clean(tags.get("title", "")) or _clean(p.stem)
    artist = _clean(tags.get("artist") or tags.get("album_artist") or "")
    for sep in (" - ", " – ", " — "):
        if sep in title:
            a, t = (x.strip() for x in title.split(sep, 1))
            if a and t and (not artist or a.lower() in artist.lower() or artist.lower() in a.lower()):
                artist, title = a, t
            break
    title = re.sub(r"\s+[-–—]\s+@\S+$", "", title)               # "... - @channelname"
    if artist:                                                    # "... - Artist" repeated at the end
        title = re.sub(r"\s+[-–—]\s+" + re.escape(artist) + r"$", "", title, flags=re.I)
    return title or p.stem, artist


def format_txt(title: str, artist: str, r: dict) -> str:
    """The lyric sheet: title, artist, then the lines - a blank line between sections."""
    out = [title] + ([f"Artist: {artist}"] if artist else []) + [""]
    prev_end = None
    for ln in r.get("lines", []):
        ws = ln.get("words") or []
        if not ws:
            continue
        if prev_end is not None and ws[0]["s"] - prev_end >= SECTION_GAP:
            out.append("")
        out.append(_text(ln))
        prev_end = ws[-1]["e"]
    if prev_end is None:
        out.append("(no vocals heard)")
    return "\n".join(out) + "\n"


def format_lrc(title: str, artist: str, r: dict) -> str:
    d = int(round(r.get("duration", 0)))
    how = ENGINE_NAME.get(r.get("engine"), r.get("engine") or "")
    if r.get("separated"):
        how += ", vocal isolated"
    out = [f"[ti:{title}]"] + ([f"[ar:{artist}]"] if artist else []) + [
        f"[la:{r.get('language') or ''}]", f"[length:{d // 60:02d}:{d % 60:02d}]",
        f"[re:Subtitle Studio - {how}]"] + [f"[#:{w}]" for w in r.get("warnings", [])]
    for ln in r.get("lines", []):
        ws = ln.get("words") or []
        if ws:
            out.append(_lrc_stamp(ws[0]["s"]) + _text(ln))
    return "\n".join(out) + "\n"


def format_srt(r: dict) -> str:
    """One subtitle per lyric line, for video editors and players."""
    def ts(t: float) -> str:
        ms = int(round(max(0.0, t) * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    lines = [ln["words"] for ln in r.get("lines", []) if ln.get("words")]
    out = []
    for i, ws in enumerate(lines):
        s, e = ws[0]["s"], max(ws[-1]["e"], ws[0]["s"] + 0.8)
        if i + 1 < len(lines):
            e = min(e, lines[i + 1][0]["s"])
        out.append(f"{i + 1}\n{ts(s)} --> {ts(e)}\n" + " ".join(w["t"] for w in ws) + "\n")
    return "\n".join(out)


def finish(p: Path, r: dict) -> None:
    txt, lrc, err, _ = paths(p)
    title, artist = song_info(p)
    _write(lrc, format_lrc(title, artist, r))
    _write(p.with_suffix(".srt"), format_srt(r))
    _write(txt, format_txt(title, artist, r))      # the .txt last: it is the "done" signal
    try:
        _retry(lambda: err.unlink(missing_ok=True))
    except OSError:
        pass


def fail(p: Path, message: str) -> None:
    try:
        _write(paths(p)[2], f"{p.name}: no lyrics - {message}\n")
    except OSError:
        log.exception("could not write the error file for %s", p.name)


# ------------------------------------------------------------- runners ---

def process(asr: ASR, p: Path, owner: str, say: Callable[[str], None] = print) -> bool:
    """Do one claimed song in this process. Releases the claim either way."""
    prog = Progress(p, owner)
    try:
        r = transcribe_file(asr, p, hints_for(p), prog)
        finish(p, r)
        n = sum(1 for ln in r["lines"] if ln.get("words"))
        say(f"  {p.name}: {n} lines, {r['language']}, {_clock(r['duration'])} song, done in {r['seconds']:.0f} s")
        log.info("lyrics: %s -> %d lines (%s, %s) in %.1fs", p.name, n, r["language"], r["engine"], r["seconds"])
        return True
    except Exception as e:  # noqa: BLE001
        log.exception("lyrics failed for %s", p.name)
        fail(p, f"{type(e).__name__}: {e}")
        say(f"  {p.name}: FAILED - {type(e).__name__}: {e}")
        return False
    finally:
        release(p)


def run_worker(owner: str, idle_exit: float = 180.0, say: Callable[[str], None] = print) -> None:
    """Headless helper (started by Lyrics.bat): do every waiting song, keep the models
    warm for a few minutes in case another comes, then exit and free the GPU."""
    asr: ASR | None = None
    settled = Settled()
    last = time.time()
    while True:
        for p in candidates():
            if settled.ready(p) and claim(p, owner):
                if asr is None:
                    asr = ASR()     # models load on first use, then stay until this helper exits
                say(f"  {p.name}: working...")
                process(asr, p, owner, say)
                last = time.time()
        if time.time() - last > idle_exit:
            return
        time.sleep(1.0)


def start_in_studio(worker) -> None:
    """Run the inbox inside Subtitle Studio: one GPU queue, the editor's loaded models."""
    owner = f"studio {os.getpid()}"

    def run_one(p: Path) -> None:
        prog = Progress(p, owner)
        try:
            job = worker.submit("lyricsfile", "", {"path": str(p), "context": hints_for(p)})
            while not job.done_event.wait(1.0):
                beat("studio")
                if job.state == "queued":
                    prog(0.0, "Waiting for the editor's current job...")
                else:
                    prog(job.progress, job.message)
            if job.state == "done":
                finish(p, job.result)
                log.info("lyrics: %s done (%s)", p.name, job.result.get("language"))
            else:
                fail(p, job.error or "unknown error")
        except Exception as e:  # noqa: BLE001
            log.exception("lyrics inbox: %s", p.name)
            fail(p, f"{type(e).__name__}: {e}")
        finally:
            release(p)

    def loop() -> None:
        INBOX.mkdir(exist_ok=True)
        settled = Settled()
        while True:
            try:
                beat("studio")
                for p in candidates():
                    if settled.ready(p) and claim(p, owner):
                        run_one(p)
            except Exception:  # noqa: BLE001
                log.exception("lyrics inbox")
            time.sleep(1.0)

    threading.Thread(target=loop, daemon=True, name="lyrics-inbox").start()
