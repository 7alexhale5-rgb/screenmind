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


# --- scene detection on long, high-res captures -----------------------------
# 2026-09-29: a 190.9s 1320x2868 @ 60fps iPhone capture hit the flat 120s
# timeout in the scene pass and the TimeoutExpired killed screenmind_watch.


def test_pass_timeout_scales_with_duration_above_the_old_floor():
    from screenmind.ffmpeg import pass_timeout

    assert pass_timeout(0) == 120.0
    assert pass_timeout(60) == 120.0
    assert pass_timeout(190.9) == 190.9
    assert pass_timeout(3180) == 3180


def _capture_run(monkeypatch, stderr="", exc=None):
    """Patch find_binary + subprocess.run in screenmind.ffmpeg; return the call log."""
    import subprocess

    import screenmind.ffmpeg as ff

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, **kwargs})
        if exc is not None:
            raise exc
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=stderr)

    monkeypatch.setattr(ff, "find_binary", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(ff.subprocess, "run", fake_run)
    return calls


def test_scene_pass_downscales_and_drops_fps_before_scoring(monkeypatch):
    from screenmind.ffmpeg import detect_scene_changes

    calls = _capture_run(monkeypatch)
    detect_scene_changes("/v.mov", 0.3, duration=190.9)

    cmd = calls[0]["cmd"]
    vf = cmd[cmd.index("-vf") + 1]
    # The prefilter must come BEFORE select, or the scene score still runs at full size.
    assert vf.startswith("fps=10,scale=480:-2,select='gt(scene,0.3)'")
    assert "-an" in cmd and cmd.index("-an") < cmd.index("-i")
    assert calls[0]["timeout"] == 190.9


def test_scene_pass_parses_real_pts_times(monkeypatch):
    from screenmind.ffmpeg import detect_scene_changes

    stderr = (
        "[Parsed_showinfo_3 @ 0x1] n:   0 pts:  12 pts_time:1.2 duration:1\n"
        "noise line\n"
        "[Parsed_showinfo_3 @ 0x1] n:   1 pts: 473 pts_time:47.3 duration:1\n"
    )
    _capture_run(monkeypatch, stderr=stderr)
    assert detect_scene_changes("/v.mov", 0.3, duration=60) == [1.2, 47.3]


def test_scene_pass_timeout_returns_none_instead_of_raising(monkeypatch):
    import subprocess

    from screenmind.ffmpeg import detect_scene_changes

    _capture_run(monkeypatch, exc=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=190.9))
    assert detect_scene_changes("/v.mov", 0.3, duration=190.9) is None


def test_interval_pass_timeout_scales_with_window(monkeypatch, tmp_path):
    from screenmind.ffmpeg import extract_frames_at_fps

    calls = _capture_run(monkeypatch)
    extract_frames_at_fps("/v.mov", str(tmp_path), 2.0, 80, 1280, duration=450)
    assert calls[0]["timeout"] == 450
