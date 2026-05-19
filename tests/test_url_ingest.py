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
