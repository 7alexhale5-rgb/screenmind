# ScreenMind

Local MCP server that turns screen recordings and online videos into structured behavioral context for Claude.

ScreenMind processes a recording (local file or URL from YouTube, Instagram, TikTok, Twitter/X, and 1000+ other sites via yt-dlp) into keyframes, OCR text, and a timeline. It returns a text report with frame file paths — Claude reads the frames itself via the Read tool, so nothing is base64-encoded into the context window.

## Features

- **Local files and URLs** — `.mov`, `.mp4`, `.mkv` from disk, or any video URL yt-dlp supports
- **Real scene detection** — ffmpeg `showinfo` filter, timestamps parsed from `pts_time:` (never estimated)
- **Adaptive FPS extraction** — 2fps for short clips, 0.5fps for long ones, based on duration
- **SSIM deduplication** — drops near-identical frames while preserving first, last, and scene-change frames
- **OCR** — tesseract extracts visible text from each retained frame
- **Smart frame selection** — when over budget, prioritizes first/last, scene changes, OCR text changes, then even distribution
- **macOS screen recording** — start/stop via ffmpeg avfoundation, clean shutdown via SIGINT
- **Session persistence** — frames stored under `~/.screenmind/sessions/<session_id>/` so they remain readable across turns
- **Graceful degradation** — missing yt-dlp, scikit-image, pytesseract, or tesseract just disables that feature; the server keeps working
- **Time range scoping** — re-examine a specific `start_time`/`end_time` window without reprocessing the whole video

## Quick Start

```bash
# Install Python venv, ffmpeg, tesseract
chmod +x install.sh && ./install.sh

# The installer prints the exact registration command. Run it:
claude mcp add screenmind -- /path/to/.venv/bin/python /path/to/server.py
```

Verify Claude sees the server:

```bash
claude mcp list
```

## Usage

ScreenMind exposes five MCP tools. Most of the time you ask Claude in plain English; the raw tool calls below are for power users.

### Watching a local recording

Tell Claude:

```text
watch my latest recording
analyze the screen recording on my desktop, focus on the error dialog
```

Raw calls:

```text
screenmind_watch
screenmind_watch file_path="/Users/me/Desktop/demo.mov"
screenmind_watch file_path="/Users/me/Desktop/demo.mov" focus="watch the form submit flow"
screenmind_watch file_path="/Users/me/Desktop/demo.mov" start_time=5.0 end_time=15.0
```

If `file_path` is omitted, ScreenMind picks the most recent file in `capture_dir` matching `file_patterns`.

### Watching a URL

Tell Claude:

```text
watch this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Raw calls:

```text
screenmind_watch file_path="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
screenmind_watch file_path="https://www.instagram.com/reel/ABC123/"
screenmind_watch file_path="https://twitter.com/user/status/123" focus="what does the demo show at 0:30?"
```

URLs are downloaded to `~/.screenmind/downloads/` via yt-dlp, merged to `.mp4`, then processed like a local file. Requires `yt-dlp` on PATH (`brew install yt-dlp`).

### Recording your screen

```text
screenmind_record_start
screenmind_record_start duration=60 output_name="login-flow"
screenmind_record_stop
```

`screenmind_record_start` launches ffmpeg with avfoundation. `screenmind_record_stop` sends `SIGINT` so ffmpeg writes a clean file trailer.

### Listing and status

```text
screenmind_list                  # 10 most recent recordings in capture_dir
screenmind_list limit=25
screenmind_status                # recording state + dependency probe
```

## Tool Reference

| Tool                      | Purpose                                                   | Parameters                                                                                                                                                                                                                                                                    | Returns                                     |
| ------------------------- | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| `screenmind_watch`        | Process recording into keyframes + OCR + timeline         | `file_path` (str, optional — local path or URL; defaults to latest in `capture_dir`), `focus` (str, optional — context hint), `start_time` (float, optional — seconds), `end_time` (float, optional — seconds), `max_frames` (int, optional — overrides `default_max_frames`) | Markdown report with frame file paths       |
| `screenmind_record_start` | Start macOS screen recording via ffmpeg avfoundation      | `duration` (int, optional — defaults to `max_recording_duration`), `output_name` (str, optional — defaults to `screenmind_<timestamp>`)                                                                                                                                       | Status string with output path              |
| `screenmind_record_stop`  | Stop active recording (SIGINT for clean trailer)          | none                                                                                                                                                                                                                                                                          | Status string with saved file path and size |
| `screenmind_list`         | List recordings in `capture_dir` matching `file_patterns` | `limit` (int, default `10`)                                                                                                                                                                                                                                                   | Markdown list of files with size and mtime  |
| `screenmind_status`       | Recording state, session count, dependency probe          | none                                                                                                                                                                                                                                                                          | Markdown status report                      |

## How It Works

`screenmind_watch` runs a 7-step pipeline:

1. **ffprobe metadata** — duration, resolution, fps, codec. Frame rate parsed by splitting `r_frame_rate` on `/` (no arbitrary code execution).
2. **Scene detection** — ffmpeg `select='gt(scene,THRESHOLD)',showinfo` filter. Real timestamps parsed from the `pts_time:` field in stderr — never estimated.
3. **Adaptive FPS extraction** — `≤15s → 2fps`, `≤60s → 1fps`, `else 0.5fps`. Honors `start_time`/`end_time` via ffmpeg `-ss`/`-t`.
4. **Scene + interval merge** — scene-change frames extracted at exact timestamps and merged with interval frames. When two frames fall within `0.3s` of each other, the `scene_change` frame wins.
5. **SSIM deduplication** — `skimage.metrics.structural_similarity` drops near-identical frames against `dedup_threshold`. First, last, and all scene-change frames are always preserved.
6. **Best-frame selection within budget** — when frames exceed `max_frames`, priority order is: first/last → scene changes → frames with OCR text changes (>30% character delta) → even distribution to fill remaining slots.
7. **OCR + cleanup** — tesseract runs on retained frames. Discarded frame files are deleted. Sessions beyond `max_sessions_kept` are pruned.

The returned text report lists each frame with its timestamp, source tag (`scene_change` or `interval`), file path, and OCR text. Claude opens specific frames with the Read tool when it needs to see pixels.

## Configuration

`~/.screenmind/config.json` is created with defaults on first run. User values are merged on top of defaults — missing keys fall back to defaults.

| Key                         | Default                       | Description                                                                              |
| --------------------------- | ----------------------------- | ---------------------------------------------------------------------------------------- |
| `capture_dir`               | `~/Desktop`                   | Where recordings are saved and discovered                                                |
| `file_patterns`             | `["*.mov", "*.mp4", "*.mkv"]` | Glob patterns used by `screenmind_list` and "latest recording" lookup                    |
| `max_recording_duration`    | `120`                         | Max seconds for `screenmind_record_start`                                                |
| `default_max_frames`        | `15`                          | Frame budget per `screenmind_watch` call                                                 |
| `frame_quality`             | `80`                          | JPEG quality, 1-100 (mapped to ffmpeg `-q:v`)                                            |
| `frame_max_width`           | `1280`                        | Max output frame width; aspect ratio preserved                                           |
| `dedup_threshold`           | `0.95`                        | SSIM score above which frames are treated as duplicates (higher = more aggressive dedup) |
| `scene_change_threshold`    | `0.3`                         | ffmpeg scene score cutoff (lower = more scenes detected)                                 |
| `ocr_enabled`               | `true`                        | Toggle tesseract OCR pass                                                                |
| `avfoundation_screen_index` | `"1"`                         | macOS screen device index for ffmpeg avfoundation                                        |
| `max_sessions_kept`         | `20`                          | Old session directories pruned beyond this count                                         |

## Sessions and Storage

ScreenMind writes everything under `~/.screenmind/`:

```text
~/.screenmind/
├── config.json                          # user config (merged with defaults)
├── downloads/                           # yt-dlp output for URL inputs
│   └── <title>_<id>.mp4
└── sessions/
    └── <unix_ts>_<source_stem>/         # one directory per screenmind_watch call
        ├── scene_<timestamp>.jpg        # scene-change frames
        └── frame_<NNNNN>.jpg            # surviving interval frames
```

Session IDs are `<unix_timestamp>_<source_filename_stem>` so they sort chronologically. Sessions persist across server restarts; old ones are pruned automatically beyond `max_sessions_kept`.

## Dependencies

### Required

| Dependency   | What it provides                             | Install                   |
| ------------ | -------------------------------------------- | ------------------------- |
| Python 3.10+ | runtime                                      | system                    |
| `ffmpeg`     | frame extraction, scene detection, recording | `brew install ffmpeg`     |
| `ffprobe`    | video metadata                               | bundled with ffmpeg       |
| `fastmcp`    | MCP server framework                         | installed by `install.sh` |

### Optional (graceful degradation)

| Dependency               | What it unlocks                                         | Without it                                                                     |
| ------------------------ | ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `yt-dlp` binary          | URL inputs (YouTube, Instagram, TikTok, X, 1000+ sites) | URL inputs return `Download failed: yt-dlp not found` — local files still work |
| `scikit-image`           | SSIM frame deduplication                                | all interval frames retained (slightly noisier reports)                        |
| `pytesseract` + `Pillow` | OCR text extraction                                     | reports omit `Visible text` blocks                                             |
| `tesseract` binary       | OCR engine that pytesseract drives                      | OCR silently disabled                                                          |

Binary lookup checks `/opt/homebrew/bin/` first (Apple Silicon Homebrew) before falling back to `PATH`. Results are cached per process.

## macOS Permissions

ffmpeg needs Screen Recording permission to capture your screen. The first time you run `screenmind_record_start`, macOS prompts you to grant it. If it doesn't prompt, or if your recordings come out as a black rectangle:

1. Open **System Settings → Privacy & Security → Screen Recording**
2. Click `+` and add the ffmpeg binary (typically `/opt/homebrew/bin/ffmpeg`)
3. Restart your terminal so ffmpeg inherits the new permission

Run `screenmind_status` to confirm ffmpeg is found at the expected path.

## Auto-notify on New Recordings

`new-recording-notify.sh` is a small helper that sends a macOS notification when a new recording lands in `~/Desktop`, reminding you to ask Claude to watch it. Wire it up with launchd `WatchPaths`:

`~/Library/LaunchAgents/com.screenmind.new-recording.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.screenmind.new-recording</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/screenmind/new-recording-notify.sh</string>
    </array>
    <key>WatchPaths</key>
    <array>
        <string>/Users/YOU/Desktop</string>
    </array>
    <key>StandardOutPath</key>
    <string>/tmp/screenmind-notify.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/screenmind-notify.err</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.screenmind.new-recording.plist
```

When a new file appears in `~/Desktop`, the launchd job runs the script and you get a notification — your cue to type `watch my latest recording` in Claude.

## Troubleshooting

| Symptom                                    | Cause                                    | Fix                                                                                                                  |
| ------------------------------------------ | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `ffprobe not found` or `ffmpeg not found`  | ffmpeg not installed or not on PATH      | `brew install ffmpeg`; verify with `screenmind_status`                                                               |
| Recording produces a black `.mov`          | ffmpeg lacks Screen Recording permission | Add the ffmpeg binary path under System Settings → Privacy & Security → Screen Recording, then restart your terminal |
| `Download failed: yt-dlp not found`        | yt-dlp not installed                     | `brew install yt-dlp` — local files still work without it                                                            |
| Reports never include `Visible text`       | OCR stack missing                        | `pip install pytesseract Pillow` in the venv and `brew install tesseract`                                            |
| `SSIM dedup: unavailable` in report header | scikit-image not installed               | `pip install scikit-image` in the venv. The server still works; you just get more interval frames in reports         |
| `No recording found`                       | `capture_dir` empty or wrong patterns    | Pass `file_path` explicitly, or edit `capture_dir` / `file_patterns` in `~/.screenmind/config.json`                  |
| `Invalid time range`                       | `start_time >= end_time`                 | Pass a valid range, or omit both to process the full video                                                           |
| URL download hangs past 5 minutes          | yt-dlp subprocess timeout is 300s        | Download the file manually and pass it as a local path                                                               |

## Development

```bash
# Compile-check the server
python3 -m py_compile server.py

# Run directly (stdio MCP transport — useful for client debugging)
python3 server.py

# Reinstall the venv from scratch
./install.sh
```

Key design constraints enforced in `server.py`:

- Returns text + file paths, never base64 — keeps frames out of the context window
- Scene timestamps parsed from real `pts_time:` values — no estimation
- Frame rate parsed by splitting `r_frame_rate` on `/` — no `eval`
- Binary lookups cached after first hit, with `/opt/homebrew/bin/` checked before `PATH` for Apple Silicon
- Optional deps (`skimage`, `pytesseract`, `Pillow`, `numpy`) imported inside functions with try/except so missing packages disable a feature instead of crashing the server

## License

MIT.
