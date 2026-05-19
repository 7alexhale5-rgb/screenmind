# ScreenMind Architecture

Engineering deep-dive into how ScreenMind turns a screen recording into a text report Claude can act on. If you're tuning behavior, read [`CONFIGURATION.md`](./CONFIGURATION.md). If something is failing, read [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md). For example workflows, see [`USAGE.md`](./USAGE.md).

---

## Output shape: text + paths, not base64

`screenmind_watch` returns a Markdown report. Each frame entry includes its absolute file path on disk. Claude opens the frame separately with the `Read` tool when it wants to see it.

Why not return base64-encoded images directly?

- **Token cost.** A 1280-wide JPEG encoded as base64 runs into the tens of thousands of tokens. Multiply by 15 frames and a single `screenmind_watch` call would burn a meaningful chunk of context before Claude has read a word.
- **Claude's `Read` tool is already multimodal.** It opens images natively and shows them visually. There's no benefit to inlining them.
- **The report is searchable.** Returning text + paths means the OCR layer is grep-able. Claude can scan the timeline, decide which frames matter, and only pay the image-token cost for the ones it actually needs.
- **Frames persist.** Files live under `~/.screenmind/sessions/<session_id>/`, so a later Claude turn can re-open the same frame without re-running the pipeline.

---

## Scene detection — parsed, not estimated

Scene change timestamps come from ffmpeg's `select` and `showinfo` filters:

```text
ffmpeg -i <video> -vf "select='gt(scene,0.3)',showinfo" -vsync vfr -f null -
```

The `scene` value is ffmpeg's built-in 0–1 scene-similarity score. Frames scoring above `scene_change_threshold` survive the `select`. `showinfo` then prints diagnostic info per surviving frame to stderr, including a line like:

```text
[Parsed_showinfo_1 @ 0x...] n: 12 pts: 14014 pts_time:0.467133 pos: ...
```

ScreenMind parses `pts_time:` directly with the regex `r"pts_time:\s*([\d.]+)"`. These are **exact timestamps reported by ffmpeg** — they are not estimated by dividing a frame index by the FPS. That matters: variable-framerate recordings (most screen recordings are VFR) have non-uniform frame times, and any FPS-based estimate would drift.

The `-vsync vfr` tells ffmpeg to preserve original frame timing rather than resample to a constant rate. `-f null -` discards the actual output — we only care about the stderr metadata.

The whole pass runs with a 120s timeout. Long recordings can still bust this if scene detection is slow; in that case `_detect_scene_changes` returns whatever it parsed before the timeout (effectively `[]` if ffmpeg got killed before any output reached stderr).

---

## Adaptive FPS for interval extraction

After scene detection, the pipeline runs a second pass that extracts frames at a fixed FPS to fill in coverage between scene changes. The FPS depends on the effective duration of the segment being analyzed:

| Effective duration | Extraction FPS | Rationale                                                         |
| ------------------ | -------------- | ----------------------------------------------------------------- |
| ≤ 15 seconds       | 2.0 fps        | Short clips often pack tight interaction sequences — need density |
| ≤ 60 seconds       | 1.0 fps        | Standard demo / Reel length — one frame per second is enough      |
| > 60 seconds       | 0.5 fps        | Long tutorials — keep total frames under control                  |

Implementation is `_get_extraction_fps(duration)`. The "effective duration" is `end_time - start_time` when a window is provided, otherwise the full video duration.

Why a step function and not a smooth curve? Because the frame budget is fixed (`max_frames`, default 15). A linear FPS would either run out of budget on long videos or under-sample short ones. The buckets keep the total raw extraction count in a workable range for the dedup and selection passes downstream.

---

## SSIM dedup — drop the static moments

Once scene frames and interval frames are merged, the pipeline runs SSIM (Structural Similarity Index) on consecutive frames using `skimage.metrics.structural_similarity`. Frames scoring above `dedup_threshold` (default `0.95`) are dropped and their files deleted.

Two important guarantees:

1. **First and last frames are always preserved.** They're added to the `preserve_indices` set before dedup runs.
2. **Scene-change frames are always preserved.** They're also added to `preserve_indices`. A scene change is, by definition, a moment ffmpeg already flagged as visually distinct.

SSIM is computed on grayscale (`Image.convert("L")` → numpy array). When the two frames have different dimensions, we crop both to the smaller width and height before comparing. Frames smaller than 7×7 pixels are skipped (SSIM's default window won't fit).

If `scikit-image` isn't installed, `_dedup_frames` is a no-op and the report flags `**SSIM dedup:** unavailable`.

---

## Merging scene frames and interval frames

After both extraction passes, you have two lists:

- Scene frames at exact `pts_time` timestamps (filenames like `scene_4.667.jpg`)
- Interval frames at uniform spacing (filenames like `frame_00012.jpg`)

These get concatenated, sorted by timestamp, then walked through a collision window:

- If a frame's timestamp is **more than 0.3s** away from the last kept frame, keep it.
- If it's within 0.3s, one frame wins:
  - If the new frame is a `scene_change` and the held one is `interval`, the scene_change replaces it and the interval file is deleted.
  - Otherwise the new frame is discarded and its file is deleted.

Net effect: scene_change frames always beat interval frames in collisions, and you don't end up with two near-identical frames within a third of a second of each other.

---

## Smart frame selection — priority order

After merge + dedup, you may still have more frames than `max_frames`. `_select_best_frames` trims to the budget using a strict priority order:

1. **First and last frame.** Always selected. They anchor the timeline and give Claude start/end context.
2. **Scene change frames.** For each scene change timestamp from ffmpeg, the closest frame in the candidate list is added.
3. **OCR text-change frames.** With `ocr_enabled`, the pipeline walks frames in order and runs OCR. A frame is selected if its OCR text shares less than 70% of characters (positionally) with the previous OCR text — i.e., the visible text changed substantially.
4. **Even distribution remainder.** Any budget left after steps 1–3 is filled by walking the unselected frames at a stride of `len(available) // remaining`, taking one every N.

Frames not selected get their files deleted to save disk. Selected frames have their interval-pass JPEGs moved out of the temporary `raw/` subdirectory into the session root so they survive the end-of-run cleanup.

This ordering means: in a recording with strong scene cuts and changing on-screen text, the kept frames cluster around the moments that matter. In a recording with no scene cuts and no text (e.g., a video of someone's face), the selection degenerates to "first, last, evenly distributed" — which is fine.

---

## Binary lookup caching

`_find_binary(name)` resolves external tools (`ffmpeg`, `ffprobe`, `tesseract`, `yt-dlp`). Lookup order:

1. **`/opt/homebrew/bin/<name>`** — checked first. On Apple Silicon Macs, Homebrew installs here and it's often not on the MCP process's `PATH` (Claude Code launches MCP servers with a minimal environment). Hard-coding the check eliminates a class of "not found" failures that look like missing dependencies but are actually `PATH` issues.
2. **`shutil.which(name)`** — falls back to whatever's on `PATH`.

Results are cached in `_binary_cache: dict[str, Optional[str]]` keyed by name. The cache survives for the lifetime of the MCP server process — meaning if you install ffmpeg after the server starts, you need to restart Claude Code for the cache to pick up the new binary. The cache also stores `None` for misses, so a missing binary stays missing within a session.

This is a deliberate trade-off: the cache saves a `shutil.which` call per tool invocation, and external binaries rarely appear or disappear during a session.

---

## Graceful degradation — optional deps

Three dependencies are optional: `scikit-image` (SSIM), `pytesseract` + `PIL` + `numpy` (OCR), and `yt-dlp` (URL ingestion). Each is imported **inside the function that needs it**, inside a `try/except ImportError`:

```python
def _get_ssim_func():
    try:
        from skimage.metrics import structural_similarity
        return structural_similarity
    except ImportError:
        return None
```

If the import fails, the function returns `None` and callers check for `None` before using it. The server still starts. `screenmind_watch` still runs. The report tells the user what's unavailable:

```text
**SSIM dedup:** unavailable (install scikit-image)
**OCR:** unavailable
```

Why import inside functions instead of at the top of the module?

- **Server startup is fast.** No `ImportError` blocks MCP registration.
- **Errors are localized.** A missing OCR install can't prevent recording from working.
- **`screenmind_status` can report dependency state honestly** — by attempting the imports itself, not by inspecting some flag set at module load time.

The trade is a small per-call cost (the import system is cached after first hit, so subsequent calls are cheap).

---

## Recording subprocess management

`screenmind_record_start` and `screenmind_record_stop` manage a single ffmpeg process held in two module-level globals:

```python
_recording_process: Optional[subprocess.Popen] = None
_recording_output: Optional[str] = None
```

Starting a recording while one is already running returns early with the path of the existing recording — no overlap is possible.

**Stop sequence** is what matters for file integrity:

1. Send `SIGINT` via `_recording_process.send_signal(signal.SIGINT)`. ffmpeg traps SIGINT, flushes its mux buffer, and writes a proper `.mov` trailer (the `moov` atom). This makes the file immediately playable without recovery.
2. `wait(timeout=10)` — give ffmpeg up to 10 seconds to shut down cleanly.
3. If it hasn't exited, escalate to `SIGKILL` via `_recording_process.kill()` and `wait(timeout=5)`. A SIGKILL'd ffmpeg leaves an unfinalized `.mov` — usually still playable in most players, but the duration metadata may be off.

A simple `terminate()` (which sends `SIGTERM`) would not give ffmpeg the same chance to finalize. SIGINT is the convention ffmpeg's stop logic expects.

After stop, both globals are reset to `None` so the next `screenmind_record_start` is a clean slate. `screenmind_status` also resets `_recording_process` to `None` if it detects the process has already exited (polled via `.poll()`).

---

## Security choices

These aren't paranoia — they're concrete decisions you can verify in `server.py`.

**No dynamic-code-execution for frame rate parsing.** ffprobe returns frame rates as strings like `"30000/1001"`. Passing that string to a Python expression-evaluator would be unsafe with untrusted input. ScreenMind splits on `/` and divides:

```python
num, den = fps_str.split("/")
fps = float(num) / float(den) if float(den) != 0 else 30.0
```

A malformed fps string raises a clear `ValueError` from `float()` rather than running arbitrary code.

**File path validation before processing.** `screenmind_watch` expands `~` once, then checks `os.path.exists()` and returns a polite error if the file isn't there. No symlink traversal tricks, no implicit creation. URLs go through a separate `_is_url()` check that requires `scheme in ("http", "https")` and a non-empty `netloc` — `file://` and `javascript:` URLs do not match.

**`subprocess` arguments are always lists, never `shell=True`.** Every `subprocess.run` and `subprocess.Popen` call passes a list of strings:

```python
cmd = [ffmpeg, "-i", video_path, "-vf", f"select='gt(scene,{threshold})',showinfo", ...]
subprocess.run(cmd, capture_output=True, text=True, timeout=120)
```

This means shell metacharacters in the video path can't trigger command injection — they're passed as a single argument to the executable. Paths with spaces, quotes, or backticks are safe. The only string interpolation is into ffmpeg filter expressions where the inputs are numeric config values (`threshold`, `fps`, `max_width`).

**Timeouts on every external call.** `ffprobe` (30s), `_detect_scene_changes` (120s), `_extract_frame_at_timestamp` (30s), `_extract_frames_at_fps` (120s), `_download_url` (300s). A wedged subprocess can't hang the MCP server indefinitely.

**No code executed from downloads.** `yt-dlp` is invoked with `--no-playlist` and `--print after_move:filepath` so the only thing we read from its output is the final file path on disk. We do not source or execute any of the downloaded content beyond passing it back through ffprobe and ffmpeg.
