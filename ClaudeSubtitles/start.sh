#!/usr/bin/env bash
# Subtitle Animator launcher (macOS / Linux)
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "Python 3 isn't installed or isn't on your PATH."
  echo "macOS:  brew install python"
  echo "Linux:  sudo apt install python3"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 && [ ! -x ./bin/ffmpeg ]; then
  echo "Heads up: ffmpeg not found, so .mov export is disabled."
  echo "PNG sequence export still works."
  echo "  macOS:  brew install ffmpeg"
  echo "  Linux:  sudo apt install ffmpeg"
  echo
fi

exec "$PY" server.py "$@"
