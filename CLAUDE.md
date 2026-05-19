# ScreenMind

> Status: active | Type: lab (MCP server)

## What It Does

Local MCP server that turns a screen recording into keyframes + OCR + a timeline document, giving Claude behavioral context from interaction sequences (click flows, UI transitions, error chains). Accepts both local recording files and URLs — YouTube, Instagram, TikTok, Twitter/X, and 1000+ other sites via yt-dlp. Output is a text comprehension document with file paths; Claude reads individual frames via the Read tool (no base64 in the response).

## Architecture

- **Runtime:** Python 3.10+, FastMCP, stdio transport
- **Processing:** ffmpeg (frame extraction, scene detection, recording), ffprobe (metadata), tesseract (OCR), yt-dlp (URL ingest)
- **Storage:** `~/.screenmind/sessions/<session_id>/` (persistent frames), `~/.screenmind/downloads/` (URL downloads), `~/.screenmind/config.json`
- **Optional deps:** scikit-image (SSIM dedup), pytesseract + Pillow (OCR), yt-dlp (URL support) — server works without them, features degrade gracefully

## Key Decisions

- Returns text + file paths, NOT base64 — Claude reads frames via the Read tool
- Scene change timestamps parsed from ffmpeg showinfo `pts_time:` — NOT estimated
- Frame rate string parsed by splitting on `/` — no `eval`, no arbitrary code execution
- Frames persist to `~/.screenmind/sessions/` — NOT tempdir; oldest sessions reaped per `max_sessions_kept`
- Binary paths cached after first lookup; `/opt/homebrew/bin/` checked first for Apple Silicon
- SSIM, OCR, and yt-dlp imported inside functions with try/except — graceful degradation if any are missing
- URL detection via `urllib.parse.urlparse` (scheme http/https + netloc); downloads via yt-dlp with `--no-playlist --merge-output-format mp4`
- Adaptive extraction FPS: ≤15s → 2fps, ≤60s → 1fps, else 0.5fps
- Frame selection priority when over budget: first/last → scene change → OCR text change (>30% character delta) → even distribution
- Recording shutdown sends SIGINT first (clean ffmpeg trailer write), falls back to SIGKILL after 10s timeout

## Dev Commands

```bash
# Compile check
python3 -m py_compile server.py

# Run directly (stdio mode)
python3 server.py

# Install / reinstall
./install.sh

# Register with Claude Code (install.sh prints the exact command for your path)
claude mcp add screenmind -- /path/to/screenmind/.venv/bin/python /path/to/screenmind/server.py
```

## MCP Tools

| Tool                      | Purpose                                                                |
| ------------------------- | ---------------------------------------------------------------------- |
| `screenmind_watch`        | Process a recording (file path or URL) into keyframes + OCR + timeline |
| `screenmind_record_start` | Start recording via ffmpeg avfoundation                                |
| `screenmind_record_stop`  | Stop the active recording (SIGINT, SIGKILL fallback)                   |
| `screenmind_list`         | List recordings in capture_dir, newest first                           |
| `screenmind_status`       | Check recording state, session count, dependency availability          |

## Config

`~/.screenmind/config.json` — created on first run. Highest-impact keys:

- `capture_dir` — where to find/save recordings (default: `~/Desktop`)
- `default_max_frames` — frame budget per session (default: 15)
- `dedup_threshold` — SSIM threshold above which frames count as duplicates (default: 0.95)
- `scene_change_threshold` — ffmpeg scene-detect sensitivity, 0.0–1.0 (default: 0.3)
- `avfoundation_screen_index` — screen device index for recording (default: `"1"`)
- `max_sessions_kept` — oldest sessions reaped beyond this count (default: 20)

Full reference: `docs/CONFIGURATION.md`.

## Files in this repo

- `server.py` — MCP server (all tools, frame pipeline, recording state)
- `install.sh` — installer; bootstraps `.venv`, ensures ffmpeg/tesseract, prints the exact `claude mcp add` registration command
- `new-recording-notify.sh` — launchd helper that fires a macOS notification when a new recording lands in `capture_dir`
- `requirements.txt` — minimum deps (`fastmcp>=2.0.0`); optional deps commented inline
- `docs/` — USAGE, CONFIGURATION, ARCHITECTURE, TROUBLESHOOTING
