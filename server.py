"""ScreenMind — Local MCP server for screen recording comprehension.

Processes screen recordings (or any video URL via yt-dlp) into keyframes,
OCR text, audio transcript, and a temporal timeline. Returns text + file
paths; Claude reads frames with the Read tool.
"""

import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from screenmind.config import (
    CONFIG_PATH,
    DEFAULT_CONFIG,
    DOWNLOADS_DIR,
    SCREENMIND_DIR,
    SESSIONS_DIR,
    load_config,
)
from screenmind.ffmpeg import (
    detect_scene_changes,
    extract_frame_at_timestamp,
    extract_frames_at_fps,
    get_extraction_fps,
    get_video_metadata,
)
from screenmind.url_ingest import download_url, is_url
from screenmind.util import find_binary

# ---------------------------------------------------------------------------
# Optional dependency loaders — graceful degradation
# ---------------------------------------------------------------------------

_whisper_model_cache: dict = {}


def _get_ssim_func():
    """scikit-image SSIM, or None when not installed."""
    try:
        from skimage.metrics import structural_similarity
        return structural_similarity
    except ImportError:
        return None


def _get_ocr_func():
    """pytesseract image_to_string, or None when not installed."""
    try:
        import pytesseract
        tesseract_bin = find_binary("tesseract")
        if tesseract_bin:
            pytesseract.pytesseract.tesseract_cmd = tesseract_bin
        return pytesseract.image_to_string
    except ImportError:
        return None


def _get_whisper_model(model_name: str):
    """Load (and cache) a faster-whisper model. Returns None when not installed."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    if model_name in _whisper_model_cache:
        return _whisper_model_cache[model_name]
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        _whisper_model_cache[model_name] = model
        return model
    except Exception:
        return None


def _load_image_grayscale(path: str):
    """Load image as grayscale numpy array for SSIM. Returns None on failure."""
    try:
        from PIL import Image
        import numpy as np
        img = Image.open(path).convert("L")
        return np.array(img)
    except (ImportError, Exception):
        return None


# ---------------------------------------------------------------------------
# Frame pipeline (in-process — not split into its own module yet; high churn)
# ---------------------------------------------------------------------------


def _dedup_frames(
    frames: list[dict], threshold: float, preserve_indices: set[int]
) -> list[dict]:
    """Remove near-duplicate frames via SSIM. Always preserves indices in `preserve_indices`."""
    ssim_func = _get_ssim_func()
    if ssim_func is None or len(frames) <= 2:
        return frames

    kept = []
    prev_img = None

    for i, frame in enumerate(frames):
        if i in preserve_indices:
            img = _load_image_grayscale(frame["path"])
            if img is not None:
                prev_img = img
            kept.append(frame)
            continue

        img = _load_image_grayscale(frame["path"])
        if img is None:
            kept.append(frame)
            continue

        if prev_img is None:
            prev_img = img
            kept.append(frame)
            continue

        try:
            min_h = min(prev_img.shape[0], img.shape[0])
            min_w = min(prev_img.shape[1], img.shape[1])
            if min_h < 7 or min_w < 7:
                kept.append(frame)
                prev_img = img
                continue
            score = ssim_func(
                prev_img[:min_h, :min_w],
                img[:min_h, :min_w],
            )
            if score < threshold:
                kept.append(frame)
                prev_img = img
            else:
                try:
                    os.remove(frame["path"])
                except OSError:
                    pass
        except Exception:
            kept.append(frame)
            prev_img = img

    return kept


def _run_ocr(frame_path: str) -> str:
    """Run OCR on a frame. Returns empty string when OCR unavailable."""
    ocr_func = _get_ocr_func()
    if ocr_func is None:
        return ""
    try:
        from PIL import Image
        img = Image.open(frame_path)
        return ocr_func(img).strip()
    except Exception:
        return ""


def _select_best_frames(
    frames: list[dict], max_frames: int,
    scene_timestamps: list[float],
    ocr_enabled: bool,
) -> list[dict]:
    """Pick best frames within budget. Priority: first/last → scenes → OCR-change → distribution."""
    if len(frames) <= max_frames:
        if ocr_enabled:
            for frame in frames:
                if "ocr_text" not in frame:
                    frame["ocr_text"] = _run_ocr(frame["path"])
        return frames

    selected_indices: set[int] = {0, len(frames) - 1}

    for ts in scene_timestamps:
        closest_idx = min(
            range(len(frames)),
            key=lambda i: abs(frames[i]["timestamp"] - ts),
        )
        selected_indices.add(closest_idx)

    if ocr_enabled:
        prev_text = ""
        for i, frame in enumerate(frames):
            if i in selected_indices:
                text = _run_ocr(frame["path"])
                frame["ocr_text"] = text
                prev_text = text
                continue
            if len(selected_indices) < max_frames:
                text = _run_ocr(frame["path"])
                frame["ocr_text"] = text
                if prev_text and text:
                    common = sum(1 for a, b in zip(prev_text, text) if a == b)
                    max_len = max(len(prev_text), len(text), 1)
                    if common / max_len < 0.7:
                        selected_indices.add(i)
                        prev_text = text
                elif text and not prev_text:
                    selected_indices.add(i)
                    prev_text = text

    remaining = max_frames - len(selected_indices)
    if remaining > 0:
        available = [i for i in range(len(frames)) if i not in selected_indices]
        if available:
            step = max(1, len(available) // remaining)
            for i in range(0, len(available), step):
                if len(selected_indices) >= max_frames:
                    break
                selected_indices.add(available[i])

    result = []
    for i in sorted(selected_indices):
        frame = frames[i]
        if ocr_enabled and "ocr_text" not in frame:
            frame["ocr_text"] = _run_ocr(frame["path"])
        result.append(frame)

    for i, frame in enumerate(frames):
        if i not in selected_indices:
            try:
                os.remove(frame["path"])
            except OSError:
                pass
    return result


# ---------------------------------------------------------------------------
# Audio transcription (v0.3.0)
# ---------------------------------------------------------------------------


def _extract_audio(video_path: str, audio_path: str) -> bool:
    """Extract audio track to MP3. Returns False when no audio stream or ffmpeg missing."""
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        return False
    cmd = [ffmpeg, "-i", video_path, "-vn", "-acodec", "mp3", "-y", audio_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0 and os.path.exists(audio_path)


def _transcribe_audio(audio_path: str, model_name: str) -> list[dict]:
    """Transcribe an MP3 with faster-whisper. Returns list of {start, end, text} segments.

    Returns [] when whisper unavailable or transcription fails.
    """
    model = _get_whisper_model(model_name)
    if model is None:
        return []
    try:
        segments, _info = model.transcribe(audio_path, beam_size=1)
        return [
            {"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()}
            for seg in segments
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def _cleanup_old_sessions(max_kept: int) -> None:
    """Remove oldest sessions beyond max_sessions_kept."""
    if not SESSIONS_DIR.exists():
        return
    sessions = sorted(
        [d for d in SESSIONS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    for old in sessions[max_kept:]:
        shutil.rmtree(old, ignore_errors=True)


def _find_latest_recording(config: dict) -> Optional[str]:
    """Find the most recent recording in capture_dir matching file_patterns."""
    capture_dir = Path(config["capture_dir"]).expanduser()
    if not capture_dir.exists():
        return None
    candidates = []
    for pattern in config["file_patterns"]:
        candidates.extend(capture_dir.glob(pattern))
    if not candidates:
        return None
    return str(max(candidates, key=lambda f: f.stat().st_mtime))


def _parse_since(since: str) -> Optional[float]:
    """Parse a 'since' filter: ISO date or relative ('7d', '24h', '30m'). Returns epoch seconds."""
    if not since:
        return None
    m = re.fullmatch(r"(\d+)([dhm])", since.strip())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        seconds = {"d": 86400, "h": 3600, "m": 60}[unit] * n
        return time.time() - seconds
    try:
        return time.mktime(time.strptime(since.strip(), "%Y-%m-%d"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Recording state
# ---------------------------------------------------------------------------

_recording_process: Optional[subprocess.Popen] = None
_recording_output: Optional[str] = None


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("ScreenMind")


@mcp.tool()
def screenmind_watch(
    file_path: Optional[str] = None,
    focus: Optional[str] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    max_frames: Optional[int] = None,
) -> str:
    """Process a screen recording into keyframes + OCR + audio transcript + timeline.

    Args:
        file_path: Path to recording OR a URL (YouTube, Instagram, TikTok, X, 1000+ sites).
            If omitted, uses the latest recording in capture_dir.
        focus: Optional context hint (e.g. "watch the error dialog").
        start_time: Start time in seconds.
        end_time: End time in seconds.
        max_frames: Override default_max_frames from config.

    Returns:
        A text comprehension document with timeline, OCR text, audio transcript,
        and frame file paths. Use the Read tool on returned paths to inspect frames.
    """
    config = load_config()

    if file_path and is_url(file_path):
        try:
            video_path = download_url(file_path)
        except RuntimeError as e:
            return f"Download failed: {e}"
    elif file_path:
        video_path = os.path.expanduser(file_path)
    else:
        video_path = _find_latest_recording(config)

    if not video_path or not os.path.exists(video_path):
        return "No recording found. Provide a file_path (local path or URL) or place a recording in your capture_dir."

    meta = get_video_metadata(video_path)

    effective_start = start_time or 0.0
    effective_end = end_time or meta["duration"]
    if effective_start >= effective_end:
        return f"Invalid time range: start={effective_start}s >= end={effective_end}s"

    effective_duration = effective_end - effective_start

    session_id = f"{int(time.time())}_{Path(video_path).stem}"
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    frame_budget = max_frames or config["default_max_frames"]
    ocr_enabled = config["ocr_enabled"]

    # Step 1: scene detection
    scene_timestamps = detect_scene_changes(video_path, config["scene_change_threshold"])
    scene_timestamps = [ts for ts in scene_timestamps if effective_start <= ts <= effective_end]

    # Step 2: scene-change frames at exact timestamps
    scene_frames = []
    for ts in scene_timestamps:
        out_path = str(session_dir / f"scene_{ts:.3f}.jpg")
        if extract_frame_at_timestamp(
            video_path, ts, out_path,
            config["frame_quality"], config["frame_max_width"],
        ):
            scene_frames.append({"path": out_path, "timestamp": round(ts, 3), "source": "scene_change"})

    # Step 3: adaptive-FPS interval frames
    extraction_fps = get_extraction_fps(effective_duration)
    raw_dir = str(session_dir / "raw")
    os.makedirs(raw_dir, exist_ok=True)
    fps_frames = extract_frames_at_fps(
        video_path, raw_dir, extraction_fps,
        config["frame_quality"], config["frame_max_width"],
        start_time=start_time, end_time=end_time,
    )
    for f in fps_frames:
        f["source"] = "interval"

    # Merge scene + interval, prefer scene_change inside 0.3s collision window
    all_frames = scene_frames + fps_frames
    all_frames.sort(key=lambda f: f["timestamp"])

    merged: list[dict] = []
    for frame in all_frames:
        if not merged or abs(frame["timestamp"] - merged[-1]["timestamp"]) > 0.3:
            merged.append(frame)
        else:
            if frame["source"] == "scene_change" and merged[-1]["source"] != "scene_change":
                try:
                    os.remove(merged[-1]["path"])
                except OSError:
                    pass
                merged[-1] = frame
            else:
                try:
                    os.remove(frame["path"])
                except OSError:
                    pass

    # Step 4: SSIM dedup
    preserve = {0, len(merged) - 1} if merged else set()
    for i, f in enumerate(merged):
        if f["source"] == "scene_change":
            preserve.add(i)
    merged = _dedup_frames(merged, config["dedup_threshold"], preserve)

    # Step 5: smart selection within budget (runs OCR as it goes)
    selected = _select_best_frames(merged, frame_budget, scene_timestamps, ocr_enabled)

    # Step 6: move selected interval frames out of raw/ before cleanup
    for frame in selected:
        fpath = Path(frame["path"])
        if fpath.parent.name == "raw":
            new_path = session_dir / fpath.name
            shutil.move(str(fpath), str(new_path))
            frame["path"] = str(new_path)
    shutil.rmtree(raw_dir, ignore_errors=True)

    # Step 7: audio transcription (graceful degradation)
    transcript_segments: list[dict] = []
    audio_status = "disabled"
    if config.get("audio_transcription_enabled", True):
        audio_path = str(session_dir / "audio.mp3")
        if _extract_audio(video_path, audio_path):
            transcript_segments = _transcribe_audio(audio_path, config["whisper_model"])
            audio_status = "active" if transcript_segments else "unavailable (faster-whisper not installed or transcription failed)"
        else:
            audio_status = "no audio stream"

    # Step 8: auto-cleanup
    _cleanup_old_sessions(config["max_sessions_kept"])

    # Step 9: build the comprehension document
    lines = [
        "# ScreenMind Session Report",
        "",
        f"**Recording:** `{video_path}`",
        f"**Duration:** {meta['duration']:.1f}s ({meta['width']}x{meta['height']} @ {meta['fps']:.1f}fps, {meta['codec']})",
        f"**Time range:** {effective_start:.1f}s – {effective_end:.1f}s",
        f"**Frames retained:** {len(selected)} (from {len(fps_frames) + len(scene_frames)} extracted)",
        f"**Scene changes detected:** {len(scene_timestamps)}",
        f"**Session:** `{session_dir}`",
    ]
    if focus:
        lines.append(f"**Focus:** {focus}")

    ssim_available = _get_ssim_func() is not None
    ocr_available = _get_ocr_func() is not None
    lines.append(f"**SSIM dedup:** {'active' if ssim_available else 'unavailable (install scikit-image)'}")
    lines.append(
        f"**OCR:** {'active' if ocr_available and ocr_enabled else 'unavailable' if not ocr_available else 'disabled'}"
    )
    lines.append(f"**Audio transcription:** {audio_status}")

    lines.append("")
    lines.append("## Timeline")
    lines.append("")
    for i, frame in enumerate(selected):
        ts = frame["timestamp"]
        src = frame.get("source", "unknown")
        lines.append(f"### Frame {i + 1} — {ts:.1f}s [{src}]")
        lines.append(f"**File:** `{frame['path']}`")
        ocr_text = frame.get("ocr_text", "")
        if ocr_text:
            if len(ocr_text) > 500:
                ocr_text = ocr_text[:500] + "..."
            lines.append("**Visible text:**")
            lines.append("```")
            lines.append(ocr_text)
            lines.append("```")
        lines.append("")

    if transcript_segments:
        lines.append("## Audio Transcript")
        lines.append("")
        for seg in transcript_segments:
            lines.append(f"- **{seg['start']:.1f}s–{seg['end']:.1f}s** — {seg['text']}")
        lines.append("")

    lines.append("---")
    lines.append("*Use the Read tool on any frame path above to inspect it visually.*")

    report = "\n".join(lines)

    # Persist for cross-session search
    try:
        (session_dir / "report.md").write_text(report)
    except OSError:
        pass

    return report


@mcp.tool()
def screenmind_wait_for_change(
    threshold: float = 0.95,
    max_wait_seconds: int = 300,
    poll_interval: float = 1.0,
) -> str:
    """Long-poll until the screen changes, or until the timeout elapses.

    Snaps a baseline frame via avfoundation, then samples every `poll_interval`
    seconds. Returns the first frame whose SSIM similarity to the baseline
    drops below `threshold`. Useful for "tell me when the user finishes X".

    Args:
        threshold: SSIM similarity floor (0.0–1.0). Lower = more sensitive (default 0.95).
        max_wait_seconds: Hard cap, max 600s.
        poll_interval: Seconds between samples (min 0.5).

    Returns:
        Either the changed-frame report (path + timestamp + ssim score) or a
        timed-out report describing how many frames were sampled.
    """
    if max_wait_seconds > 600:
        max_wait_seconds = 600
    if poll_interval < 0.5:
        poll_interval = 0.5

    ssim_func = _get_ssim_func()
    if ssim_func is None:
        return "wait_for_change requires scikit-image. Install: pip install scikit-image"

    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        return "ffmpeg not found. Install with: brew install ffmpeg"

    config = load_config()
    screen_idx = config["avfoundation_screen_index"]
    quality = config["frame_quality"]
    max_width = config["frame_max_width"]

    session_dir = SESSIONS_DIR / f"wait_{int(time.time())}"
    session_dir.mkdir(parents=True, exist_ok=True)

    def snap(path: str) -> bool:
        cmd = [
            ffmpeg, "-f", "avfoundation",
            "-capture_cursor", "1",
            "-framerate", "30",
            "-i", f"{screen_idx}:none",
            "-frames:v", "1",
            "-q:v", str(max(1, min(31, (100 - quality) * 31 // 100))),
            "-vf", f"scale='min({max_width},iw)':-2",
            "-y", path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode == 0 and os.path.exists(path)

    baseline_path = str(session_dir / "baseline.jpg")
    if not snap(baseline_path):
        return "Failed to capture baseline frame. Check Screen Recording permission for ffmpeg."

    baseline_img = _load_image_grayscale(baseline_path)
    if baseline_img is None:
        return "Failed to load baseline frame for comparison."

    started = time.time()
    frames_checked = 0
    while time.time() - started < max_wait_seconds:
        time.sleep(poll_interval)
        frames_checked += 1
        candidate_path = str(session_dir / f"frame_{frames_checked:04d}.jpg")
        if not snap(candidate_path):
            continue
        candidate_img = _load_image_grayscale(candidate_path)
        if candidate_img is None:
            continue
        try:
            min_h = min(baseline_img.shape[0], candidate_img.shape[0])
            min_w = min(baseline_img.shape[1], candidate_img.shape[1])
            if min_h < 7 or min_w < 7:
                continue
            score = ssim_func(
                baseline_img[:min_h, :min_w],
                candidate_img[:min_h, :min_w],
            )
        except Exception:
            continue
        if score < threshold:
            elapsed = time.time() - started
            return (
                f"# ScreenMind wait_for_change — Change Detected\n\n"
                f"**Elapsed:** {elapsed:.1f}s\n"
                f"**Frames sampled:** {frames_checked}\n"
                f"**SSIM score:** {score:.3f} (threshold {threshold})\n"
                f"**Baseline:** `{baseline_path}`\n"
                f"**Changed frame:** `{candidate_path}`\n"
                f"**Session:** `{session_dir}`\n\n"
                f"*Use the Read tool on the frame paths above to inspect the change.*"
            )

    return (
        f"# ScreenMind wait_for_change — Timed Out\n\n"
        f"**Waited:** {max_wait_seconds}s\n"
        f"**Frames sampled:** {frames_checked}\n"
        f"**Threshold:** {threshold}\n"
        f"**Baseline:** `{baseline_path}`\n"
        f"**Session:** `{session_dir}`\n\n"
        f"*No SSIM drop below the threshold during the wait window.*"
    )


@mcp.tool()
def screenmind_search(
    query: str,
    limit: int = 10,
    since: Optional[str] = None,
) -> str:
    """Search across persisted session reports for OCR text or transcript matches.

    Args:
        query: Substring to match (case-insensitive).
        limit: Maximum number of session hits to return.
        since: ISO date ("2026-05-01") or relative ("24h", "7d", "30m").

    Returns:
        Ranked list of session_id + timestamp + matched snippet + frame paths.
    """
    if not query or not query.strip():
        return "Provide a non-empty query string."

    if not SESSIONS_DIR.exists():
        return "No sessions yet. Run screenmind_watch first."

    since_epoch = _parse_since(since) if since else None
    needle = query.strip().lower()

    hits: list[dict] = []
    for report_path in sorted(SESSIONS_DIR.glob("*/report.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if since_epoch is not None and report_path.stat().st_mtime < since_epoch:
            continue
        try:
            text = report_path.read_text()
        except OSError:
            continue
        if needle not in text.lower():
            continue

        # Pull the first matching line + a one-line context around it
        snippet = ""
        for line in text.splitlines():
            if needle in line.lower():
                snippet = line.strip()
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                break

        # First frame in the session as the "open this" pointer
        first_frame = next(
            (str(p) for p in sorted(report_path.parent.glob("*.jpg"))),
            "",
        )

        hits.append({
            "session_id": report_path.parent.name,
            "mtime": report_path.stat().st_mtime,
            "report_path": str(report_path),
            "first_frame": first_frame,
            "snippet": snippet,
        })
        if len(hits) >= limit:
            break

    if not hits:
        scope = f" since {since}" if since else ""
        return f"No matches for `{query}`{scope} across {len(list(SESSIONS_DIR.glob('*/report.md')))} indexed sessions."

    lines = [f"# ScreenMind search: `{query}`", "", f"**Hits:** {len(hits)}", ""]
    for h in hits:
        mtime_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(h["mtime"]))
        lines.append(f"## {h['session_id']} — {mtime_str}")
        lines.append(f"**Snippet:** {h['snippet']}")
        lines.append(f"**Report:** `{h['report_path']}`")
        if h["first_frame"]:
            lines.append(f"**First frame:** `{h['first_frame']}`")
        lines.append("")
    lines.append("*Read the report.md file or any frame path above to inspect a hit.*")
    return "\n".join(lines)


@mcp.tool()
def screenmind_record_start(
    duration: Optional[int] = None,
    output_name: Optional[str] = None,
) -> str:
    """Start recording the screen via ffmpeg avfoundation.

    Args:
        duration: Max recording duration in seconds. Defaults to max_recording_duration.
        output_name: Custom filename (without extension). Defaults to screenmind_<ts>.

    macOS Screen Recording permission required. If recordings are black, add
    ffmpeg to System Settings → Privacy & Security → Screen Recording.
    """
    global _recording_process, _recording_output

    if _recording_process is not None and _recording_process.poll() is None:
        return f"Recording already in progress → `{_recording_output}`\nUse screenmind_record_stop to stop it."

    config = load_config()
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        return "ffmpeg not found. Install with: brew install ffmpeg"

    max_dur = duration or config["max_recording_duration"]
    name = output_name or f"screenmind_{int(time.time())}"
    capture_dir = Path(config["capture_dir"]).expanduser()
    capture_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(capture_dir / f"{name}.mov")

    screen_idx = config["avfoundation_screen_index"]
    cmd = [
        ffmpeg, "-f", "avfoundation",
        "-capture_cursor", "1",
        "-i", f"{screen_idx}:none",
        "-t", str(max_dur),
        "-pix_fmt", "yuv420p",
        "-y", output_path,
    ]
    _recording_process = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    _recording_output = output_path

    return (
        f"Recording started → `{output_path}`\n"
        f"Max duration: {max_dur}s\n"
        f"Screen index: {screen_idx}\n"
        f"Use `screenmind_record_stop` to stop early."
    )


@mcp.tool()
def screenmind_record_stop() -> str:
    """Stop the active screen recording (SIGINT for a clean ffmpeg shutdown)."""
    global _recording_process, _recording_output

    if _recording_process is None or _recording_process.poll() is not None:
        _recording_process = None
        path_info = f" Last output: `{_recording_output}`" if _recording_output else ""
        return f"No active recording.{path_info}"

    _recording_process.send_signal(signal.SIGINT)
    try:
        _recording_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _recording_process.kill()
        _recording_process.wait(timeout=5)

    output = _recording_output
    _recording_process = None
    _recording_output = None

    if output and os.path.exists(output):
        size_mb = os.path.getsize(output) / (1024 * 1024)
        return f"Recording saved → `{output}` ({size_mb:.1f} MB)"
    return f"Recording stopped but output file not found at `{output}`"


@mcp.tool()
def screenmind_list(limit: int = 10) -> str:
    """List recordings in the capture directory, newest first."""
    config = load_config()
    capture_dir = Path(config["capture_dir"]).expanduser()
    if not capture_dir.exists():
        return f"Capture directory not found: `{capture_dir}`"

    candidates = []
    for pattern in config["file_patterns"]:
        candidates.extend(capture_dir.glob(pattern))
    if not candidates:
        return f"No recordings found in `{capture_dir}`"

    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    candidates = candidates[:limit]

    lines = [f"## Recordings in `{capture_dir}`", ""]
    for f in candidates:
        stat = f.stat()
        size_mb = stat.st_size / (1024 * 1024)
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
        lines.append(f"- `{f}` — {size_mb:.1f} MB, {mtime}")
    return "\n".join(lines)


@mcp.tool()
def screenmind_status() -> str:
    """Show recording state, session count, and dependency availability."""
    global _recording_process, _recording_output

    lines = ["## ScreenMind Status", ""]

    if _recording_process is not None and _recording_process.poll() is None:
        lines.append(f"**Recording:** ACTIVE → `{_recording_output}`")
    else:
        lines.append("**Recording:** inactive")
        if _recording_process is not None:
            _recording_process = None

    if SESSIONS_DIR.exists():
        sessions = [d for d in SESSIONS_DIR.iterdir() if d.is_dir()]
        lines.append(f"**Sessions stored:** {len(sessions)}")
    else:
        lines.append("**Sessions stored:** 0")

    config = load_config()
    lines.append(f"**Capture dir:** `{config['capture_dir']}`")
    lines.append(f"**Max frames:** {config['default_max_frames']}")
    lines.append(f"**Screen index:** {config['avfoundation_screen_index']}")
    lines.append(f"**Whisper model:** {config['whisper_model']}")

    ssim = _get_ssim_func() is not None
    ocr = _get_ocr_func() is not None
    whisper_available = False
    try:
        import faster_whisper  # noqa: F401
        whisper_available = True
    except ImportError:
        pass
    lines.append(f"**SSIM dedup:** {'available' if ssim else 'not installed'}")
    lines.append(f"**OCR:** {'available' if ocr else 'not installed'}")
    lines.append(f"**Audio transcription:** {'available' if whisper_available else 'not installed (pip install faster-whisper)'}")

    ffmpeg = find_binary("ffmpeg")
    ffprobe = find_binary("ffprobe")
    tesseract = find_binary("tesseract")
    yt_dlp = find_binary("yt-dlp")
    lines.append(f"**ffmpeg:** `{ffmpeg or 'NOT FOUND'}`")
    lines.append(f"**ffprobe:** `{ffprobe or 'NOT FOUND'}`")
    lines.append(f"**tesseract:** `{tesseract or 'not installed'}`")
    lines.append(f"**yt-dlp:** `{yt_dlp or 'not installed (URL ingest disabled)'}`")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
