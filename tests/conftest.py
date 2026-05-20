"""Pytest fixtures — isolate every test from the real ~/.screenmind/ directory."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_screenmind_dir(tmp_path, monkeypatch):
    """Redirect SCREENMIND_DIR (and its children) into a tmpdir for the test.

    Patches both the `screenmind.config` module attributes and — if `server`
    has been imported in this test session — its `from screenmind.config import`
    aliases as well. The server.py import is best-effort because `fastmcp` is
    an optional transitive dep for unit tests that only touch the package.
    """
    import screenmind.config as cfg

    tmp_root = tmp_path / ".screenmind"
    tmp_root.mkdir()

    monkeypatch.setattr(cfg, "SCREENMIND_DIR", tmp_root)
    monkeypatch.setattr(cfg, "SESSIONS_DIR", tmp_root / "sessions")
    monkeypatch.setattr(cfg, "DOWNLOADS_DIR", tmp_root / "downloads")
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_root / "config.json")

    # If server.py is already loaded, its bound copies of the path constants
    # also need patching — `from X import Y` snapshots Y at import time, so
    # mutating X.Y after the fact doesn't affect the importer.
    import sys
    if "server" in sys.modules:
        server = sys.modules["server"]
        for attr in ("SCREENMIND_DIR", "SESSIONS_DIR", "DOWNLOADS_DIR", "CONFIG_PATH"):
            if hasattr(server, attr):
                monkeypatch.setattr(server, attr, getattr(cfg, attr))

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

    # Same `from X import Y` snapshot problem as above — patch any importers.
    import sys
    for modname in ("server", "screenmind.ffmpeg", "screenmind.url_ingest"):
        if modname in sys.modules and hasattr(sys.modules[modname], "find_binary"):
            monkeypatch.setattr(sys.modules[modname], "find_binary", _fake_find)

    return Path(fake)
