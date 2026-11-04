#!/usr/bin/env python3
"""
============================================================================
 Subtitle Animator — local server + export pipeline
----------------------------------------------------------------------------
 Serves the browser UI and turns the canvas frames it sends back into a
 transparent .mov (ProRes 4444) via ffmpeg.

 Standard library only. No pip install required.

   python server.py                 # launch, opens your browser
   python server.py --port 9000     # different port
   python server.py --no-browser    # don't auto-open

 Why frames come from the browser: the animation engine lives in JavaScript
 and is used by BOTH the preview and the export, so there is exactly one
 renderer and the preview is guaranteed to match the file byte for byte.
============================================================================
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"
OUT_DIR = ROOT / "output"
FONT_DIR = ROOT / "fonts"
BIN_DIR = ROOT / "bin"

OUT_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------- ffmpeg ----

def find_ffmpeg():
    """PATH first, then a local bin/ drop, then the usual Windows install spots."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    names = ["ffmpeg.exe", "ffmpeg"]
    candidates = [BIN_DIR / n for n in names]
    candidates += [
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe")),
        Path("/usr/bin/ffmpeg"), Path("/usr/local/bin/ffmpeg"), Path("/opt/homebrew/bin/ffmpeg"),
    ]
    for c in candidates:
        try:
            if c.is_file():
                return str(c)
        except OSError:
            pass
    return None


FFMPEG = find_ffmpeg()


# Encoder recipes. yuva444p10le is the pixel format that actually carries the
# alpha channel through ProRes — without it you get an opaque black matte.
CODECS = {
    "prores4444": dict(
        label="ProRes 4444 (recommended)",
        ext=".mov",
        args=["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
              "-alpha_bits", "16", "-vendor", "apl0", "-qscale:v", "9"],
    ),
    "prores4444xq": dict(
        label="ProRes 4444 XQ (max quality, big files)",
        ext=".mov",
        args=["-c:v", "prores_ks", "-profile:v", "5", "-pix_fmt", "yuva444p10le",
              "-alpha_bits", "16", "-vendor", "apl0", "-qscale:v", "5"],
    ),
    "qtrle": dict(
        label="QuickTime Animation (lossless, huge files)",
        ext=".mov",
        args=["-c:v", "qtrle", "-pix_fmt", "argb"],
    ),
    # Deliberately no WebM/VP9 option: most ffmpeg builds silently drop the
    # alpha channel on libvpx-vp9, and After Effects doesn't import WebM well
    # anyway. A format that quietly loses transparency is worse than no format.
    "png": dict(label="PNG sequence (no ffmpeg needed)", ext="", args=None),
}


def safe_name(s):
    s = re.sub(r"[^\w\-. ]+", "_", (s or "subtitle").strip())
    s = re.sub(r"\s+", "_", s)
    return (s or "subtitle")[:60]


def unique_path(base: Path):
    if not base.exists():
        return base
    stem, suf = base.stem, base.suffix
    i = 2
    while True:
        p = base.with_name(f"{stem}_{i}{suf}")
        if not p.exists():
            return p
        i += 1


# --------------------------------------------------------------- sessions --

class ExportSession:
    """Buffers incoming frames and flushes them to ffmpeg strictly in order."""

    def __init__(self, opts):
        self.id = uuid.uuid4().hex[:12]
        self.opts = opts
        self.total = int(opts.get("frames", 0))
        self.codec = opts.get("codec", "prores4444")
        self.fps = float(opts.get("fps", 30))
        self.lock = threading.Lock()
        self.next_index = 0
        self.pending = {}
        self.received = 0
        self.proc = None
        self.err_tail = []
        self.out_path = None
        self.png_dir = None
        self.failed = None
        self.started = time.time()

        spec = CODECS.get(self.codec, CODECS["prores4444"])
        name = safe_name(opts.get("name"))

        if self.codec == "png":
            self.png_dir = unique_path(OUT_DIR / name)
            self.png_dir.mkdir(parents=True, exist_ok=True)
            self.out_path = self.png_dir
            return

        if not FFMPEG:
            self.failed = "ffmpeg not found"
            return

        self.out_path = unique_path(OUT_DIR / (name + spec["ext"]))
        cmd = [
            FFMPEG, "-y",
            "-f", "image2pipe", "-framerate", f"{self.fps}", "-c:v", "png", "-i", "-",
            *spec["args"],
            "-r", f"{self.fps}",
            str(self.out_path),
        ]
        self.cmd = cmd
        try:
            self.proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
            )
        except Exception as e:  # noqa: BLE001
            self.failed = f"could not start ffmpeg: {e}"
            return

        self._drain = threading.Thread(target=self._drain_stderr, daemon=True)
        self._drain.start()

    def _drain_stderr(self):
        try:
            for line in self.proc.stderr:
                txt = line.decode("utf-8", "replace").rstrip()
                self.err_tail.append(txt)
                if len(self.err_tail) > 40:
                    self.err_tail.pop(0)
        except Exception:  # noqa: BLE001
            pass

    def add_frame(self, index, data):
        with self.lock:
            if self.failed:
                return False
            self.pending[index] = data
            self.received += 1
            while self.next_index in self.pending:
                chunk = self.pending.pop(self.next_index)
                try:
                    if self.codec == "png":
                        (self.png_dir / f"frame_{self.next_index:05d}.png").write_bytes(chunk)
                    else:
                        self.proc.stdin.write(chunk)
                except Exception as e:  # noqa: BLE001
                    self.failed = f"write failed at frame {self.next_index}: {e}"
                    return False
                self.next_index += 1
            return True

    def finish(self):
        with self.lock:
            if self.codec == "png":
                return dict(ok=self.failed is None, path=str(self.png_dir),
                            frames=self.next_index, error=self.failed)
            if self.proc is None:
                return dict(ok=False, error=self.failed or "no encoder process")
            try:
                self.proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            code = self.proc.wait(timeout=300)
            ok = code == 0 and self.failed is None and self.out_path.exists()
            return dict(
                ok=ok,
                path=str(self.out_path),
                frames=self.next_index,
                error=self.failed or (None if ok else f"ffmpeg exited {code}"),
                log="\n".join(self.err_tail[-14:]),
                size=self.out_path.stat().st_size if self.out_path.exists() else 0,
            )

    def cancel(self):
        with self.lock:
            try:
                if self.proc:
                    self.proc.stdin.close()
                    self.proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            try:
                if self.out_path and self.codec != "png" and Path(self.out_path).exists():
                    Path(self.out_path).unlink()
            except Exception:  # noqa: BLE001
                pass


SESSIONS = {}

MIME = {
    ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon",
    ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "SubtitleAnimator/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # keep the console clean; errors are surfaced in the UI

    # ---------------------------------------------------------- helpers ----
    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        buf = bytearray()
        while len(buf) < n:
            chunk = self.rfile.read(min(65536, n - len(buf)))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    # -------------------------------------------------------------- GET ----
    def do_GET(self):
        u = urlparse(self.path)
        path = u.path

        if path == "/api/env":
            local_fonts = FONT_DIR / "fonts.css"
            return self._json(dict(
                ffmpeg=bool(FFMPEG),
                ffmpegPath=FFMPEG or "",
                outputDir=str(OUT_DIR),
                localFonts=local_fonts.is_file(),
                codecs={k: v["label"] for k, v in CODECS.items()},
                platform=sys.platform,
            ))

        if path == "/":
            path = "/app/index.html"
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")

        rel = path.lstrip("/")
        target = (ROOT / rel).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            return self._send(403, b"forbidden", "text/plain")
        if not target.is_file():
            return self._send(404, b"not found", "text/plain")

        ctype = MIME.get(target.suffix.lower(), "application/octet-stream")
        return self._send(200, target.read_bytes(), ctype)

    def do_HEAD(self):
        self.do_GET()

    # ------------------------------------------------------------- POST ----
    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path

        if path == "/api/export/start":
            opts = json.loads(self._body() or b"{}")
            if opts.get("codec") != "png" and not FFMPEG:
                return self._json(dict(ok=False, error="ffmpeg-missing"), 200)
            s = ExportSession(opts)
            if s.failed:
                return self._json(dict(ok=False, error=s.failed), 200)
            SESSIONS[s.id] = s
            return self._json(dict(ok=True, id=s.id, path=str(s.out_path)))

        if path == "/api/export/frame":
            sid = (q.get("id") or [""])[0]
            idx = int((q.get("n") or ["0"])[0])
            s = SESSIONS.get(sid)
            data = self._body()
            if not s:
                return self._json(dict(ok=False, error="no such export session"), 404)
            ok = s.add_frame(idx, data)
            return self._json(dict(ok=ok, written=s.next_index, error=s.failed))

        if path == "/api/export/finish":
            sid = (q.get("id") or [""])[0]
            s = SESSIONS.pop(sid, None)
            if not s:
                return self._json(dict(ok=False, error="no such export session"), 404)
            return self._json(s.finish())

        if path == "/api/export/cancel":
            sid = (q.get("id") or [""])[0]
            s = SESSIONS.pop(sid, None)
            if s:
                s.cancel()
            return self._json(dict(ok=True))

        if path == "/api/open":
            target = OUT_DIR
            try:
                if os.name == "nt":
                    os.startfile(str(target))  # noqa: S606
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(target)])
                else:
                    subprocess.Popen(["xdg-open", str(target)])
                return self._json(dict(ok=True))
            except Exception as e:  # noqa: BLE001
                return self._json(dict(ok=False, error=str(e)))

        return self._json(dict(ok=False, error="unknown endpoint"), 404)


def free_port(preferred):
    for p in [preferred] + list(range(preferred + 1, preferred + 25)):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return preferred


def main():
    ap = argparse.ArgumentParser(description="Subtitle Animator local server")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    port = free_port(a.port)
    url = f"http://127.0.0.1:{port}/"

    bar = "=" * 66
    print(bar)
    print("  SUBTITLE ANIMATOR")
    print(bar)
    print(f"  Open:    {url}")
    print(f"  Output:  {OUT_DIR}")
    if FFMPEG:
        print(f"  ffmpeg:  {FFMPEG}")
    else:
        print("  ffmpeg:  NOT FOUND  ->  .mov export disabled")
        print("           PNG sequence export still works.")
        print("           Install with:  winget install Gyan.FFmpeg")
        print("           ...or drop ffmpeg.exe into the bin/ folder here.")
    print(bar)
    print("  Leave this window open while you work. Ctrl+C to quit.")
    print()

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
