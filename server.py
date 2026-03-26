"""ScreenMind — Local MCP server for screen recording comprehension.

Processes screen recordings into keyframes + OCR + timeline,
giving Claude behavioral context from interaction sequences.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCREENMIND_DIR = Path.home() / ".screenmind"
SESSIONS_DIR = SCREENMIND_DIR / "sessions"
CONFIG_PATH = SCREENMIND_DIR / "config.json"

DEFAULT_CONFIG = {
    "capture_dir": "~/Desktop",
    "file_patterns": ["*.mov", "*.mp4", "*.mkv"],
    "max_recording_duration": 120,
    "default_max_frames": 15,
    "frame_quality": 80,
    "frame_max_width": 1280,
    "dedup_threshold": 0.95,
    "scene_change_threshold": 0.3,
    "ocr_enabled": True,
    "avfoundation_screen_index": "1",
    "max_sessions_kept": 20,
}

# ---------------------------------------------------------------------------
# Binary lookup cache
# ---------------------------------------------------------------------------

_binary_cache: dict[str, Optional[str]] = {}


def _find_binary(name: str) -> Optional[str]:
    """Find a binary, checking /opt/homebrew/bin/ first for Apple Silicon."""
    if name in _binary_cache:
        return _binary_cache[name]

    # Apple Silicon Homebrew first
    homebrew_path = f"/opt/homebrew/bin/{name}"
    if os.path.isfile(homebrew_path) and os.access(homebrew_path, os.X_OK):
        _binary_cache[name] = homebrew_path
        return homebrew_path

    # Fall back to PATH
    result = shutil.which(name)
    _binary_cache[name] = result
    return result


# ---------------------------------------------------------------------------
# Config management
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    """Load config from ~/.screenmind/config.json, creating defaults if missing."""
    SCREENMIND_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            user_config = json.load(f)
        # Merge with defaults for any missing keys
        merged = {**DEFAULT_CONFIG, **user_config}
        return merged

    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    return dict(DEFAULT_CONFIG)


# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------


def _get_ssim_func():
    """Try to import SSIM from scikit-image. Returns None if unavailable."""
    try:
        from skimage.metrics import structural_similarity
        return structural_similarity
    except ImportError:
        return None


def _get_ocr_func():
    """Try to import pytesseract. Returns None if unavailable."""
    try:
        import pytesseract
        tesseract_bin = _find_binary("tesseract")
        if tesseract_bin:
            pytesseract.pytesseract.tesseract_cmd = tesseract_bin
        return pytesseract.image_to_string
    except ImportError:
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
# ffmpeg / ffprobe helpers
# ---------------------------------------------------------------------------


def _get_video_metadata(video_path: str) -> dict:
    """Extract video metadata via ffprobe."""
    ffprobe = _find_binary("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not found. Install ffmpeg: brew install ffmpeg")

    cmd = [
        ffprobe, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)

    # Find video stream
    video_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        raise RuntimeError("No video stream found in file")

    duration = float(data.get("format", {}).get("duration", 0))
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    # Parse frame rate without eval — split on / and divide
    fps_str = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    else:
        fps = float(fps_str)

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "codec": video_stream.get("codec_name", "unknown"),
    }


def _get_extraction_fps(duration: float) -> float:
    """Adaptive FPS based on recording duration."""
    if duration <= 15:
        return 2.0
    elif duration <= 60:
        return 1.0
    else:
        return 0.5


def _detect_scene_changes(video_path: str, threshold: float) -> list[float]:
    """Detect scene change timestamps using ffmpeg showinfo filter.

    Parses pts_time from showinfo output — NOT estimated.
    """
    ffmpeg = _find_binary("ffmpeg")
    if not ffmpeg:
        return []

    cmd = [
        ffmpeg, "-i", video_path,
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-vsync", "vfr",
        "-f", "null", "-",
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120
    )

    # Parse pts_time from showinfo output (appears in stderr)
    timestamps = []
    for line in result.stderr.splitlines():
        if "pts_time:" in line:
            match = re.search(r"pts_time:\s*([\d.]+)", line)
            if match:
                timestamps.append(float(match.group(1)))

    return timestamps


def _extract_frame_at_timestamp(
    video_path: str, timestamp: float, output_path: str,
    quality: int, max_width: int
) -> bool:
    """Extract a single frame at an exact timestamp."""
    ffmpeg = _find_binary("ffmpeg")
    if not ffmpeg:
        return False

    cmd = [
        ffmpeg, "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", str(max(1, min(31, (100 - quality) * 31 // 100))),
        "-vf", f"scale='min({max_width},iw)':-2",
        "-y", output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0 and os.path.exists(output_path)


def _extract_frames_at_fps(
    video_path: str, output_dir: str, fps: float,
    quality: int, max_width: int,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> list[dict]:
    """Extract frames at a given FPS rate. Returns list of {path, timestamp}."""
    ffmpeg = _find_binary("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    input_args = []
    if start_time is not None:
        input_args.extend(["-ss", str(start_time)])
    input_args.extend(["-i", video_path])
    if end_time is not None:
        duration = end_time - (start_time or 0)
        input_args.extend(["-t", str(duration)])

    pattern = os.path.join(output_dir, "frame_%05d.jpg")

    cmd = [
        ffmpeg, *input_args,
        "-vf", f"fps={fps},scale='min({max_width},iw)':-2",
        "-q:v", str(max(1, min(31, (100 - quality) * 31 // 100))),
        "-y", pattern,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Frame extraction failed: {result.stderr[:500]}")

    # Collect extracted frames with timestamps
    frames = []
    offset = start_time or 0.0
    frame_files = sorted(Path(output_dir).glob("frame_*.jpg"))
    for i, fp in enumerate(frame_files):
        timestamp = offset + i / fps
        frames.append({"path": str(fp), "timestamp": round(timestamp, 3)})

    return frames


# ---------------------------------------------------------------------------
# Frame processing pipeline
# ---------------------------------------------------------------------------


def _dedup_frames(
    frames: list[dict], threshold: float, preserve_indices: set[int]
) -> list[dict]:
    """Remove near-duplicate frames using SSIM. Always preserves first and last."""
    ssim_func = _get_ssim_func()
    if ssim_func is None or len(frames) <= 2:
        return frames

    kept = []
    prev_img = None

    for i, frame in enumerate(frames):
        # Always keep first, last, and explicitly preserved frames
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

        # Compare with previous kept frame
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
                # Remove the duplicate file
                try:
                    os.remove(frame["path"])
                except OSError:
                    pass
        except Exception:
            kept.append(frame)
            prev_img = img

    return kept


def _run_ocr(frame_path: str) -> str:
    """Run OCR on a frame. Returns empty string if unavailable."""
    ocr_func = _get_ocr_func()
    if ocr_func is None:
        return ""
    try:
        from PIL import Image
        img = Image.open(frame_path)
        text = ocr_func(img).strip()
        return text
    except Exception:
        return ""


def _select_best_frames(
    frames: list[dict], max_frames: int,
    scene_timestamps: list[float],
    ocr_enabled: bool,
) -> list[dict]:
    """Select best frames when over budget, following priority rules.

    Priority:
    1. First and last frame (always kept)
    2. Scene change frames
    3. Frames where OCR text changed significantly
    4. Evenly distributed remainder
    """
    if len(frames) <= max_frames:
        # Run OCR on all if enabled
        if ocr_enabled:
            for frame in frames:
                if "ocr_text" not in frame:
                    frame["ocr_text"] = _run_ocr(frame["path"])
        return frames

    selected_indices: set[int] = set()

    # 1. First and last
    selected_indices.add(0)
    selected_indices.add(len(frames) - 1)

    # 2. Scene change frames (closest frame to each scene timestamp)
    for ts in scene_timestamps:
        closest_idx = min(
            range(len(frames)),
            key=lambda i: abs(frames[i]["timestamp"] - ts),
        )
        selected_indices.add(closest_idx)

    # 3. OCR text change detection
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
                # Significant change = more than 30% different characters
                if prev_text and text:
                    common = sum(1 for a, b in zip(prev_text, text) if a == b)
                    max_len = max(len(prev_text), len(text), 1)
                    if common / max_len < 0.7:
                        selected_indices.add(i)
                        prev_text = text
                elif text and not prev_text:
                    selected_indices.add(i)
                    prev_text = text

    # 4. Fill remaining budget with evenly distributed frames
    remaining = max_frames - len(selected_indices)
    if remaining > 0:
        available = [i for i in range(len(frames)) if i not in selected_indices]
        if available:
            step = max(1, len(available) // remaining)
            for i in range(0, len(available), step):
                if len(selected_indices) >= max_frames:
                    break
                selected_indices.add(available[i])

    # Build result in order
    result = []
    for i in sorted(selected_indices):
        frame = frames[i]
        if ocr_enabled and "ocr_text" not in frame:
            frame["ocr_text"] = _run_ocr(frame["path"])
        result.append(frame)

    # Clean up unselected frame files
    for i, frame in enumerate(frames):
        if i not in selected_indices:
            try:
                os.remove(frame["path"])
            except OSError:
                pass

    return result


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


# ---------------------------------------------------------------------------
# Recording state
# ---------------------------------------------------------------------------

_recording_process: Optional[subprocess.Popen] = None
_recording_output: Optional[str] = None


# ---------------------------------------------------------------------------
# MCP Server
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
    """Process a screen recording into keyframes + OCR + timeline.

    Args:
        file_path: Path to recording. If omitted, uses the latest recording in capture_dir.
        focus: Optional context hint (e.g. "watch the error dialog" or "track the form flow").
        start_time: Start time in seconds to examine a specific segment.
        end_time: End time in seconds to examine a specific segment.
        max_frames: Override default_max_frames from config.

    Returns:
        A text comprehension document with timeline, OCR text, and frame file paths.
        Use the Read tool on returned file paths to inspect specific frames.
    """
    config = _load_config()

    # Resolve video file
    if file_path:
        video_path = os.path.expanduser(file_path)
    else:
        video_path = _find_latest_recording(config)

    if not video_path or not os.path.exists(video_path):
        return "No recording found. Provide a file_path or place a recording in your capture_dir."

    # Get metadata
    meta = _get_video_metadata(video_path)

    # Validate time range
    effective_start = start_time or 0.0
    effective_end = end_time or meta["duration"]
    if effective_start >= effective_end:
        return f"Invalid time range: start={effective_start}s >= end={effective_end}s"

    effective_duration = effective_end - effective_start

    # Create session
    session_id = f"{int(time.time())}_{Path(video_path).stem}"
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    frame_budget = max_frames or config["default_max_frames"]
    ocr_enabled = config["ocr_enabled"]

    # Step 1: Detect scene changes
    scene_timestamps = _detect_scene_changes(
        video_path, config["scene_change_threshold"]
    )
    # Filter to time range
    scene_timestamps = [
        ts for ts in scene_timestamps
        if effective_start <= ts <= effective_end
    ]

    # Step 2: Extract scene change frames at exact timestamps
    scene_frames = []
    for ts in scene_timestamps:
        out_path = str(session_dir / f"scene_{ts:.3f}.jpg")
        if _extract_frame_at_timestamp(
            video_path, ts, out_path,
            config["frame_quality"], config["frame_max_width"]
        ):
            scene_frames.append({"path": out_path, "timestamp": round(ts, 3), "source": "scene_change"})

    # Step 3: Extract frames at adaptive FPS
    extraction_fps = _get_extraction_fps(effective_duration)
    raw_dir = str(session_dir / "raw")
    os.makedirs(raw_dir, exist_ok=True)
    fps_frames = _extract_frames_at_fps(
        video_path, raw_dir, extraction_fps,
        config["frame_quality"], config["frame_max_width"],
        start_time=start_time, end_time=end_time,
    )

    # Tag source
    for f in fps_frames:
        f["source"] = "interval"

    # Merge scene frames and interval frames, remove timestamp-duplicates
    all_frames = scene_frames + fps_frames
    all_frames.sort(key=lambda f: f["timestamp"])

    # Deduplicate by timestamp proximity (within 0.3s)
    merged = []
    for frame in all_frames:
        if not merged or abs(frame["timestamp"] - merged[-1]["timestamp"]) > 0.3:
            merged.append(frame)
        else:
            # Prefer scene_change over interval
            if frame["source"] == "scene_change" and merged[-1]["source"] != "scene_change":
                # Remove the interval frame file
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

    # Step 4: SSIM deduplication
    preserve = {0, len(merged) - 1} if merged else set()
    # Also preserve scene change frames
    for i, f in enumerate(merged):
        if f["source"] == "scene_change":
            preserve.add(i)

    merged = _dedup_frames(merged, config["dedup_threshold"], preserve)

    # Step 5: Select best frames within budget
    selected = _select_best_frames(
        merged, frame_budget, scene_timestamps, ocr_enabled
    )

    # Move selected interval frames out of raw/ before cleanup
    for frame in selected:
        fpath = Path(frame["path"])
        if fpath.parent.name == "raw":
            new_path = session_dir / fpath.name
            shutil.move(str(fpath), str(new_path))
            frame["path"] = str(new_path)

    # Clean up raw directory
    shutil.rmtree(raw_dir, ignore_errors=True)

    # Step 6: Auto-cleanup old sessions
    _cleanup_old_sessions(config["max_sessions_kept"])

    # Step 7: Build comprehension document
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
    lines.append(f"**OCR:** {'active' if ocr_available and ocr_enabled else 'unavailable' if not ocr_available else 'disabled'}")

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
            # Truncate very long OCR
            if len(ocr_text) > 500:
                ocr_text = ocr_text[:500] + "..."
            lines.append(f"**Visible text:**")
            lines.append(f"```")
            lines.append(ocr_text)
            lines.append(f"```")

        lines.append("")

    lines.append("---")
    lines.append("*Use the Read tool on any frame path above to inspect it visually.*")

    return "\n".join(lines)


@mcp.tool()
def screenmind_record_start(
    duration: Optional[int] = None,
    output_name: Optional[str] = None,
) -> str:
    """Start recording the screen via ffmpeg avfoundation.

    Args:
        duration: Max recording duration in seconds. Defaults to config max_recording_duration.
        output_name: Custom filename (without extension). Defaults to screenmind_<timestamp>.

    Returns:
        Status message with the output file path.

    Note — macOS Screen Recording Permission:
        The first time you use this, macOS will prompt for Screen Recording permission.
        If ffmpeg is not listed in System Settings → Privacy & Security → Screen Recording,
        you must add it manually:
        1. Open System Settings → Privacy & Security → Screen Recording
        2. Click '+' and add /opt/homebrew/bin/ffmpeg (or your ffmpeg path)
        3. Restart your terminal
        If recording captures a black screen, this permission is the most likely cause.
    """
    global _recording_process, _recording_output

    if _recording_process is not None and _recording_process.poll() is None:
        return f"Recording already in progress → `{_recording_output}`\nUse screenmind_record_stop to stop it."

    config = _load_config()
    ffmpeg = _find_binary("ffmpeg")
    if not ffmpeg:
        return "ffmpeg not found. Install with: brew install ffmpeg"

    max_dur = duration or config["max_recording_duration"]
    name = output_name or f"screenmind_{int(time.time())}"
    capture_dir = Path(config["capture_dir"]).expanduser()
    capture_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(capture_dir / f"{name}.mov")

    screen_idx = config["avfoundation_screen_index"]

    cmd = [
        ffmpeg,
        "-f", "avfoundation",
        "-capture_cursor", "1",
        "-i", f"{screen_idx}:none",
        "-t", str(max_dur),
        "-pix_fmt", "yuv420p",
        "-y", output_path,
    ]

    _recording_process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
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
    """Stop the active screen recording.

    Returns:
        Status message with the saved file path.
    """
    global _recording_process, _recording_output

    if _recording_process is None or _recording_process.poll() is not None:
        _recording_process = None
        path_info = f" Last output: `{_recording_output}`" if _recording_output else ""
        return f"No active recording.{path_info}"

    # Send SIGINT for clean ffmpeg shutdown (writes proper file trailer)
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
    else:
        return f"Recording stopped but output file not found at `{output}`"


@mcp.tool()
def screenmind_list(limit: int = 10) -> str:
    """List available screen recordings in the capture directory.

    Args:
        limit: Maximum number of recordings to list. Defaults to 10.

    Returns:
        Formatted list of recordings with metadata.
    """
    config = _load_config()
    capture_dir = Path(config["capture_dir"]).expanduser()

    if not capture_dir.exists():
        return f"Capture directory not found: `{capture_dir}`"

    candidates = []
    for pattern in config["file_patterns"]:
        candidates.extend(capture_dir.glob(pattern))

    if not candidates:
        return f"No recordings found in `{capture_dir}`"

    # Sort by modification time, newest first
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
    """Check if a screen recording is currently active.

    Returns:
        Recording status and session statistics.
    """
    global _recording_process, _recording_output

    lines = ["## ScreenMind Status", ""]

    # Recording status
    if _recording_process is not None and _recording_process.poll() is None:
        lines.append(f"**Recording:** ACTIVE → `{_recording_output}`")
    else:
        lines.append("**Recording:** inactive")
        if _recording_process is not None:
            _recording_process = None

    # Session count
    if SESSIONS_DIR.exists():
        sessions = [d for d in SESSIONS_DIR.iterdir() if d.is_dir()]
        lines.append(f"**Sessions stored:** {len(sessions)}")
    else:
        lines.append("**Sessions stored:** 0")

    # Config
    config = _load_config()
    lines.append(f"**Capture dir:** `{config['capture_dir']}`")
    lines.append(f"**Max frames:** {config['default_max_frames']}")
    lines.append(f"**Screen index:** {config['avfoundation_screen_index']}")

    # Dependencies
    ssim = _get_ssim_func() is not None
    ocr = _get_ocr_func() is not None
    lines.append(f"**SSIM dedup:** {'available' if ssim else 'not installed'}")
    lines.append(f"**OCR:** {'available' if ocr else 'not installed'}")

    # Binaries
    ffmpeg = _find_binary("ffmpeg")
    ffprobe = _find_binary("ffprobe")
    tesseract = _find_binary("tesseract")
    lines.append(f"**ffmpeg:** `{ffmpeg or 'NOT FOUND'}`")
    lines.append(f"**ffprobe:** `{ffprobe or 'NOT FOUND'}`")
    lines.append(f"**tesseract:** `{tesseract or 'not installed'}`")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
