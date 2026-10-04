# A environment / resource repair

R1 native ext4 permits a real file symlink and SQLite create/close/cleanup. This isolates the old F-drive symlink EPERM from production correctness; no Windows settings changed. The old ENOTEMPTY alone was ambiguous. A separate real corrupt database on ext4 proves an actual production leak: retaining the thrown DatabaseError traceback retains an open /proc/self/fd handle until GC. An externally injected schema execution failure also left its real sqlite3.Connection usable. Both regressions fail against the original copied initializer (red.log exit 1, 2 failures / 3 tests).

Minimal feedback.py change wraps post-connect initialization in try/except BaseException, closes the connection and rethrows. Corrupt bytes and DatabaseError remain unchanged. The same tests pass (green.log exit 0, 3 tests). No original test or fixture was edited.

Launcher sets temporary/cache variables only in child env; HOME stays /home/fanzhou. R1/tmp/launcher is the native temporary root. Guard covers R1 and E1 writes, including sqlite3.connect; SQLite URI connections are rejected because native URI interpretation could bypass pathlib validation. The write hook covers ordinary Python filesystem mutations and symlink resolution; this is not a kernel sandbox for arbitrary native executables.

CandidateFinder pins context_player package imports even when a subprocess runs in test-fixtures. Each backend/feedback spec logs pid, ppid, module, path, source SHA256, cwd and timestamp to IMPORT_AUDIT_PATH; caller may bind a per-run audit path. probe.json shows both working directories resolve to R1/integration/context_player. Python -B and dont_write_bytecode prevent source pycache.

Negative controls for outside open, SQLite connect and symlink escape all exited 1 before writing; positive temporary/symlink/SQLite/import probes exited 0. Only probe-owned temporary files were cleaned. Full 34-test execution is delegated to the main current-run acceptance driver.
