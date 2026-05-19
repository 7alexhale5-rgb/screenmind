# ScreenMind Configuration

All settings live in `~/.screenmind/config.json`. The file is created with defaults the first time the server runs. Edits take effect on the next tool call — no restart needed.

See also: [`USAGE.md`](./USAGE.md) for usage examples, [`ARCHITECTURE.md`](./ARCHITECTURE.md) for how these settings shape the pipeline, [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) for common config-related failures.

---

## Settings at a glance

| Key                           | Default                       | What it controls                                                                           |
| ----------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------ |
| `capture_dir`                 | `"~/Desktop"`                 | Where ScreenMind looks for recordings and writes new ones from `screenmind_record_start`.  |
| `file_patterns`               | `["*.mov", "*.mp4", "*.mkv"]` | Glob patterns used by `screenmind_list` and the "latest recording" auto-pick.              |
| `max_recording_duration`      | `120`                         | Hard cap (seconds) on `screenmind_record_start` runs.                                      |
| `default_max_frames`          | `15`                          | Frame budget per `screenmind_watch` call, before any per-call override.                    |
| `frame_quality`               | `80`                          | JPEG quality target (1–100) for extracted frames.                                          |
| `frame_max_width`             | `1280`                        | Max width (px) for extracted frames. Aspect ratio preserved.                               |
| `dedup_threshold`             | `0.95`                        | SSIM similarity above which two consecutive frames count as duplicates and one is dropped. |
| `scene_change_threshold`      | `0.3`                         | ffmpeg `select='gt(scene,T)'` threshold for detecting scene cuts.                          |
| `ocr_enabled`                 | `true`                        | Whether to run OCR on kept frames. Off → faster runs, no `**Visible text:**` blocks.       |
| `audio_transcription_enabled` | `true`                        | Whether to extract audio and run Whisper transcription during `screenmind_watch`.          |
| `whisper_model`               | `"tiny.en"`                   | faster-whisper model name. Bigger = slower but more accurate.                              |
| `avfoundation_screen_index`   | `"1"`                         | macOS screen device index used by `screenmind_record_start`.                               |
| `max_sessions_kept`           | `20`                          | How many session directories to keep under `~/.screenmind/sessions/`. Oldest pruned.       |

---

## `capture_dir`

- **Default:** `"~/Desktop"`
- **What:** Where new recordings are saved and where the "latest recording" lookup searches when you call `screenmind_watch` without `file_path`. Also where `screenmind_list` enumerates from.
- **When to change:** You record into a dedicated folder, you have a Screenshots/Recordings folder set up elsewhere, or you keep recordings on an external drive.
- **Tuning:** Use `~`-prefixed paths — they get expanded. Avoid network mounts unless you accept the latency hit on every `_find_latest_recording` call.

---

## `file_patterns`

- **Default:** `["*.mov", "*.mp4", "*.mkv"]`
- **What:** Glob list used to identify recordings inside `capture_dir`. Only matching files appear in `screenmind_list` and are eligible for the auto-pick.
- **When to change:** You also record `.webm`, `.avi`, `.m4v`, or your OS writes a different extension by default.
- **Tuning:** Order doesn't matter — results are merged then sorted by mtime. Adding more patterns has negligible cost.

Example:

```json
"file_patterns": ["*.mov", "*.mp4", "*.mkv", "*.webm", "*.m4v"]
```

---

## `max_recording_duration`

- **Default:** `120`
- **What:** The `-t` flag passed to ffmpeg when starting a recording. ffmpeg exits cleanly at this point even if you forget to call `screenmind_record_stop`.
- **When to change:** You record long demo walkthroughs and need a higher ceiling, or you want to enforce a tight cap to avoid runaway recordings.
- **Tuning:** `duration` on `screenmind_record_start` overrides this per-call. The config value is just the default. Longer recordings produce bigger files and slower `screenmind_watch` runs.

---

## `default_max_frames`

- **Default:** `15`
- **What:** Frame budget for a `screenmind_watch` call. After scene detection, interval extraction, merging, and SSIM dedup, the pipeline trims down to this number using a priority order (see [`ARCHITECTURE.md`](./ARCHITECTURE.md)).
- **When to change:** You routinely deal with dense recordings (raise to 25–40) or quick scans (drop to 6–10).
- **Tuning:** Each frame adds OCR time and Claude context tokens. 15 is a reasonable middle ground; numbers over ~40 start to feel slow.

---

## `frame_quality`

- **Default:** `80`
- **What:** Target JPEG quality. ScreenMind converts this to ffmpeg's `-q:v` scale internally: `max(1, min(31, (100 - quality) * 31 // 100))`. So `100` becomes `q:v 1` (best), `0` becomes `q:v 31` (worst).
- **When to change:** OCR is missing text on small fonts → raise to 90+. Frames are huge and you don't care about visual fidelity → drop to 60.
- **Tuning:** Above 90 the size grows fast for little visible gain. Below 60 OCR accuracy starts to suffer on small UI text.

---

## `frame_max_width`

- **Default:** `1280`
- **What:** Max width in pixels for extracted frames. ffmpeg scales with `scale='min(1280,iw)':-2` — never upscales, preserves aspect ratio, height rounded to even.
- **When to change:** Recording is from a Retina display and you need crisper OCR on small text → raise to 1920. You want lighter frames for quick scans → drop to 960.
- **Tuning:** OCR accuracy correlates strongly with text size in pixels. If text in your recordings looks small, raise this before raising `frame_quality`.

---

## `dedup_threshold`

- **Default:** `0.95`
- **What:** SSIM (Structural Similarity Index) threshold. If two consecutive frames score **above** this value, the second is considered a duplicate and its file is deleted. SSIM ranges from -1 to 1; 1.0 is identical.
- **When to change:** Too many near-duplicates surviving → lower to `0.90`. Important small changes (a single character changing) being dropped → raise to `0.98`.
- **Tuning:** SSIM is computed on grayscale at the smaller of the two frame sizes. First, last, and scene-change frames are always preserved regardless of similarity score. Requires `scikit-image`; if missing, dedup is a no-op and `**SSIM dedup:** unavailable` appears in the report.

A quick mental model:

- `0.99` → only exact duplicates dropped
- `0.95` → near-identical frames dropped (default — good middle)
- `0.90` → drops anything that looks roughly the same to a human eye
- `0.80` → aggressive, will likely drop legitimate transitions

---

## `scene_change_threshold`

- **Default:** `0.3`
- **What:** Passed to ffmpeg as `select='gt(scene,0.3)',showinfo`. ffmpeg's scene detector emits a 0–1 score per frame measuring how different it is from the previous frame; frames scoring above this threshold are flagged as scene changes.
- **When to change:** Too many scene changes in a UI recording (every micro-animation triggers) → raise to `0.4` or `0.5`. Real cuts being missed in a video tutorial → lower to `0.2`.
- **Tuning:** Higher = fewer scene changes detected, more dependence on the interval-FPS pass. Lower = more scene change frames, more risk of false positives. UI recordings often need higher thresholds than video tutorials because hover states and cursor moves can spike the scene score.

---

## `ocr_enabled`

- **Default:** `true`
- **What:** Whether to run OCR on each kept frame. When on, OCR text is inlined in the report under `**Visible text:**` blocks (truncated at 500 chars) and also used to detect "OCR-change" frames during selection.
- **When to change:** OCR is slow or not useful for your recordings (mostly video content with no text) → set `false`. Or you want OCR back on after disabling.
- **Tuning:** Disabling OCR speeds up `screenmind_watch` substantially on long recordings, but Claude loses the searchable text layer. If `tesseract` or `pytesseract` are missing, OCR is unavailable regardless of this setting and the report says `**OCR:** unavailable`.

---

## `avfoundation_screen_index`

- **Default:** `"1"`
- **What:** Which screen device ffmpeg captures from when you call `screenmind_record_start`. Mapped to `-f avfoundation -i "<index>:none"` (the `:none` means no audio).
- **When to change:** Your recordings capture the wrong display, or you have multiple monitors and want a specific one.
- **Finding your screen index:** Run this in your terminal:

```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

You'll see a block like:

```text
[AVFoundation indev @ 0x...] AVFoundation video devices:
[AVFoundation indev @ 0x...] [0] FaceTime HD Camera
[AVFoundation indev @ 0x...] [1] Capture screen 0
[AVFoundation indev @ 0x...] [2] Capture screen 1
```

The number in brackets is the index. Set it as a string in the config:

```json
"avfoundation_screen_index": "2"
```

- **Tuning:** Store as a string — that's what ffmpeg expects in the `<index>:none` format. Numeric `2` will also work because Python stringifies it, but stick with strings for clarity.

---

## `max_sessions_kept`

- **Default:** `20`
- **What:** Maximum session directories kept under `~/.screenmind/sessions/`. After each `screenmind_watch` run, anything beyond this count is deleted, oldest first by mtime.
- **When to change:** You want more session history for re-reading old reports (raise to 50–100), or you're tight on disk and want to keep less (drop to 5).
- **Tuning:** Pruning only happens during a `screenmind_watch` run — it does not run on a schedule. If sessions pile up between runs, that's expected. Manually delete with `rm -rf ~/.screenmind/sessions/*` if you need to free space immediately.

---

## `audio_transcription_enabled`

- **Default:** `true`
- **What:** Toggles audio extraction (ffmpeg) + transcription (faster-whisper) inside `screenmind_watch`. When `false`, the report omits the `## Audio Transcript` section regardless of whether faster-whisper is installed.
- **When to change:** Set to `false` when you only care about the visual timeline (UI flows without dialog), or when faster-whisper is installed but you want to skip the per-call latency hit.
- **Tuning:** Even with this `true`, transcription degrades gracefully: ffmpeg returns no audio stream → "no audio stream" line; faster-whisper not installed → "unavailable" line; everything else works.

---

## `whisper_model`

- **Default:** `"tiny.en"`
- **What:** Model name passed to `faster_whisper.WhisperModel(...)`. The model is downloaded on first use and cached on disk by faster-whisper itself.
- **When to change:** You want better accuracy on accented speech or technical terms (try `"base.en"` or `"small.en"`), or you have GPU acceleration set up and want to use a larger multilingual model.
- **Tuning:** First call with a new model name downloads the weights (`tiny.en` ≈75 MB, `base.en` ≈140 MB, `small.en` ≈460 MB). Subsequent calls in the same server process reuse a cached in-memory model — no reload cost. The server defaults to CPU `int8` compute for portability; edit `_get_whisper_model` in `server.py` if you need GPU.

---

## Filesystem layout under `~/.screenmind/`

```text
~/.screenmind/
├── config.json                 # Settings. Created automatically on first run with defaults.
├── sessions/                   # Per-watch outputs. Persistent across runs.
│   └── <session_id>/           # session_id = "<unix_ts>_<video_stem>"
│       ├── scene_<ts>.jpg      # Frame extracted at a scene-change timestamp.
│       └── frame_<NNNNN>.jpg   # Frame extracted at the adaptive interval rate.
└── downloads/                  # yt-dlp output for URL inputs.
    └── <title>_<id>.mp4        # Downloaded video. Reusable — re-running on the same URL re-downloads.
```

Notes:

- `config.json` is read on every `_load_config()` call and merged with `DEFAULT_CONFIG`. If you delete a key, the default is used until you re-add it. New keys you don't recognize are kept as-is.
- Session directories are pruned by `max_sessions_kept` only during a `screenmind_watch` run. The `raw/` subdirectory used during extraction is removed at the end of each run.
- Downloads do not auto-clean. Delete the `downloads/` folder manually when you want to reclaim space.
- The whole tree is created with default permissions (`0o755` from `mkdir`). If `~/.screenmind/` fails to create with a permission error, see [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md).
