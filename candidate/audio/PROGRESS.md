# A branch progress

- Frozen contract v1 read before code.
- Implemented PCM streaming sample extraction, full-file SHA256 inventory, immutable content association, per-field provenance, unknown vocals, row checkpoints.
- Development iteration 1: six mechanism tests pass; no real-song accuracy assertion. Initial environment run failed because HOME relocation hid installed user-site NumPy; explicit read-only PYTHONPATH resolved it.
- First 48 content-hash pilot in progress; expand only after completion and remaining budget assessment.
- Environment interrupted initial WSL inventory before manifest existed; original process vanished and no successful exit claimed. Resume inspected no active extraction and no inventory/features checkpoint. Native existing Windows Python inventory helper now writes per-file checkpoint; WSL extraction remains unchanged.
- Second and final development iteration corrected source SHA256 binding and resume verification accounting per C review; seven guarded mechanism tests passed. Algorithm parameters unchanged.
- Native full-byte inventory completed exit 0 in 575.16 s: 545 physical WAV files. Catalog has 544; all 544 hashes match historical catalog.sha256. One orphan retained read-only and excluded from candidate; manifest_all_wav.json preserves its evidence.
- Guarded final pilot completed exit 0 in 88.36 s: first 48 content hashes, 48 verified this run, 0 failed, BPM nonnull 47, vocal unknown 48. Features remain FEATURES_ESTIMATED; accuracy NOT_RUN; hard BPM gate disabled.
- Remaining 496 catalog tracks not extracted in this run; main-agent scope decision retained pilot only. Resume command available, no copies of library.
- A reviewed B, reported two issues, verified author's fixes; audio/review-B.md records evidence. No Jev calls.
