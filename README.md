# ScreenMind

Local MCP server that gives Claude Code behavioral context from screen recordings — keyframes, OCR text, and temporal timelines from interaction sequences.

## Quick Start

```bash
# Install
chmod +x install.sh && ./install.sh

# Register with Claude Code
claude mcp add screenmind -- /path/to/.venv/bin/python /path/to/server.py
```

The installer prints the exact registration command for your system.

## Usage

### Watch a recording

Tell Claude: "watch my latest recording" or "analyze this screen recording"

```
# Processes the most recent recording in capture_dir
screenmind_watch

# Specific file with focus context
screenmind_watch file_path="/path/to/recording.mov" focus="watch the error dialog"

# Re-examine a specific time range
screenmind_watch file_path="/path/to/recording.mov" start_time=5.0 end_time=15.0
```

### Record your screen

```
# Start recording (stops after max_recording_duration or manual stop)
screenmind_record_start

# Stop recording
screenmind_record_stop
```

**First time:** macOS will prompt for Screen Recording permission. If you get a black screen, add ffmpeg to System Settings → Privacy & Security → Screen Recording.

### List and check status

```
screenmind_list          # Recent recordings in capture_dir
screenmind_status        # Recording state, session count, dependency status
```

## Tool Reference

| Tool | Purpose | Params |
|------|---------|--------|
| `screenmind_watch` | Process recording → keyframes + OCR + timeline | `file_path`, `focus`, `start_time`, `end_time`, `max_frames` |
| `screenmind_record_start` | Start screen recording | `duration`, `output_name` |
| `screenmind_record_stop` | Stop active recording | — |
| `screenmind_list` | List recordings in capture dir | `limit` |
| `screenmind_status` | Check status and dependencies | — |

## How It Works

1. **ffprobe** extracts video metadata (duration, resolution, fps)
2. **ffmpeg scene detection** finds visual transition timestamps from `showinfo pts_time:`
3. **ffmpeg** extracts frames at adaptive intervals (2fps for ≤15s, 1fps for 15-60s, 0.5fps for 60-120s)
4. **Scene change frames** extracted at exact detected timestamps
5. **SSIM deduplication** drops near-identical frames (static moments)
6. **Tesseract OCR** extracts visible text from retained frames
7. **Smart selection** prioritizes: first/last → scene changes → OCR text changes → even distribution

Returns a text report with frame file paths. Claude reads specific frames via the Read tool.

## Config

`~/.screenmind/config.json` — created automatically on first run.

| Key | Default | Description |
|-----|---------|-------------|
| `capture_dir` | `~/Desktop` | Where to find/save recordings |
| `file_patterns` | `["*.mov", "*.mp4", "*.mkv"]` | File patterns to match |
| `max_recording_duration` | `120` | Max recording length (seconds) |
| `default_max_frames` | `15` | Max frames per analysis |
| `frame_quality` | `80` | JPEG quality (1-100) |
| `frame_max_width` | `1280` | Max frame width (aspect preserved) |
| `dedup_threshold` | `0.95` | SSIM threshold (higher = more aggressive dedup) |
| `scene_change_threshold` | `0.3` | Scene detection sensitivity (lower = more scenes) |
| `ocr_enabled` | `true` | Enable/disable OCR |
| `avfoundation_screen_index` | `"1"` | macOS screen device index |
| `max_sessions_kept` | `20` | Auto-cleanup old sessions |

## Sessions

Processed frames persist at `~/.screenmind/sessions/<session_id>/`. Old sessions are automatically cleaned up beyond `max_sessions_kept`.

## Dependencies

**Required:** Python 3.10+, ffmpeg, ffprobe

**Optional (graceful degradation):**
- scikit-image — SSIM frame deduplication (without it, all interval frames are kept)
- pytesseract + Pillow — OCR text extraction (without it, no text in reports)
- tesseract — OCR engine binary (installed via Homebrew)
