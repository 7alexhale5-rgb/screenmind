"""Pytest fixtures — isolate every test from the real ~/.screenmind/ directory."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_screenmind_dir(tmp_path, monkeypatch):
    """Redirect SCREENMIND_DIR (and its children) into a tmpdir for the test.

    Patches both the `screenmind.config` module attributes and any already-imported
    aliases in `server` so MCP tools see the same redirected paths.
    """
    import screenmind.config as cfg

    tmp_root = tmp_path / ".screenmind"
    tmp_root.mkdir()

    monkeypatch.setattr(cfg, "SCREENMIND_DIR", tmp_root)
    monkeypatch.setattr(cfg, "SESSIONS_DIR", tmp_root / "sessions")
    monkeypatch.setattr(cfg, "DOWNLOADS_DIR", tmp_root / "downloads")
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_root / "config.json")

    return tmp_root


@pytest.fixture
def fake_binary(tmp_path, monkeypatch):
    """Build a no-op shell script and return its path. Patches find_binary to return it."""
    fake = tmp_path / "fake-bin"
    fake.write_text("#!/usr/bin/env bash\nexit 0\n")
    fake.chmod(0o755)

    import screenmind.util as util

    def _fake_find(name: str):
        return str(fake)

    monkeypatch.setattr(util, "find_binary", _fake_find)
    monkeypatch.setattr(util, "_binary_cache", {})
    return Path(fake)
