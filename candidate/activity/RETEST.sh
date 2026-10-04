#!/bin/sh
set -eu
R=/mnt/f/context-recommend-v1-20261004-154611/activity
cd "$R"
export TMPDIR="$R/tmp" TEMP="$R/tmp" TMP="$R/tmp" HOME="$R/home"
export XDG_CACHE_HOME="$R/tmp" XDG_CONFIG_HOME="$R/tmp" PYTHONDONTWRITEBYTECODE=1
exec timeout 1800 python3 -B "$R/run.py"
