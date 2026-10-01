# Code room: the MCP server, its package and its tests

One job: change what ScreenMind does, with a test that proves it. Paths are relative to the
repo root.

## Inputs

- The change request, or a `.planning/BACKLOG.md` entry with its acceptance criterion.
- Code: `server.py` (MCP tools, frame pipeline, recording state) and `screenmind/`
  (`config.py`, `density.py`, `ffmpeg.py`, `url_ingest.py`, `util.py`).
- Tests: `tests/` (pytest; `conftest.py` isolates `~/.screenmind`).
- Stable rules: `_reference/decisions.md`. Installer and launchd helpers at the root:
  `install.sh`, `new-recording-notify.sh`, `com.screenmind.new-recording-notify.plist.template`.
- Missing input: no acceptance criterion means stop and ask for one.

## Process

1. Write or change a test first; watch it fail against the old code.
2. Make the smallest change in `server.py` or `screenmind/` that passes it. Pure logic goes in
   `screenmind/` so it can be tested without ffmpeg.
3. Run `python3 -m py_compile server.py screenmind/*.py` and `.venv/bin/python -m pytest -q`.
4. For pipeline changes, run `screenmind_watch` on a real long recording and read the report.
5. Record the change in `CHANGELOG.md` under Unreleased; update `_reference/decisions.md` when
   a decision changed.

## Outputs

- Changed code in `server.py` or `screenmind/`, and tests in `tests/test_<module>.py`.
- A `CHANGELOG.md` entry. A `_reference/decisions.md` edit when a decision moved.

## Human check

Alex (or the reviewer) reads the pytest summary and, for pipeline work, the Sample density
line of a real report. Pass: suite green, the new tests fail on the old code, and the real
report shows the promised behaviour. Fail: fix and re-run; nothing merges on a red suite.
Record the pass in the commit message with the test count and the real-file result.
