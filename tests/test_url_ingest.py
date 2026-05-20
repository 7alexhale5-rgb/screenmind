"""URL detection — covers the boundary that decides 'download' vs 'local path'."""

import pytest

from screenmind.url_ingest import is_url


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "http://example.com/path",
    "https://example.com:8080/foo",
    "https://www.instagram.com/reel/ABC123/",
    "https://tiktok.com/@user/video/123",
])
def test_real_urls_detected(url):
    assert is_url(url) is True


@pytest.mark.parametrize("not_url", [
    "/Users/me/Desktop/recording.mov",
    "~/Desktop/recording.mov",
    "recording.mov",
    "",
    "ftp://example.com/file",  # only http/https supported
    "file:///Users/me/Desktop/recording.mov",
])
def test_local_paths_and_unsupported_schemes_rejected(not_url):
    assert is_url(not_url) is False


def test_malformed_url_does_not_raise():
    # Defensive: bad input must return False, not raise
    assert is_url("not a url at all !!!") is False
    assert is_url("http://") is False


def test_download_url_raises_when_yt_dlp_missing(monkeypatch):
    """If yt-dlp isn't installed, callers get a clear install hint — not a binary-not-found stack trace."""
    from screenmind import url_ingest

    monkeypatch.setattr(url_ingest, "find_binary", lambda _name: None)

    with pytest.raises(RuntimeError, match="yt-dlp not found"):
        url_ingest.download_url("https://example.com/video")


def test_download_url_handles_empty_stdout(monkeypatch, tmp_path):
    """yt-dlp exit=0 with empty stdout is a real edge case (some live streams).

    Don't let it crash with IndexError on `splitlines()[-1]` — surface a clear message.
    """
    from screenmind import url_ingest

    monkeypatch.setattr(url_ingest, "find_binary", lambda _name: "/usr/bin/yt-dlp")

    class FakeResult:
        returncode = 0
        stdout = "   \n   "  # whitespace only — strip() leaves nothing
        stderr = ""

    monkeypatch.setattr(url_ingest.subprocess, "run", lambda *a, **kw: FakeResult())

    with pytest.raises(RuntimeError, match="no after_move:filepath"):
        url_ingest.download_url("https://example.com/video")
