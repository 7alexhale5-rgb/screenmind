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


def test_extraction_fps_is_flat_at_the_house_standard():
    # 2 fps, every frame, is the shipped contract (SKILL.md). Duration alone
    # must not lower it: the old 15s/60s tiers quietly quartered the density
    # on exactly the multi-minute captures this tool exists for.
    for duration in (5, 15, 15.1, 60, 60.1, 300, 450):
        assert get_extraction_fps(duration) == 2.0, f"{duration}s should stay at 2 fps"


def test_extraction_fps_degrades_only_at_the_frame_budget():
    # 900 frames is 7.5 minutes at 2 fps. At the boundary we are still flat.
    assert get_extraction_fps(450) == 2.0
    # Past it, sample as densely as the budget allows rather than blowing it.
    assert get_extraction_fps(900) == 1.0
    assert get_extraction_fps(1800) == 0.5
    # And never exceed the budget, whatever the duration.
    for duration in (451, 900, 1800, 7200):
        assert get_extraction_fps(duration) * duration <= 900 + 1e-9


def test_extraction_fps_honours_overrides():
    assert get_extraction_fps(100, target_fps=4.0) == 4.0
    assert get_extraction_fps(100, target_fps=4.0, ceiling=200) == 2.0
    # A zero or negative duration must not divide by zero.
    assert get_extraction_fps(0) == 2.0


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
