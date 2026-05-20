# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

## [0.3.0] - 2026-05-19

### Added

- `screenmind_wait_for_change` — server-side long-poll until SSIM similarity to a baseline frame drops below the threshold or `max_wait_seconds` elapses (hard-capped at 600). Reuses the existing `scikit-image` import; no new heavy dependency.
- `screenmind_search` — substring search across persisted session reports (OCR text + audio transcript). Accepts an ISO date or relative duration (`30m`, `24h`, `7d`) for the `since` filter.
- Audio transcription via `faster-whisper` (optional dependency, graceful degradation). Adds a timestamped `## Audio Transcript` section to every `screenmind_watch` report when a model is installed.
- Two new config keys: `audio_transcription_enabled` (toggle) and `whisper_model` (default `tiny.en`). Existing user configs backfill from defaults on load.
- `report.md` is now persisted alongside frames at `~/.screenmind/sessions/<session_id>/report.md` so `screenmind_search` can index across sessions.
- `pyproject.toml` declaring `screenmind` as a buildable package with `[project.optional-dependencies]` extras: `ocr`, `ssim`, `whisper`, `all`.
- `tests/` suite with 29 mocked tests covering config merge/backfill, URL detection across schemes, ffmpeg frame-rate parsing, and adaptive-FPS boundaries. Runs in under a second.
- GitHub Actions CI workflow at `.github/workflows/ci.yml` running `py_compile` + `pytest` on `ubuntu-latest` and `macos-latest` × Python 3.11 and 3.12.
- `docs/POSITIONING.md` — naming audit results (no functional conflicts found across GitHub / PyPI / npm) and a "what ScreenMind is not" section linking to peer projects.
- README "How ScreenMind compares" table covering screenpipe, claude-screen-mcp, ghost-os, and Anthropic computer-use.

### Changed

- `server.py` split into a `screenmind/` package for testability: `config.py` (defaults + load), `ffmpeg.py` (ffprobe/ffmpeg I/O), `url_ingest.py` (yt-dlp wrapper), `util.py` (binary lookup). Public MCP surface is identical — host clients see no change.
- `_find_binary` renamed to `find_binary` and moved to `screenmind/util.py`. Internal callers updated.
- `_get_video_metadata`, `_detect_scene_changes`, `_extract_frame_at_timestamp`, `_extract_frames_at_fps`, `_get_extraction_fps` moved to `screenmind/ffmpeg.py` and exposed without leading underscore.
- `_is_url` / `_download_url` moved to `screenmind/url_ingest.py` as `is_url` / `download_url`.
- `screenmind_status` now reports faster-whisper availability and the yt-dlp binary path alongside the existing SSIM/OCR/ffmpeg checks.

### Fixed

- `parse_frame_rate` now handles zero denominators (`30/0`) and malformed strings by falling back to 30.0 instead of raising `ZeroDivisionError` or `ValueError`.
- `load_config` falls back to defaults when `~/.screenmind/config.json` is corrupt JSON or parses to a non-object — the server no longer refuses to start on a hand-edited file.
- `extract_frames_at_fps` rejects `fps <= 0` at the function boundary instead of emitting a malformed ffmpeg filter or hitting `ZeroDivisionError` in the timestamp loop.
- `download_url` raises a clear `RuntimeError` when yt-dlp exits 0 but emits no `after_move:filepath` line (rare, hit on some live streams) instead of `IndexError` on `splitlines()[-1]`.
- `_extract_audio` catches `subprocess.TimeoutExpired` (120s budget) and degrades to "no transcript" so very long videos don't crash the whole `screenmind_watch` run.
- `screenmind_search` validates `limit > 0` and returns a clear message on `limit=0`/negative.

### Security

- `.github/workflows/ci.yml` pins `actions/checkout` and `actions/setup-python` to commit SHAs (was floating `@v4` / `@v5` tags) and sets `persist-credentials: false` on checkout.
- Bumped test suite to 36 tests (added coverage for the corrupt-JSON, non-object-JSON, non-positive-fps, missing-yt-dlp, and empty-stdout paths above).

## [0.2.0] - 2026-05-19

### Added

- `screenmind_watch` now accepts URLs in addition to local file paths. Supports YouTube, Instagram, TikTok, X/Twitter, and 1000+ sites via yt-dlp.
- Downloaded media is cached under `~/.screenmind/downloads/` so repeat URL processing reuses the local file.
- Graceful "yt-dlp not found" error message when the optional dependency is missing, with installation guidance.

## [0.1.0] - 2026-05-19

### Added

- Five MCP tools: `screenmind_watch`, `screenmind_record_start`, `screenmind_record_stop`, `screenmind_list`, `screenmind_status`.
- ffmpeg-based scene detection with real `pts_time:` parsing from showinfo output (no estimated timestamps).
- Adaptive FPS extraction tuned by clip duration (2 / 1 / 0.5 fps tiers).
- SSIM-based frame deduplication via scikit-image (optional dependency; gracefully degrades when absent).
- Tesseract OCR for extracting on-screen text from selected frames.
- Smart frame selection pipeline: first/last anchors → scene-change frames → OCR-change frames → even distribution fill.
- Session persistence at `~/.screenmind/sessions/<session_id>/` so Claude can re-read frames via the Read tool.
- Auto-cleanup of old sessions beyond the configured `max_sessions_kept` limit.
- macOS screen recording via ffmpeg avfoundation, configurable screen device index.
- Graceful degradation when optional dependencies (scikit-image, pytesseract, Pillow) are missing — server still starts and reports capability via `screenmind_status`.
- Binary lookup caches the Apple Silicon Homebrew path (`/opt/homebrew/bin/`) first for faster startup on M-series Macs.

[Unreleased]: https://github.com/7alexhale5-rgb/screenmind/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/7alexhale5-rgb/screenmind/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/7alexhale5-rgb/screenmind/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/7alexhale5-rgb/screenmind/releases/tag/v0.1.0
