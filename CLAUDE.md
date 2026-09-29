# ScreenMind

> Status: active | Type: lab (MCP server)

## What It Does

Local MCP server that turns a screen recording into keyframes + OCR + a timeline document, giving Claude behavioral context from interaction sequences (click flows, UI transitions, error chains). Accepts both local recording files and URLs — YouTube, Instagram, TikTok, Twitter/X, and 1000+ other sites via yt-dlp. Output is a text comprehension document with file paths; Claude reads individual frames via the Read tool (no base64 in the response).

## Architecture

- **Runtime:** Python 3.10+, FastMCP, stdio transport
- **Layout:** `server.py` (MCP tools + frame pipeline + recording state) + `screenmind/` package (`config.py`, `ffmpeg.py`, `url_ingest.py`, `util.py`) for testability
- **Processing:** ffmpeg (frame extraction, scene detection, recording), ffprobe (metadata), tesseract (OCR), yt-dlp (URL ingest), faster-whisper (audio transcription, v0.3.0+)
- **Storage:** `~/.screenmind/sessions/<session_id>/` (persistent frames + `report.md`), `~/.screenmind/downloads/` (URL downloads), `~/.screenmind/config.json`
- **Optional deps:** scikit-image (SSIM dedup + `wait_for_change`), pytesseract + Pillow (OCR), yt-dlp (URL support), faster-whisper (audio transcript) — server works without them, features degrade gracefully

## Key Decisions

- Returns text + file paths, NOT base64 — Claude reads frames via the Read tool
- Scene change timestamps parsed from ffmpeg showinfo `pts_time:` — NOT estimated
- Frame rate parsed by splitting on `/` with malformed-input fallback to 30.0 — no `eval`, no arbitrary code execution
- Frames persist to `~/.screenmind/sessions/` — NOT tempdir; oldest sessions reaped per `max_sessions_kept`
- `report.md` persisted per session enables `screenmind_search` cross-session indexing without a separate DB
- Binary paths cached after first lookup; `/opt/homebrew/bin/` checked first for Apple Silicon
- SSIM, OCR, yt-dlp, and faster-whisper imported inside functions with try/except — graceful degradation if any are missing
- URL detection via `urllib.parse.urlparse` (scheme http/https + netloc); downloads via yt-dlp with `--no-playlist --merge-output-format mp4`
- Flat 2 fps extraction (`target_fps`); only the 900-frame budget (`frame_budget_ceiling`) lowers it, and the report's Sample density line + DENSITY SHORTFALL block say when it did
- Scene pass prefilters to `fps=10,scale=480:-2`; decode passes time out at `max(120s, duration)`; a scene-pass timeout skips scene frames instead of failing the call
- Frame selection priority when over budget: first/last → scene change → OCR text change (>30% character delta) → even distribution
- Recording shutdown sends SIGINT first (clean ffmpeg trailer write), falls back to SIGKILL after 10s timeout
- `screenmind_wait_for_change` hard-caps `max_wait_seconds` at 600 and minimum `poll_interval` at 0.5s to bound long-poll cost

## Dev Commands

```bash
# Compile check
python3 -m py_compile server.py screenmind/*.py

# Run the test suite
pip install -r requirements-dev.txt
pytest -q

# Run directly (stdio mode)
python3 server.py

# Install / reinstall
./install.sh

# Register with Claude Code (install.sh prints the exact command for your path)
claude mcp add screenmind -- /path/to/screenmind/.venv/bin/python /path/to/screenmind/server.py
```

## MCP Tools

| Tool                         | Purpose                                                                                   |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| `screenmind_watch`           | Process a recording (file path or URL) into keyframes + OCR + audio transcript + timeline |
| `screenmind_wait_for_change` | Long-poll until SSIM drops below a threshold or timeout elapses                           |
| `screenmind_search`          | Substring search across persisted session reports (OCR + transcript)                      |
| `screenmind_record_start`    | Start recording via ffmpeg avfoundation                                                   |
| `screenmind_record_stop`     | Stop the active recording (SIGINT, SIGKILL fallback)                                      |
| `screenmind_list`            | List recordings in capture_dir, newest first                                              |
| `screenmind_status`          | Check recording state, session count, dependency availability                             |

## Config

`~/.screenmind/config.json` — created on first run. Highest-impact keys:

- `capture_dir` — where to find/save recordings (default: `~/Desktop`)
- `default_max_frames` — frame budget per session (default: 900, 7.5 min at 2 fps)
- `dedup_threshold` — SSIM threshold above which frames count as duplicates (default: 0.995)
- `scene_change_threshold` — ffmpeg scene-detect sensitivity, 0.0–1.0 (default: 0.3)
- `whisper_model` — faster-whisper model name (default: `tiny.en`)
- `audio_transcription_enabled` — toggle the transcript pass (default: `true`)
- `avfoundation_screen_index` — screen device index for recording (default: `"1"`)
- `max_sessions_kept` — oldest sessions reaped beyond this count (default: 20)

Full reference: `docs/CONFIGURATION.md`.

## Files in this repo

- `server.py` — MCP tool registrations + frame pipeline + recording state
- `screenmind/` — testable package: `config.py`, `density.py`, `ffmpeg.py`, `url_ingest.py`, `util.py`
- `tests/` — pytest suite (config merge, URL detection, ffmpeg frame-rate parsing, extraction FPS, scene pass, density report, end-to-end watch)
- `install.sh` — installer; bootstraps `.venv`, ensures ffmpeg/tesseract, prints the exact `claude mcp add` registration command
- `new-recording-notify.sh` — launchd helper that fires a macOS notification when a new recording lands in `capture_dir`
- `requirements.txt` — runtime deps (`fastmcp>=2.0.0`); optional deps commented inline
- `requirements-dev.txt` — dev deps (`pytest`, `pytest-mock`)
- `pyproject.toml` — packaging metadata + pytest + ruff config
- `.github/workflows/ci.yml` — CI matrix (ubuntu + macOS × Python 3.11 + 3.12)
- `docs/` — USAGE, CONFIGURATION, ARCHITECTURE, TROUBLESHOOTING, POSITIONING
