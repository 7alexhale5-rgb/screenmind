# Contributing to ScreenMind

ScreenMind is a small, focused MCP server and easy to contribute to. Bug reports, docs fixes, and feature ideas are all welcome.

## Quick setup

```bash
git clone https://github.com/7alexhale5-rgb/screenmind.git
cd screenmind
./install.sh
pip install -r requirements-dev.txt
pytest -q
```

## Where things live

- `server.py` — MCP tool registrations, frame pipeline, recording state machine
- `screenmind/` — testable helpers split for SOLID:
  - `config.py` — config load/merge with defaults
  - `ffmpeg.py` — ffmpeg/ffprobe wrappers and frame-rate parsing
  - `url_ingest.py` — URL detection and yt-dlp download orchestration
  - `util.py` — shared utilities
- `tests/` — pytest suite, all external binaries mocked
- `docs/` — USAGE, CONFIGURATION, ARCHITECTURE, TROUBLESHOOTING, POSITIONING
- `.github/workflows/ci.yml` — CI matrix (ubuntu + macOS × Python 3.11 + 3.12)

## Running tests

```bash
pytest -q
```

The 29-test suite covers config merge, URL detection, ffmpeg frame-rate parsing, and adaptive FPS boundaries. No real ffmpeg invocation — all subprocess calls are mocked, so the suite runs fast and works in CI without media tooling installed.

## Style

`pyproject.toml` carries ruff config. If you have ruff installed, run it before opening a PR:

```bash
ruff check .
```

Otherwise default Python style is fine. Type hints are encouraged but not enforced.

## PR checklist

- [ ] Tests pass (`pytest -q`)
- [ ] Ruff clean (`ruff check .`), if installed
- [ ] CHANGELOG entry added under `[Unreleased]`
- [ ] README / `docs/` updated for any new public surface (new tool, new config key, new flag)
- [ ] Screenshot or short GIF attached if it's a UX-visible change

## Good first issues

Browse the [`good first issue`](https://github.com/7alexhale5-rgb/screenmind/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) label on the issue tracker for small, well-scoped tasks.

## Backlog

Non-trivial roadmap items already triaged live in `.planning/BACKLOG.md`. Check there before opening a feature request — your idea may already be queued.

## Code of conduct

Treat everyone with respect. Bad behavior gets you removed.
