#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/f/context-dj-work
python3 "$ROOT/repo/tools/disk-guard.py"
test "$(df -B1 --output=avail /mnt/c | tail -1)" -ge 5368709120
export OCTOSENSE_HOME="$ROOT/octosense-data/home"
export OCTOSENSE_APP_DATA="$ROOT/octosense-data/apps"
export OCTOS_APP_CORE_DIR=/home/fanzhou/.octosense/octos-home/.octos
# model.complete uses the host provider service directly. The unrelated agent
# kernel is disabled here to prevent it rewriting the existing credential profile.
export OCTOS_APP_CORE_BIN="$ROOT/octosense-data/disabled-agent-kernel"
export OCTOSENSE_LLM_VAULT=file
export OCTOSENSE_HUB="$ROOT/mirror"
export OCTOSENSE_HUB_ANCHOR
OCTOSENSE_HUB_ANCHOR=$(cat "$ROOT/mirror/anchor-public.txt")
export XDG_CACHE_HOME="$ROOT/octosense-data/cache"
export TMPDIR="$ROOT/tmp/g1"
export XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir
export MAKEPAD_REMOTE=8399
export MAKEPAD_HIDE_WINDOWS=1
export MAKEPAD_WRITE_FRAMEBUFFER_PNG="$ROOT/evidence/G1-ai/live-framebuffer.png"
# The pinned Wayland backend times out on remote frame capture. Use WSLg X11.
unset WAYLAND_DISPLAY
cd "$ROOT"
exec /home/fanzhou/octosense-ws/OctoSense/target/release/octosense
