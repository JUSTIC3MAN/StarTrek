"""SongMap self-check: GPU, Beat This!, SongFormer, the Subtitle Studio bridge, ffmpeg. Writes setup_check.txt."""
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import songmap  # noqa: E402
from smlib import models as M  # noqa: E402

lines, bad = [], 0


def say(ok: bool, what: str) -> None:
    global bad
    bad += 0 if ok else 1
    s = f"{'OK  ' if ok else 'FAIL'} {what}"
    lines.append(s)
    print("          " + s, flush=True)


def clicks(bpm: float, sec: float, sr: int = 22050) -> np.ndarray:
    y = np.zeros(int(sec * sr), dtype=np.float32)
    k = np.exp(-np.linspace(0, 40, 800)).astype(np.float32) * np.sin(np.linspace(0, 400, 800)).astype(np.float32)
    for i, t in enumerate(np.arange(0.5, sec - 0.2, 60 / bpm)):
        a = int(t * sr)
        y[a:a + 800] += k * (1.0 if i % 4 == 0 else 0.5)
    return y + 0.01 * np.random.randn(len(y)).astype(np.float32)


def main() -> int:
    try:
        import torch
        say(torch.cuda.is_available(), f"torch {torch.__version__} GPU: "
            f"{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none - would run on the CPU (slow)'}")
    except Exception as e:  # noqa: BLE001
        say(False, f"torch: {e}")
    m = M.Models()
    try:
        t = time.time()
        b, d = m.beats(clicks(120, 20), 22050)
        bpm = 60 / float(np.median(np.diff(b)))
        say(abs(bpm - 120) < 3, f"Beat This! {bpm:.1f} BPM on a 120 BPM test ({time.time() - t:.1f}s)")
    except Exception as e:  # noqa: BLE001
        say(False, f"Beat This!: {type(e).__name__}: {e}")
    try:
        t = time.time()
        segs = m.sections(np.random.randn(24000 * 40).astype(np.float32) * 0.1, 24000)
        say(bool(segs), f"SongFormer loaded and ran ({len(segs)} segments on test noise, {time.time() - t:.0f}s)")
    except Exception as e:  # noqa: BLE001
        say(False, f"SongFormer: {type(e).__name__}: {str(e)[:300]}")
    ss, py = songmap.ss_python()
    if py.is_file():
        r = subprocess.run([str(py), "-c", "import sys; sys.path.insert(0, r'%s'); "
                            "from studio import lyricsfile, media, separate, pipeline; from studio.asr import ASR; "
                            "print('ffmpeg' if media.FFMPEG else 'no-ffmpeg')" % ss],
                           cwd=str(ss), capture_output=True, text=True)
        say(r.returncode == 0, "Subtitle Studio bridge (lyrics) " + (r.stdout.strip() or r.stderr.strip()[-300:]))
    else:
        say(False, f"Subtitle Studio not found at {ss} (lyrics will be skipped)")
    say(bool(shutil.which("ffmpeg")), "ffmpeg on PATH" if shutil.which("ffmpeg") else "ffmpeg not on PATH (only needed as a fallback)")
    (ROOT / "setup_check.txt").write_text(time.strftime("%Y-%m-%d %H:%M ") + "\n".join(lines) + "\n", "utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
