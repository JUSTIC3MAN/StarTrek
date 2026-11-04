#!/usr/bin/env bash
# SongMap from the Cowork device shell. One call per request; prints one line per song.
#   sm.sh                                   status (one line)
#   sm.sh [-w SECS] [-c WINFOLDER] [-l WINLYRICS] SONG...   queue and wait (default -w 170)
#        SONG = a Windows path ('A:\Music\X\Song.mp3' or a folder 'A:\Music\X'), or a file/folder under $HOME/mnt
#        -c  also copy the results to this Windows folder (repeatable)   -l  known lyrics .txt for the song
#   sm.sh -w SECS                           keep waiting for what is already queued
# Exit: 0 done, 2 failed, 3 SongMap isn't running on the PC, 4 still working (run: sm.sh -w 170)
SM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Python for the job file: the desktop app's Linux shell has python3; Claude Code on Windows (Git Bash) uses SongMap's own venv
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) PYB="$SM/venv/Scripts/python.exe"; [ -x "$PYB" ] || PYB=python;; *) PYB=python3;; esac
WAIT=170; COPY=(); LYR=""; SONGS=(); LOCAL=()
while [ $# -gt 0 ]; do
  case "$1" in
    -w) WAIT="$2"; shift 2;;
    -c) COPY+=("$2"); shift 2;;
    -l) LYR="$2"; shift 2;;
    *) if [[ "$1" =~ ^[A-Za-z]:\\ ]]; then SONGS+=("$1"); else LOCAL+=("$1"); fi; shift;;
  esac
done
st() { head -c 300 "$SM/status.txt" 2>/dev/null | tr -d '\r\n'; }
alive() { local f="$SM/.alive.watcher" g="$SM/.alive.worker" now; now=$(date +%s)
  for x in "$f" "$g"; do [ -f "$x" ] && [ $(( now - $(stat -c %Y "$x") )) -lt 30 ] && return 0; done; return 1; }
PEND="$SM/.pending_jobs"
queued=0
if [ ${#SONGS[@]} -gt 0 ]; then
  name="sm_$(date +%m%d-%H%M%S)"
  "$PYB" - "$SM/inbox/$name.json.tmp" "$LYR" "${#COPY[@]}" "${COPY[@]}" "${SONGS[@]}" <<'EOF'
import json, sys
out, lyr, nc = sys.argv[1], sys.argv[2], int(sys.argv[3])
copy, songs = sys.argv[4:4 + nc], sys.argv[4 + nc:]
items = []
for s in songs:
    if "." in s.rsplit("\\", 1)[-1]:
        items.append({"song": s, "copy_to": copy, "lyrics": lyr or None})
    else:
        items.append({"folder": s})
job = {"songs": [i for i in items if "song" in i]}
folders = [i["folder"] for i in items if "folder" in i]
if folders:
    job["folder"] = folders[0]
    job["copy_to"] = copy
open(out, "w", encoding="utf-8").write(json.dumps(job))
EOF
  mv "$SM/inbox/$name.json.tmp" "$SM/inbox/$name.json" && echo "$name" >> "$PEND" && queued=1
fi
for p in "${LOCAL[@]}"; do
  if [ -d "$p" ]; then files=("$p"/*); else files=("$p"); fi
  for f in "${files[@]}"; do
    case "${f,,}" in *.mp3|*.wav|*.flac|*.m4a|*.ogg|*.aac|*.opus) ;; *) continue;; esac
    b="$(basename "$f")"; cp "$f" "$SM/inbox/.$b.part" && mv "$SM/inbox/.$b.part" "$SM/inbox/$b" \
      && echo "${b%.*}" >> "$PEND" && queued=1
  done
done
if [ $queued -eq 0 ] && [ ! -s "$PEND" ]; then
  echo "$(st)"; alive || { echo "SongMap isn't running on the PC (start SongMap.bat)"; exit 3; }; exit 0
fi
end=$(( $(date +%s) + WAIT ))
while :; do
  left=(); out=(); fail=0
  while read -r j; do
    [ -z "$j" ] && continue
    if [ -f "$SM/jobs/done/$j.txt" ]; then out+=("$(cat "$SM/jobs/done/$j.txt")")
    elif [ -f "$SM/jobs/failed/$j.txt" ]; then out+=("$(cat "$SM/jobs/failed/$j.txt")"); fail=1
    else left+=("$j"); fi
  done < <(sort -u "$PEND" 2>/dev/null)
  if [ ${#left[@]} -eq 0 ]; then
    : > "$PEND"; printf '%s\n' "${out[@]}"; [ $fail -eq 1 ] && exit 2; exit 0
  fi
  if ! alive; then
    printf '%s\n' "${left[@]}" > "$PEND"; [ ${#out[@]} -gt 0 ] && printf '%s\n' "${out[@]}"
    echo "${#left[@]} queued - SongMap isn't running on the PC: ask Justice to double-click SongMap.bat (A:\\Ai projects\\Star Trek\\SongMap)"; exit 3
  fi
  if [ "$(date +%s)" -ge "$end" ]; then
    printf '%s\n' "${left[@]}" > "$PEND"; [ ${#out[@]} -gt 0 ] && printf '%s\n' "${out[@]}"
    echo "${#left[@]} still working - $(st). Run: sm.sh -w 170"; exit 4
  fi
  sleep 3
done
