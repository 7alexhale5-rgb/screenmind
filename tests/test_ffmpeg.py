"""Pure-function tests for ffmpeg helpers — no real ffmpeg invocation."""

import pytest

from screenmind.ffmpeg import get_extraction_fps, parse_frame_rate


@pytest.mark.parametrize("input_str,expected", [
    ("30/1", 30.0),
    ("60/1", 60.0),
    ("30000/1001", pytest.approx(29.97, rel=0.001)),
    ("25/1", 25.0),
    ("29.97", pytest.approx(29.97)),
    ("0/1", 0.0),
])
def test_parse_frame_rate_supported(input_str, expected):
    assert parse_frame_rate(input_str) == expected


@pytest.mark.parametrize("malformed", [
    "30/0",      # zero denominator
    "garbage",
    "/",
    "30/x",
    "",
])
def test_parse_frame_rate_falls_back_to_30(malformed):
    assert parse_frame_rate(malformed) == 30.0


def test_extraction_fps_short_clip():
    # Short clip → dense sampling
    assert get_extraction_fps(5) == 2.0
    assert get_extraction_fps(15) == 2.0


def test_extraction_fps_medium_clip():
    # 15 < d <= 60 → 1 fps
    assert get_extraction_fps(15.1) == 1.0
    assert get_extraction_fps(60) == 1.0


def test_extraction_fps_long_clip():
    # > 60s → 0.5 fps
    assert get_extraction_fps(60.1) == 0.5
    assert get_extraction_fps(600) == 0.5


@pytest.mark.parametrize("bad_fps", [0, -1, -0.5])
def test_extract_frames_at_fps_rejects_non_positive_fps(bad_fps, tmp_path):
    """fps <= 0 would make the downstream `timestamp = offset + i / fps` blow up.

    Better to fail loudly at the function boundary than emit a confusing
    ZeroDivisionError or hand ffmpeg a malformed filter chain.
    """
    from screenmind.ffmpeg import extract_frames_at_fps

    with pytest.raises(ValueError, match="fps must be positive"):
        extract_frames_at_fps(
            video_path="/nonexistent.mov",
            output_dir=str(tmp_path),
            fps=bad_fps,
            quality=80,
            max_width=1280,
        )
