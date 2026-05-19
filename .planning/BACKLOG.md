# ScreenMind Backlog

Project-scope work staged via `/ci-ingest`. Pulled in by `/planning-stack` when working in this repo.

Order: P0 first, then P1, then P2, then P3.

---

## SHIPPED in v0.3.0 (2026-05-19)

- ✅ **P0 `screenmind_wait_for_change`** — long-poll primitive landed in `server.py`. SSIM-based, hard-capped at 600s / 0.5s poll interval. Reuses `_get_ssim_func` and `_load_image_grayscale`. No new dependencies.
- ✅ **P1 Whisper audio transcription** — `screenmind_watch` now extracts audio via ffmpeg and runs `faster-whisper` (optional dep). New config keys `audio_transcription_enabled` and `whisper_model`. Graceful degradation when missing.
- ✅ **P1 Cross-session search** — `screenmind_search` tool. Persists `report.md` per session and substring-matches across `~/.screenmind/sessions/`. `since` accepts ISO date or relative (`30m`/`24h`/`7d`).
- ✅ **P2 Naming + positioning audit** — five same-name repos on GitHub, none on the MCP/dev-tooling lane, none on PyPI/npm. Documented in `docs/POSITIONING.md`. No rename.
- ✅ **P3 README comparison table** — `## How ScreenMind compares` shipped with screenpipe / claude-screen-mcp / ghost-os / Anthropic computer-use rows.

Also landed in v0.3.0 (engineering hygiene, not original backlog):

- ✅ `screenmind/` package split (`config.py`, `ffmpeg.py`, `url_ingest.py`, `util.py`) — server.py kept at MCP-tool layer
- ✅ `pyproject.toml` with optional-dependency extras
- ✅ pytest suite (29 tests in <1s)
- ✅ GitHub Actions CI matrix (ubuntu + macOS × py 3.11/3.12)

CI ledger: `~/Projects/memory-vault/continuous-improvement/2026-05-19-screenmind-eyes-gap-audit.md`.

---

## screenmind_diff — INTEGRATE

- **CI source**: `~/Projects/memory-vault/continuous-improvement/2026-05-19-screenmind-eyes-gap-audit.md`
- **Priority**: P2
- **Verdict + reason**: INTEGRATE — "what changed between this build and the broken one" is a recurring Claude Code workflow that currently requires running `watch` twice and diffing by hand.
- **What to do**: New MCP tool `screenmind_diff(file_a, file_b, focus=None)`. Run the existing `screenmind_watch` pipeline against both files (or accept two existing session IDs to skip re-processing). For each, align by relative timestamp; compute per-frame SSIM between aligned pairs; emit a report flagging frames where SSIM drops below a configurable threshold AND OCR text differs. Output structure: `## Differences` section with frame pairs + side-by-side paths + OCR delta.
- **Effort estimate**: 4-6 hours
- **Acceptance criterion**: Diff of two recordings of the same flow with one UI difference (e.g., button color) returns the frame pair where the change happens, ranked by SSIM delta.

---

## Deferred / not-now

- **AX-tree integration** — ghost-os lane, macOS-only, requires Swift sidecar. Reeval if Alex's workflow needs it.
- **Live capture-while-watching** — pair screen recording with concurrent AX-tree snapshots. Same dependency.
- **On-device VLM (Ollama)** — screenpipe uses Apple Intelligence on supported Macs. Reeval if token cost on Claude vision becomes a real budget item.
- **Python 3.10 + 3.13 CI rows** — add when a real user requests them.
- **mypy / strict typing** — useful but not yet pulling weight.
- **60%+ test coverage** — chase only when a real bug escapes the current smoke tests.
