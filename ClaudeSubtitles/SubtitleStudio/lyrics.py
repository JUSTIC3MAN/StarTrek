#!/usr/bin/env python3
"""
lyrics.py - Subtitle Studio's Lyrics inbox, without the editor.

    Lyrics.bat                                   watch the Lyrics folder (leave the window open)
    venv\\Scripts\\python lyrics.py song.mp3       do one file now and print its lyrics

Drop a song into SubtitleStudio\\Lyrics and its lyrics appear beside it as
<song>.txt, plus <song>.lrc with timings. This window stays light: a helper
process loads the models only when there is a song to do, and exits a few
minutes after the last one, so the GPU is free for everything else.
While Subtitle Studio is open, it does the work instead, with the models it
already has loaded.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))
sys.path.insert(0, str(ROOT))

from studio import lyricsfile as L  # noqa: E402

LOG_FILE = ROOT / "lyrics.log"
log = logging.getLogger("studio.lyrics")


def setup_log(rotate: bool) -> None:
    if rotate:
        try:
            if LOG_FILE.is_file() and LOG_FILE.stat().st_size > 2_000_000:
                LOG_FILE.replace(LOG_FILE.with_name("lyrics.log.1"))
        except OSError:
            pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")])
    for noisy in ("httpx", "urllib3", "huggingface_hub", "filelock", "audio_separator", "transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def say(msg: str) -> None:
    print(time.strftime("%H:%M:%S") + msg, flush=True)


def watch() -> None:
    setup_log(rotate=True)
    L.INBOX.mkdir(exist_ok=True)
    bar = "=" * 64
    print(bar)
    print("  SUBTITLE STUDIO - LYRICS INBOX")
    print(bar)
    print(f"  Drop songs in:  {L.INBOX}")
    print("  Lyrics appear beside each one as <song>.txt (and <song>.lrc with timings).")
    print("  The GPU is only used while a song is being done.")
    print(bar)
    print("  Leave this window open. Close it to stop.")
    print(flush=True)
    log.info("lyrics inbox watching %s", L.INBOX)
    me = os.getpid()
    child: subprocess.Popen | None = None
    deferred = False
    try:
        while True:
            L.beat("headless")
            if child is not None and child.poll() is not None:
                if child.returncode:
                    log.warning("lyrics helper exited with code %s", child.returncode)
                say("  models released, GPU free.")
                child = None
            studio = L.alive("studio")
            if child is None and L.candidates():
                if studio:
                    if not deferred:
                        say("  Subtitle Studio is open - it's doing the songs.")
                    deferred = True
                else:
                    deferred = False
                    child = subprocess.Popen(
                        [sys.executable, str(ROOT / "lyrics.py"), "--worker"], cwd=str(ROOT),
                        env={**os.environ, "SS_LYRICS_OWNER": f"headless {me}"})
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        if child is not None and child.poll() is None:
            child.terminate()


def worker() -> None:
    setup_log(rotate=False)
    owner = os.environ.get("SS_LYRICS_OWNER") or f"headless {os.getppid()}"
    L.run_worker(owner, idle_exit=180, say=say)


def once(path: str) -> int:
    setup_log(rotate=False)
    p = Path(path).resolve()
    if not p.is_file():
        print(f"not found: {p}")
        return 2
    from studio.asr import ASR
    last = [""]

    def report(f: float, m: str = "") -> None:
        if m and m != last[0]:
            last[0] = m
            print(f"  {int(f * 100):3d}%  {m}", file=sys.stderr, flush=True)

    r = L.transcribe_file(ASR(), p, L.hints_for(p), report)
    L.finish(p, r)
    sys.stdout.write(p.with_suffix(".txt").read_text("utf-8"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Subtitle Studio - Lyrics inbox")
    ap.add_argument("file", nargs="?", help="do this one file now and print its lyrics")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        worker()
        return 0
    if a.file:
        return once(a.file)
    watch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
