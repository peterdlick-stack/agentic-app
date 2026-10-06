#!/usr/bin/env bash
set -eu
ROOT=/mnt/f/context-dj-work
OUT="$ROOT/evidence/G4-issue"
MAKEPAD=/home/fanzhou/octosense-ws/OctoSense/.sources/makepad
HARNESS=/home/fanzhou/octosense-ws/OctoScript-App-Design-Flow
python3 "$ROOT/repo/tools/disk-guard.py"
test ! -e "$OUT/local-makepad-head.txt"
git -C "$MAKEPAD" rev-parse HEAD > "$OUT/local-makepad-head.txt"
git -C "$HARNESS" rev-parse HEAD > "$OUT/local-harness-head.txt"
git -C "$MAKEPAD" show HEAD:platform/src/audio.rs > "$OUT/audio.rs"
git -C "$MAKEPAD" show HEAD:platform/src/event/event.rs > "$OUT/event.rs"
git -C "$HARNESS" show HEAD:docs/SCRIPT-API.md > "$OUT/SCRIPT-API.md"
git -C "$HARNESS" show HEAD:docs/CAPABILITIES.md > "$OUT/CAPABILITIES.md"
set +e
git -C "$MAKEPAD" grep -n -E 'audio_route|AudioDevices|"gps"' -- platform/src widgets/src > "$OUT/runtime-search.txt"
code=$?
printf 'git_grep_exit=%s\n' "$code" > "$OUT/runtime-search-status.txt"
test "$code" -le 1 || exit "$code"
git -C "$HARNESS" grep -n -i -E 'audio|bluetooth|headphone|route' -- docs/SCRIPT-API.md docs/CAPABILITIES.md > "$OUT/harness-search.txt"
code=$?
printf 'git_grep_exit=%s\n' "$code" > "$OUT/harness-search-status.txt"
test "$code" -le 1 || exit "$code"
