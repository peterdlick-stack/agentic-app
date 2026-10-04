# Audio branch v1

Delivered pilot: 48/48 processed, 47 BPM estimates, 48 unknown vocal labels, zero extraction failures; no music accuracy claim. Physical inventory contains 545 WAV files but catalog contains 544; the one orphan is recorded in `catalog_hash_check.json` and excluded. All 544 catalog hashes match original catalog SHA256 values. Full hashing took 575.16 s; final pilot took 88.36 s. Remaining 496 catalog members are unprocessed in this delivery.

`extract.py --library /mnt/f/context-player-cache-20261004/library --pilot` hashes the complete WAV files and freezes the first 48 entries in content-hash order. Run without `--pilot` only after pilot completion. It checkpoints `features.json` after each unique content. Existing side-table rows are reused, so remove nothing and use a new version directory for algorithm revisions.

Run with Python `-B`, `PYTHONDONTWRITEBYTECODE=1`, TMPDIR/TMP/TEMP/HOME/XDG_CACHE_HOME inside this audio branch, and `PYTHONPATH=/home/fanzhou/.local/lib/python3.12/site-packages` to read the installed NumPy. No FFmpeg or dependencies are installed. All JSON writes are checked against the audio branch directory. Input WAV files are opened read-only.

`python3 -B run_audio.py test` runs seven mechanism tests with captured process exit and isolated writes. Synthetic clicks establish only mechanism behavior, never accuracy on music.

The fixed estimator measures channel-averaged PCM RMS using at most three nonoverlapping 30-second intervals. RMS is dBFS, **not LUFS or perceived loudness**. Dynamic range is the sampled 95th minus 10th percentile of 10ms frame dBFS, **not standardized loudness range**. Rhythm uses positive envelope differences and normalized autocorrelation in the fixed 60–200 BPM range. Quiet/aperiodic content can abstain. Half/double-time ambiguity remains unresolved. Periodicity strength is uncalibrated, not a probability. Values above 1 may occur with lag-specific normalization.

All sample intervals and method versions are embedded per field. `vocal` always remains null because no credible model is available. The hard BPM gate is disabled. No independent manual BPM truth was supplied; sealed truth denominators, hit rate, MAE, octave-error rate and music accuracy are NOT_RUN. Valid estimate coverage is an extraction statistic only.

`manifest.json` contains full-input SHA256 content IDs, paths and byte sizes, preserving aliases. `features.json` contains one row per unique content ID. Extraction rehashes every target including reused rows and rejects changed content. This-run verified count is distinct from existing feature count; incomplete verification exits 2. Inventory checkpoints each completed file, and native stdlib `inventory_native.py` avoids slow WSL cross-filesystem hashing. Stop by interrupting only the current extraction process; completed rows survive. Each invocation budgets 1700 seconds, and the branch launcher times out at 1790 seconds.
