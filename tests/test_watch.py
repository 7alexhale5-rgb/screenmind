"""End-to-end screenmind_watch on a real (synthetic) clip. Needs ffmpeg + fastmcp."""

import json
import shutil
import subprocess

import pytest

pytest.importorskip("fastmcp")
if not shutil.which("ffmpeg"):
    pytest.skip("ffmpeg not installed", allow_module_level=True)


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30",
         "-t", "5", "-pix_fmt", "yuv420p", "-y", str(path)],
        check=True,
    )
    return path


@pytest.fixture
def watch(tmp_screenmind_dir, monkeypatch):
    import server

    # conftest patches server's path aliases only if server was imported first.
    monkeypatch.setattr(server, "SESSIONS_DIR", tmp_screenmind_dir / "sessions")
    (tmp_screenmind_dir / "config.json").write_text(json.dumps({
        "ocr_enabled": False, "audio_transcription_enabled": False,
    }))
    return server.screenmind_watch


def test_report_opens_with_sample_density(clip, watch):
    report = watch(file_path=str(clip))
    lines = report.splitlines()
    assert lines[0] == "# ScreenMind Session Report"
    assert lines[2].startswith("**Sample density:** target 2 fps = 10 frames over 5.0s")


def test_scene_timeout_degrades_to_interval_frames(clip, watch, monkeypatch):
    import screenmind.ffmpeg as ff

    real_run = subprocess.run

    def run(cmd, **kwargs):
        if any("select=" in str(arg) for arg in cmd):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(ff.subprocess, "run", run)
    report = watch(file_path=str(clip))

    assert "**Scene changes detected:** timed out; scene frames skipped" in report
    assert "[interval]" in report
    assert "[scene_change]" not in report
