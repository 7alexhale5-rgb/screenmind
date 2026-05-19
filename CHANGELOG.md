# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

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

[Unreleased]: https://github.com/alexhale/screenmind/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/alexhale/screenmind/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/alexhale/screenmind/releases/tag/v0.1.0
