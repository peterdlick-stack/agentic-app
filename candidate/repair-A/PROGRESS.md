# A progress
Read frozen interfaces. Original initializer leaks a live SQLite handle on PRAGMA/schema failure; regression holds traceback to avoid a GC-dependent false pass.
Resource RED exit1 (2 failures /3); minimal exception-close repair GREEN exit0 (3/3). Native temp/symlink/SQLite and pinned imports probes pass. Outside open/sqlite/symlink negative controls rejected; SQLite URI explicitly rejected. Main notified environment ready for original34.
Added requested interactive=True path, same child env/guard, actual child exit0. A review of B real rank confirms counterexample fixed without weight change, 23 tests exit0.
