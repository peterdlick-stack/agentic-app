# Context DJ validation tools

Task-specific helpers for PLAN G0–G5 on 泛舟's Windows + WSL machine. They reuse existing binaries and are pinned to the inspected local paths; they do not bootstrap a new machine or build OctoSense. Reports, captures, downloaded APKs and private credentials are not part of this branch.

All output is under `F:\context-dj-work` (`/mnt/f/context-dj-work` in WSL). Do not edit `bundle/`, push `main`, compile inside WSL, install SDK/NDK, or read credential file contents. Scripts reference existing credential locations only where the native application needs them. Test signing keys are handled only by the existing hub CLI; never inspect them.

## Disk checks

```powershell
python F:\context-dj-work\repo\tools\disk-guard.py
```

Requires the task's G0 evidence. Stops if C has less than 5 GiB free or loses over 1 GiB relative to the recorded baseline. A recovery baseline is valid only after explicit human approval; the 2026-10-05 incident and approval remain in the local reports. Do not reset it automatically when the OS grows its paging file. Check disk before and after longer commands, since a preflight cannot prevent concurrent OS growth.

## G1: existing WSL desktop

`g1-prepare.sh` is a one-time local mirror rehearsal for app commit `46f0f33`. It requires an already exported LF deployment copy at `octosense-data/release-lf/bundle`, and refuses an existing catalog. It signs only that deployment copy. Do not rerun it against the existing completed evidence.

`g1-launch.sh` starts the existing desktop with app state/cache/temp/captures on F. It uses the native model service and disables the unrelated agent kernel. Start it from a hidden Windows process with new F-drive stdout/stderr files. It does not configure a model or collect keys.

```powershell
wsl -d Ubuntu -- bash /mnt/f/context-dj-work/repo/tools/g1-launch.sh
wsl -d Ubuntu -- python3 /mnt/f/context-dj-work/repo/tools/g1-remote.py observe UNIQUE-NAME
```

The remote helper supports `click`, `type` (base64 UTF-8), `key`, `keys`, `scroll`, `wait` and `observe`. Coordinates must come from the current snapshot or screenshot. Every evidence name must be new. Clicking Recommend or AI tags makes a real model call; observation does not. Judge success from the real rendered playlist/understood, not service registration or a local fallback.

Stop the test instance:

```powershell
wsl -d Ubuntu -- curl --max-time 5 -sS http://127.0.0.1:8399/quit
```

## G2: existing Windows adb

`g2-adb.py` uses existing adb on private port 5038 and redirects host temp/log files to F. It requires `evidence/G2-phone/timer.json` containing the authorized 90-minute deadline; that expired historical timer must not be reset without a new authorized investigation. A single authorized device is bound locally; later calls use that exact serial without printing it in the helper summary. Names cannot be reused. A command timeout means inspect state before retrying an installation.

```powershell
python F:\context-dj-work\repo\tools\g2-adb.py UNIQUE-NAME devices -l
python F:\context-dj-work\repo\tools\g2-adb.py UNIQUE-SCREEN exec-out screencap -p
python F:\context-dj-work\repo\tools\g2-adb.py UNIQUE-STOP kill-server
```

No APK compilation or SDK installation. Stop only this task's server, not unrelated adb processes. The official installed APKs remain on the phone.

## G3 and G4

`g3-network.py` makes exactly three bounded curl requests, one second apart, and stores metrics, errors, complete bodies and the first 500 characters. Run it once on Windows and once in WSL, under the task's 30-minute `G3-net/timer.json`. It refuses existing response bodies. No DNS/proxy/certificate changes.

`g4-inspect-audio.sh` only reads the existing runtime/harness sources into G4 evidence and refuses an existing capture. The issue is a local draft for the human to submit; none of these tools submit it.

## G5: daily byte-for-byte snapshot

Not before 2026-10-06 (UTC+8), and only after 泛舟 confirms actual usage and the source directory. The G1 test directory has no labels.json and is not proof that G5 can start.

```powershell
python F:\context-dj-work\repo\tools\g5-snapshot.py --source 'F:\PATH-TO-ACTUAL-APP\accounts\device' --real-use-confirmed --check
python F:\context-dj-work\repo\tools\g5-snapshot.py --source 'F:\PATH-TO-ACTUAL-APP\accounts\device' --real-use-confirmed
```

Replace the explicit source with the verified real-use directory (a read-only WSL UNC source is also possible). The flag records a human confirmation; it must not be supplied merely to pass a check. Only labels.json/history.json are read. Both must be JSON arrays and stable during capture. Original bytes are preserved and verified; count.txt records total lengths and hashes. Total lengths are not daily additions or independently verified real-use counts. Existing dates are never overwritten. A failed partial directory is retained for human review.

There is no background loop in these scripts. Scheduling is separate and must respect the task's F-drive-only rule and any explicit exception for Codex-managed scheduling metadata.

## Validation scope

Python syntax and shell syntax checked. G1 helpers drove real AI cases A–E; G2 installed official APKs and inspected the real device; G3 issued six actual curl requests; G4 captured source evidence. G5 safety cases used clearly marked synthetic fixtures under F:\context-dj-work\tmp, outside G5 daily evidence. No real G5 daily snapshot had been taken as of 2026-10-05.
