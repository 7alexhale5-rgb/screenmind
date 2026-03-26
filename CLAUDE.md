# ScreenMind

> Status: active | Type: lab (MCP server)

## What It Does

Local MCP server that processes screen recordings into keyframes + OCR + timeline, giving Claude behavioral context from interaction sequences (click flows, UI transitions, error chains).

## Architecture

- **Runtime:** Python 3.13+, FastMCP, stdio transport
- **Processing:** ffmpeg (frame extraction, scene detection, recording), ffprobe (metadata), tesseract (OCR)
- **Storage:** `~/.screenmind/sessions/<session_id>/` (persistent frames), `~/.screenmind/config.json`
- **Optional deps:** scikit-image (SSIM dedup), pytesseract + Pillow (OCR) — server works without them

## Key Decisions

- Returns text + file paths, NOT base64 — Claude reads frames via Read tool
- Scene change timestamps parsed from ffmpeg showinfo `pts_time:` — NOT estimated
- Frame rate string parsed by splitting on `/` — no arbitrary code execution
- Frames persist to `~/.screenmind/sessions/` — NOT tempdir
- Binary paths cached after first lookup (`/opt/homebrew/bin/` checked first for Apple Silicon)
- SSIM + OCR imported inside functions with try/except for graceful degradation

## Dev Commands

```bash
# Compile check
python3 -m py_compile server.py

# Run directly (stdio mode)
python3 server.py

# Install/reinstall
./install.sh

# Register with Claude Code
claude mcp add screenmind -- /Users/alexhale/Projects/Ideas/screenmind/.venv/bin/python /Users/alexhale/Projects/Ideas/screenmind/server.py
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `screenmind_watch` | Process recording -> keyframes + OCR + timeline |
| `screenmind_record_start` | Start recording via ffmpeg avfoundation |
| `screenmind_record_stop` | Stop active recording |
| `screenmind_list` | List recordings in capture dir |
| `screenmind_status` | Check recording/dependency status |

## Config

`~/.screenmind/config.json` — created on first run. Key settings:
- `capture_dir` — where to find/save recordings (default: ~/Desktop)
- `avfoundation_screen_index` — screen device index (default: "1")
- `default_max_frames` — max frames per session (default: 15)
- `dedup_threshold` — SSIM threshold for dedup (default: 0.95)
