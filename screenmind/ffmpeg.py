"""ffmpeg / ffprobe wrappers — pure I/O, no MCP state."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from screenmind.util import find_binary


def get_video_metadata(video_path: str) -> dict:
    """Extract video metadata via ffprobe.

    Returns dict with duration, width, height, fps, codec. Raises RuntimeError on failure.
    """
    ffprobe = find_binary("ffprobe")
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

    fps = parse_frame_rate(video_stream.get("r_frame_rate", "30/1"))

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "codec": video_stream.get("codec_name", "unknown"),
    }


def parse_frame_rate(fps_str: str) -> float:
    """Parse ffprobe frame-rate string ('30/1', '30000/1001', '29.97') without eval.

    Falls back to 30.0 on malformed input or zero denominator.
    """
    if "/" in fps_str:
        try:
            num, den = fps_str.split("/", 1)
            den_f = float(den)
            if den_f == 0:
                return 30.0
            return float(num) / den_f
        except (ValueError, IndexError):
            return 30.0
    try:
        return float(fps_str)
    except ValueError:
        return 30.0


def get_extraction_fps(duration: float) -> float:
    """Adaptive FPS based on clip duration. Short clips → denser sampling."""
    if duration <= 15:
        return 2.0
    elif duration <= 60:
        return 1.0
    else:
        return 0.5


def detect_scene_changes(video_path: str, threshold: float) -> list[float]:
    """Detect scene-change timestamps using ffmpeg showinfo. Parses real pts_time."""
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        return []

    cmd = [
        ffmpeg, "-i", video_path,
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-vsync", "vfr",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    timestamps: list[float] = []
    for line in result.stderr.splitlines():
        if "pts_time:" in line:
            match = re.search(r"pts_time:\s*([\d.]+)", line)
            if match:
                timestamps.append(float(match.group(1)))
    return timestamps


def extract_frame_at_timestamp(
    video_path: str, timestamp: float, output_path: str,
    quality: int, max_width: int,
) -> bool:
    """Extract a single frame at an exact timestamp. Returns True on success."""
    ffmpeg = find_binary("ffmpeg")
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


def extract_frames_at_fps(
    video_path: str, output_dir: str, fps: float,
    quality: int, max_width: int,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> list[dict]:
    """Extract frames at a given FPS rate. Returns list of {path, timestamp}."""
    if fps <= 0:
        # ffmpeg's fps filter would emit garbage; downstream `i / fps` would also blow up.
        raise ValueError(f"fps must be positive, got {fps}")
    ffmpeg = find_binary("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    input_args: list[str] = []
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

    frames: list[dict] = []
    offset = start_time or 0.0
    frame_files = sorted(Path(output_dir).glob("frame_*.jpg"))
    for i, fp in enumerate(frame_files):
        timestamp = offset + i / fps
        frames.append({"path": str(fp), "timestamp": round(timestamp, 3)})
    return frames
