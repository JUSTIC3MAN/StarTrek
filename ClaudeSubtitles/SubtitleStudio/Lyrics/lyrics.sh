#!/usr/bin/env bash
# Subtitle Studio - Lyrics inbox, one-call interface (for Claude, or any shell).
#
#   lyrics.sh SONG.mp3       put SONG in the inbox if needed, wait, print its lyrics
#   lyrics.sh FOLDER         every song in FOLDER: lyrics saved beside each as <song>.txt;
#                            prints one summary line, never the lyrics
#   lyrics.sh -t SONG.mp3    print the timed .lrc instead
#   lyrics.sh -w 170 ...     wait up to 170 s (default 110). Not finished? Run it again: it resumes.
#   lyrics.sh                status: is the PC side up, what's queued / working / done
#
# Exit: 0 finished, 2 failed (reason printed), 3 PC side not running, 4 still working.
set -u
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAIT=110
LRC=0
while getopts "htw:" o; do
  case $o in t) LRC=1 ;; w) WAIT=$OPTARG ;; h) sed -n '2,12p' "$0" | cut -c3-; exit 0 ;; *) exit 64 ;; esac
done
shift $((OPTIND - 1))
shopt -s nullglob

alive() {   # alive studio|headless -> fresh heartbeat?
  local t
  [ -f "$D/.alive.$1" ] || return 1
  read -r t _ <"$D/.alive.$1" 2>/dev/null || return 1
  [ -n "${t:-}" ] && [ $(($(date +%s) - ${t%.*})) -lt 20 ]
}
running() {
  if alive studio; then echo "Subtitle Studio"; elif alive headless; then echo "Lyrics.bat"; else return 1; fi
}
NOT_RUNNING="the PC side isn't running. Start Lyrics.bat (or Subtitle Studio) on the PC, then run this again."
progress() { head -1 "$1" 2>/dev/null | sed -E 's/ \[[a-z]+ [0-9]+\][[:space:]]*$//'; }
is_audio() {
  case "${1,,}" in
    *.mp3 | *.wav | *.m4a | *.aac | *.flac | *.ogg | *.oga | *.opus | *.wma | *.aif | *.aiff | \
    *.mp4 | *.m4v | *.mov | *.mkv | *.webm | *.avi) return 0 ;;
  esac
  return 1
}
fresh() { [ -f "$1" ] && ! [ "$2" -nt "$1" ]; }   # result $1 exists and is newer than song $2
queue() {   # copy song $1 into the inbox unless the same file is already there
  local a="$D/${1##*/}"
  [ "$(cd "$(dirname "$1")" && pwd)" = "$D" ] && return 0
  [ -f "$a" ] && cmp -s "$1" "$a" && return 0
  cp -f "$1" "$a" || { echo "could not copy ${1##*/} into $D"; exit 2; }
}

# ---- status -------------------------------------------------------------
if [ $# -eq 0 ]; then
  if who=$(running); then echo "PC side: running ($who)"; else echo "PC side: NOT running - start Lyrics.bat (or Subtitle Studio) on the PC"; fi
  for a in "$D"/*; do
    [ -f "$a" ] && is_audio "$a" || continue
    b="${a%.*}"
    if [ -f "$b.working" ]; then echo "working: ${a##*/} - $(progress "$b.working")"
    elif fresh "$b.txt" "$a"; then echo "done:    ${a##*/}"
    elif fresh "$b.error.txt" "$a"; then echo "failed:  $(head -1 "$b.error.txt")"
    else echo "queued:  ${a##*/}"; fi
  done
  exit 0
fi

SRC=$1
[ -e "$SRC" ] || { [ -f "$D/$SRC" ] && SRC="$D/$SRC"; }
[ -e "$SRC" ] || { echo "not found: $1"; exit 2; }

# ---- a folder of songs: "<Song Title>.txt" (just the lyrics) saved in that folder ----
if [ -d "$SRC" ]; then
  S="$(cd "$SRC" && pwd)"
  songs=()
  for f in "$S"/*; do [ -f "$f" ] && is_audio "$f" && songs+=("$f"); done
  n=${#songs[@]}
  [ "$n" -gt 0 ] || { echo "no songs in $S"; exit 2; }
  for f in "${songs[@]}"; do queue "$f"; done
  end=$((SECONDS + WAIT))
  while :; do
    ok=0; bad=0; now=""; failed=""
    for f in "${songs[@]}"; do
      a="$D/${f##*/}"; b="${a%.*}"
      if fresh "$b.txt" "$a"; then
        t="$S/$(head -1 "$b.txt" | tr -d '\r' | tr '/\\:*?"<>|' '-').txt"
        fresh "$t" "$b.txt" || tail -n +2 "$b.txt" | sed '1{/^Artist: /d}' | sed '/./,$!d' >"$t"
        ok=$((ok + 1))
      elif fresh "$b.error.txt" "$a"; then bad=$((bad + 1)); failed+=$'\n'"  $(head -1 "$b.error.txt")"
      elif [ -f "$b.working" ]; then now="${f##*/} ($(progress "$b.working"))"
      fi
    done
    left=$((n - ok - bad))
    if [ $left -eq 0 ]; then
      echo "$ok/$n done - lyrics saved as <song title>.txt in $S"
      [ $bad -gt 0 ] && { echo "$bad failed:$failed"; exit 2; }
      exit 0
    fi
    running >/dev/null || { echo "$ok/$n done, $left waiting - $NOT_RUNNING"; exit 3; }
    if [ $SECONDS -ge $end ]; then
      echo "$ok/$n done, $left to go${now:+ - now: $now}. Run the same command again to keep waiting."
      exit 4
    fi
    sleep 3
  done
fi

# ---- one song -------------------------------------------------------------
is_audio "$SRC" || { echo "not an audio/video file: ${SRC##*/}"; exit 2; }
queue "$SRC"
A="$D/${SRC##*/}"
B="${A%.*}"
OUT="$B.txt"
[ "$LRC" = 1 ] && OUT="$B.lrc"
end=$((SECONDS + WAIT))
while :; do
  if fresh "$B.txt" "$A"; then cat "$OUT"; exit 0; fi
  if fresh "$B.error.txt" "$A"; then cat "$B.error.txt"; exit 2; fi
  running >/dev/null || { echo "${A##*/} is in the inbox, but $NOT_RUNNING"; exit 3; }
  if [ $SECONDS -ge $end ]; then
    if [ -f "$B.working" ]; then echo "Still working on ${A##*/} ($(progress "$B.working")) - run the same command again to keep waiting."
    else echo "${A##*/} is queued; the PC hasn't started it yet. Run the same command again to keep waiting."; fi
    exit 4
  fi
  sleep 2
done
