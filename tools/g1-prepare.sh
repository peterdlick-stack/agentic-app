#!/usr/bin/env bash
set -euo pipefail
# Local rehearsal only. Never stamps or signs the source bundle.
ROOT=/mnt/f/context-dj-work
python3 "$ROOT/repo/tools/disk-guard.py"
HUB=/home/fanzhou/octosense-ws/OctoSense-App-Hub/target/release/hub
OUT="$ROOT/evidence/G1-ai"
BUNDLE="$ROOT/octosense-data/release-lf/bundle"
test "$(df -B1 --output=avail /mnt/c | tail -1)" -ge 5368709120
test ! -e "$ROOT/mirror/catalog.json"
umask 077
"$HUB" check "$BUNDLE" --allow-unsigned > "$OUT/hub-check-deploy.txt" 2>&1
# keygen returns only the PUBLIC half; private files are never opened by this script.
if test ! -e "$ROOT/mirror/keys/anchor.key"; then
  "$HUB" keygen "$ROOT/mirror/keys/anchor.key" > "$ROOT/mirror/anchor-public.txt"
fi
anchor=$(cat "$ROOT/mirror/anchor-public.txt")
if test ! -e "$ROOT/mirror/keys/working.key"; then
  "$HUB" keygen "$ROOT/mirror/keys/working.key" >/dev/null
fi
if test ! -e "$ROOT/mirror/keys/publisher.key"; then
  "$HUB" keygen "$ROOT/mirror/keys/publisher.key" > "$ROOT/mirror/publisher-public.txt"
fi
publisher=$(cat "$ROOT/mirror/publisher-public.txt")
cert=$("$HUB" certify --anchor "$ROOT/mirror/keys/anchor.key" --working "$ROOT/mirror/keys/working.key")
printf '%s\n' "$anchor" > "$ROOT/mirror/anchor-public.txt"
# Only the exported deployment copy is signed; repo/bundle stays untouched.
"$HUB" sign-manifest "$BUNDLE" --key "$ROOT/mirror/keys/publisher.key" \
  --key-id context-dj-local-rehearsal > "$OUT/hub-sign-deployment.txt" 2>&1
"$HUB" publish "$BUNDLE" --catalog "$ROOT/mirror/catalog.json" \
  --key "$ROOT/mirror/keys/working.key" --anchor-cert "$cert" \
  --publisher context-dj-local-rehearsal \
  --publisher-key "context-dj-local-rehearsal=$publisher" \
  --repo https://github.com/peterdlick-stack/agentic-app \
  --commit 46f0f3301c2485a98ca2a4f906ea83c6722067da --out "$ROOT/mirror" \
  > "$OUT/hub-publish.txt" 2>&1
"$HUB" verify "$ROOT/mirror/catalog.json" --anchor "$anchor" > "$OUT/hub-verify.txt" 2>&1
mkdir -p "$ROOT/octosense-data/core/profiles" "$ROOT/octosense-data/home" \
  "$ROOT/octosense-data/apps" "$ROOT/octosense-data/cache" "$ROOT/tmp/g1"
# Credentials remain in their existing location; never copy them into this tree.
