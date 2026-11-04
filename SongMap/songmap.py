#!/usr/bin/env python3
"""SongMap - song file -> timing sheet for FilmCraft edits: beats, bars, BPM, sections, lyrics on timestamps,
musical changes and rhymes. All on the local GPU; Claude only reads the finished text sheet.

  SongMap.bat                       start (first run installs everything); drag songs onto it to queue them
  python songmap.py                 the inbox watcher (light; starts the worker when songs arrive)
  python songmap.py --add <paths>   queue songs or folders
  python songmap.py --once <song>   do one song in this window (testing)
  python songmap.py --worker        internal: does the queued work, exits when idle so the GPU is free

Inbox (inbox\\): drop a song (.mp3 .wav .flac .m4a ...) or a .json job:
  {"song": "A:\\\\Music\\\\X\\\\Song.mp3", "lyrics": "known lyrics .txt (optional)", "copy_to": ["folder"]}
  {"songs": [ "path", {"song": ...}, ... ]}        {"folder": "A:\\\\Music\\\\X"}
Results: out\\<song>\\<song>.songmap.txt (+ .songmap.json, .lyrics.txt, .lrc, .srt, _done.txt), also copied into
FilmCraft\\projects\\<song>\\ when that project exists, and into every copy_to folder.
One line per job lands in jobs\\done\\<job>.txt (or jobs\\failed\\). status.txt is always one line.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INBOX, OUT, WORK, JOBS, LOGS = (ROOT / d for d in ("inbox", "out", "work", "jobs", "logs"))
AUDIO = (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".opus", ".wma", ".aiff", ".aif")
DEFAULTS = {
    "subtitle_studio": r"..\ClaudeSubtitles\SubtitleStudio",
    "filmcraft_projects": r"..\FilmCraft\projects",
    "comfort": r"..\Comfort",
    "comfyui_url": "http://127.0.0.1:8188",
    "free_comfyui_vram": True,
    "wait_for_comfort_minutes": 15,
    "fps": 60,
    "beat_checkpoint": "final0",
    "songformer_repo": "ASLP-lab/SongFormer",
    "idle_exit_seconds": 180,
}


def load_cfg() -> dict:
    c = dict(DEFAULTS)
    try:
        c.update(json.loads((ROOT / "config.json").read_text("utf-8-sig")))
    except (OSError, ValueError):
        pass
    return c


CFG = load_cfg()


def rel(p: str) -> Path:
    q = Path(p if os.name == "nt" else str(p).replace("\\", "/"))
    return (q if q.is_absolute() else ROOT / q).resolve()


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        LOGS.mkdir(exist_ok=True)
        with open(LOGS / "songmap.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def status(msg: str) -> None:
    for _ in range(10):
        try:
            (ROOT / "status.txt").write_text(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n", "utf-8")
            return
        except OSError:
            time.sleep(0.2)


def heartbeat(kind: str) -> None:
    try:
        (ROOT / f".alive.{kind}").write_text(f"{time.time():.0f} {os.getpid()}", "utf-8")
    except OSError:
        pass


def is_alive(kind: str, max_age: float = 20) -> bool:
    try:
        ts, pid = (ROOT / f".alive.{kind}").read_text("utf-8").split()
        return time.time() - float(ts) < max_age
    except (OSError, ValueError):
        return False


def safe(name: str) -> str:
    s = re.sub(r"\s*[\[(](official|lyrics?|video|audio|visualizer|prod)[^\])]*[\])]", "", name, flags=re.I)
    s = re.sub(r"\s*\[[A-Za-z0-9_-]{8,}\]", "", s)              # [youtubeID]
    s = re.sub(r'[<>:"/\\|?*]+', "", s).strip(" .-_")
    return s or "song"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def dirs() -> None:
    for d in (INBOX, OUT, WORK, JOBS / "done", JOBS / "failed", LOGS):
        d.mkdir(parents=True, exist_ok=True)


# ===================================================================== jobs ===
def expand(data, base: Path | None = None) -> list[dict]:
    """Job JSON -> song dicts {src, lyrics, copy_to}."""
    songs: list[dict] = []
    if isinstance(data, str):
        data = {"song": data}
    if isinstance(data, list):
        data = {"songs": data}
    common = {"copy_to": data.get("copy_to") or [], "lyrics": data.get("lyrics")}
    items = []
    if data.get("song"):
        items.append(data)
    for s in data.get("songs") or []:
        items.append({"song": s} if isinstance(s, str) else s)
    if data.get("folder"):
        fd = Path(data["folder"])
        for f in sorted(fd.iterdir()) if fd.is_dir() else []:
            if f.suffix.lower() in AUDIO:
                items.append({"song": str(f), "copy_to": common["copy_to"]})
    for it in items:
        p = Path(it["song"])
        if not p.is_absolute() and base:
            p = base / p
        songs.append({"src": str(p), "lyrics": it.get("lyrics") or (common["lyrics"] if len(items) == 1 else None),
                      "copy_to": list(it.get("copy_to") or common["copy_to"]),
                      "title": it.get("title"), "artist": it.get("artist")})
    return songs


def take_inbox() -> list[dict]:
    jobs = []
    for f in sorted(INBOX.iterdir()):
        if not f.is_file() or f.name.startswith(("_", ".")):
            continue
        ext = f.suffix.lower()
        if ext not in AUDIO and ext != ".json":
            continue
        try:
            if time.time() - f.stat().st_mtime < 2:       # still being copied in
                continue
        except OSError:
            continue
        jid = time.strftime("%m%d-%H%M%S") + "_" + slug(f.stem)[:40]
        jdir = WORK / jid
        jdir.mkdir(parents=True, exist_ok=True)
        try:
            if ext in AUDIO:
                dst = jdir / f.name
                shutil.move(str(f), dst)
                jobs.append({"id": jid, "name": f.stem, "songs": [{"src": str(dst), "dropped": True, "copy_to": []}]})
            else:
                data = json.loads(f.read_text("utf-8-sig"))
                shutil.move(str(f), jdir / "job.json")
                jobs.append({"id": jid, "name": f.stem, "songs": expand(data)})
        except Exception as e:  # noqa: BLE001
            finish_job({"id": jid, "name": f.stem, "songs": []}, [f"FAILED {f.name}: {e}"], False)
            try:
                shutil.move(str(f), JOBS / "failed" / f.name)
            except OSError:
                pass
    return jobs


def finish_job(job: dict, lines: list[str], ok: bool) -> None:
    d = JOBS / ("done" if ok else "failed")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{job['name']}.txt").write_text("\n".join(lines) + "\n", "utf-8")


# ================================================================ the work ===
def comfort_busy() -> str:
    try:
        s = (rel(CFG["comfort"]) / "status.txt").read_text("utf-8", errors="replace")
        return s.strip() if "running" in s else ""
    except OSError:
        return ""


def free_comfyui() -> None:
    if not CFG.get("free_comfyui_vram"):
        return
    try:
        req = urllib.request.Request(CFG["comfyui_url"].rstrip("/") + "/free", method="POST",
                                     data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3).read()
        log("asked ComfyUI to unload its models (GPU memory for SongMap)")
    except Exception:  # noqa: BLE001
        pass


def ss_python() -> tuple[Path, Path]:
    ss = rel(CFG["subtitle_studio"])
    py = ss / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return ss, py


def decode_mix(src: Path, dst: Path) -> None:
    """Fallback when Subtitle Studio isn't there: our own decode to 44.1 kHz stereo WAV."""
    try:
        import soundfile as sf
        y, sr = sf.read(str(src), dtype="float32", always_2d=True)
        sf.write(str(dst), y, sr)
        return
    except Exception:  # noqa: BLE001
        pass
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "2", "-ar", "44100", str(dst)],
                       capture_output=True, text=True)
    if r.returncode or not dst.is_file():
        raise RuntimeError("could not read the audio: " + (r.stderr or "")[-200:])


def run_lyrics(songs: list[dict], tag: str) -> None:
    ss, py = ss_python()
    t0 = time.time()
    if not py.is_file():
        for s in songs:
            s["lyrics_note"] = f"Subtitle Studio not found at {ss}"
        return
    batch = WORK / f"lyrics_{tag}.json"
    batch.write_text(json.dumps([{"src": s["src"], "work": str(s["work"]), "stem": s["stem"], "lyrics": s.get("lyrics")}
                                 for s in songs]), "utf-8")
    logf = open(LOGS / f"lyrics_{tag}.log", "w", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = {k: v for k, v in os.environ.items()          # Subtitle Studio must use its own model cache,
           if k not in ("HF_HOME", "TORCH_HOME", "HF_HUB_CACHE", "TRANSFORMERS_CACHE", "SONGFORMER_LOCAL_DIR")}
    proc = subprocess.Popen([str(py), str(ROOT / "sm_lyrics.py"), str(ss), str(batch), str(LOGS / f"lyrics_{tag}.detail.log")],
                            cwd=str(ss), env=env,
                            stdout=logf, stderr=subprocess.STDOUT, creationflags=flags)
    limit = 300 + 240 * len(songs)
    while proc.poll() is None:
        heartbeat("worker")
        for i, s in enumerate(songs, 1):
            pf = s["work"] / "progress.txt"
            if pf.is_file() and not (s["work"] / "lyrics.json").is_file():
                try:
                    status(f"working {s['stem']} ({i}/{len(songs)}) - lyrics {pf.read_text('utf-8').strip()}")
                except OSError:
                    pass
                break
        if time.time() - t0 > limit:
            proc.kill()
            log("lyrics step took too long and was stopped")
            break
        time.sleep(1)
    logf.close()
    per = (time.time() - t0) / max(1, len(songs))
    for s in songs:
        s["lyrics_seconds"] = per
        err = s["work"] / "lyrics_error.txt"
        if err.is_file():
            s["lyrics_note"] = err.read_text("utf-8", errors="replace").splitlines()[0][:160]


def match_project(stem: str, title: str = "") -> Path | None:
    """FilmCraft project for this song: projects\\<slug>, matched on the file name or the song title."""
    root = rel(CFG["filmcraft_projects"])
    if not root.is_dir():
        return None
    names = [slug(x) for x in (title, stem) if x]
    best = None
    for d in root.iterdir():
        if not d.is_dir():
            continue
        p = slug(d.name)
        if p and any(n == p or re.search(rf"(^|_){re.escape(p)}(_|$)", n) for n in names):
            if best is None or len(p) > len(slug(best.name)):
                best = d
    return best


def deliver(s: dict, sheet: Path) -> list[str]:
    """Copy the results to the FilmCraft project (if one matches) and the copy_to folders."""
    files = [sheet, sheet.with_suffix(".json")] + [s["out"] / f"{s['stem']}{x}" for x in (".lyrics.txt", ".lrc", ".srt")]
    targets = [Path(p) for p in s.get("copy_to") or []]
    fc = match_project(s["stem"], s.get("title_found", ""))
    if fc:
        targets.append(fc)
    done = []
    for t in targets:
        try:
            t.mkdir(parents=True, exist_ok=True)
            for f in files:
                if f.is_file():
                    shutil.copy2(f, t / f.name)
            done.append(str(t))
        except OSError as e:
            log(f"copy to {t} failed: {e}")
    return done


def do_song(s: dict, models) -> str:
    from smlib import analyze as A
    work, out = s["work"], s["out"]
    mix = work / "mix.wav"
    if not mix.is_file():
        decode_mix(Path(s["src"]), mix)
    lyr = None
    lj = work / "lyrics.json"
    if lj.is_file():
        lyr = json.loads(lj.read_text("utf-8"))
    title = s.get("title") or (lyr or {}).get("title") or s["stem"]
    artist = s.get("artist") or (lyr or {}).get("artist") or ""
    s["title_found"] = title
    mode = (lyr or {}).get("mode", "")
    lang = (lyr or {}).get("language", "")
    meta = {"title": title, "artist": artist, "lyrics_seconds": s.get("lyrics_seconds", 0.0),
            "lyrics_src": f"{mode}, {lang} (Subtitle Studio: Qwen3-ASR + ForcedAligner)" if lyr else "none"}
    txt, js, summary = A.run(mix, lyr, meta, models, fps=int(CFG["fps"]), lyrics_note=s.get("lyrics_note", ""))
    out.mkdir(parents=True, exist_ok=True)
    for x in (".lyrics.txt", ".lrc", ".srt"):
        f = work / f"{s['stem']}{x}"
        if f.is_file():
            shutil.copy2(f, out / f.name)
    sheet = A.write(out, s["stem"], txt, js)
    if s.get("dropped"):
        try:
            shutil.move(s["src"], out / Path(s["src"]).name)
        except OSError:
            pass
    to = deliver(s, sheet)
    secs = js["timing"]
    line = (f"OK {s['stem']} {time.time() - s['t0']:.0f}s | {summary} | {sheet}"
            + (f" | copied to {', '.join(to)}" if to else ""))
    (out / "_done.txt").write_text(line + f"\n{secs}\n", "utf-8")
    return line


class Beat(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop = False

    def run(self):
        while not self.stop:
            heartbeat("worker")
            time.sleep(2)


def run_batch(jobs: list[dict], models) -> None:
    tag = time.strftime("%m%d-%H%M%S")
    songs = []
    used: set[str] = set()
    for j in jobs:
        for s in j["songs"]:
            s["job"] = j
            s["t0"] = time.time()
            src = Path(s["src"])
            stem = safe(src.stem)
            while stem.lower() in used:
                stem += "_2"
            used.add(stem.lower())
            s["stem"] = stem
            s["work"] = WORK / j["id"] / slug(stem)
            s["out"] = OUT / stem
            s["work"].mkdir(parents=True, exist_ok=True)
            if not src.is_file():
                s["error"] = f"not found: {src}"
            if not s.get("lyrics"):                      # <song>.lyrics.txt beside the song = known lyrics
                k = src.with_name(src.stem + ".lyrics.txt")
                own = s["out"] / f"{stem}.lyrics.txt"
                try:
                    if k.is_file() and not (own.is_file() and own.read_bytes() == k.read_bytes()):
                        s["lyrics"] = str(k)
                except OSError:
                    pass
            songs.append(s)
    live = [s for s in songs if not s.get("error")]
    busy, waited = comfort_busy(), 0
    while busy and waited < CFG["wait_for_comfort_minutes"] * 60:
        status(f"waiting for Comfort to finish ({busy[20:80]})")
        time.sleep(5)
        waited += 5
        busy = comfort_busy()
    free_comfyui()
    if live:
        status(f"working {live[0]['stem']} (1/{len(live)}) - lyrics starting")
        run_lyrics(live, tag)
    for i, s in enumerate(live, 1):
        status(f"working {s['stem']} ({i}/{len(live)}) - beats, sections, sheet")
        try:
            s["line"] = do_song(s, models)
            log(s["line"])
        except Exception as e:  # noqa: BLE001
            s["error"] = f"{type(e).__name__}: {e}"
            log(f"FAILED {s['stem']}: {s['error']}\n{traceback.format_exc()}")
    for j in jobs:
        lines = [s.get("line") or f"FAILED {s.get('stem', s['src'])}: {s.get('error', 'unknown')}" for s in j["songs"]]
        ok = all(s.get("line") for s in j["songs"]) and bool(j["songs"])
        finish_job(j, lines or [f"FAILED {j['name']}: no songs in this job"], ok)
        shutil.rmtree(WORK / j["id"], ignore_errors=True)
    for f in WORK.glob(f"lyrics_{tag}.*"):
        try:
            f.unlink()
        except OSError:
            pass


def worker() -> None:
    dirs()
    sys.path.insert(0, str(ROOT))
    from smlib.models import Models
    models = Models(CFG["beat_checkpoint"], CFG["songformer_repo"])
    hb = Beat()
    hb.start()
    idle = time.time()
    try:
        while True:
            jobs = take_inbox()
            if jobs:
                run_batch(jobs, models)
                idle = time.time()
                status("idle (worker ready)")
            elif time.time() - idle > CFG["idle_exit_seconds"]:
                break
            time.sleep(1)
    finally:
        hb.stop = True
        status("idle")


def pending() -> bool:
    try:
        return any(f.is_file() and not f.name.startswith(("_", ".")) and
                   (f.suffix.lower() in AUDIO or f.suffix.lower() == ".json") for f in INBOX.iterdir())
    except OSError:
        return False


def watch() -> None:
    dirs()
    status("idle")
    print("\n   SongMap is watching its inbox:\n   " + str(INBOX) +
          "\n   Drop songs there (or onto SongMap.bat). Sheets land in out\\<song>\\. Close this window to stop.\n",
          flush=True)
    proc, hold = None, 0.0
    while True:
        heartbeat("watcher")
        if proc is not None and proc.poll() is not None:
            if proc.returncode:
                hold = time.time() + 60          # a crashing worker must not respawn in a loop
                status(f"error: the worker stopped (code {proc.returncode}) - details in logs\\songmap.log; "
                       f"retrying in 60 s")
                log(f"worker exited with code {proc.returncode}")
            proc = None
        if proc is None and time.time() > hold and pending() and not is_alive("worker", 10):
            proc = subprocess.Popen([sys.executable, str(ROOT / "songmap.py"), "--worker"], cwd=str(ROOT))
        time.sleep(1)


def add(paths: list[str]) -> None:
    dirs()
    songs = []
    for p in paths:
        q = Path(p)
        if q.is_dir():
            songs += [str(f) for f in sorted(q.iterdir()) if f.suffix.lower() in AUDIO]
        elif q.suffix.lower() in AUDIO:
            songs.append(str(q))
    if songs:
        name = time.strftime("add_%m%d-%H%M%S")
        (INBOX / f"{name}.json").write_text(json.dumps({"songs": songs}), "utf-8")
        print(f"   queued {len(songs)} song(s)")


def once(path: str) -> None:
    dirs()
    name = time.strftime("once_%m%d-%H%M%S")
    (INBOX / f"{name}.json").write_text(json.dumps({"song": str(Path(path).resolve())}), "utf-8")
    worker_once()
    print((JOBS / "done" / f"{name}.txt").read_text("utf-8") if (JOBS / "done" / f"{name}.txt").is_file()
          else (JOBS / "failed" / f"{name}.txt").read_text("utf-8"))


def worker_once() -> None:
    sys.path.insert(0, str(ROOT))
    from smlib.models import Models
    run_batch(take_inbox_now(), Models(CFG["beat_checkpoint"], CFG["songformer_repo"]))


def take_inbox_now() -> list[dict]:
    for f in INBOX.iterdir():
        try:
            os.utime(f, (time.time() - 5, time.time() - 5))
        except OSError:
            pass
    return take_inbox()


def main() -> int:
    a = sys.argv[1:]
    if a[:1] == ["--worker"]:
        try:
            worker()
        except Exception:  # noqa: BLE001
            log("worker crashed:\n" + traceback.format_exc())
            status("error: the worker crashed - details in logs\\songmap.log")
            return 1
    elif a[:1] == ["--add"]:
        add(a[1:])
    elif a[:1] == ["--once"] and len(a) > 1:
        once(a[1])
    else:
        watch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
