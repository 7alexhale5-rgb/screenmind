"""URL ingest via yt-dlp — YouTube, Instagram, TikTok, X, 1000+ sites."""

import os
import subprocess
import urllib.parse

from screenmind.config import DOWNLOADS_DIR
from screenmind.util import find_binary


def is_url(s: str) -> bool:
    """True if the string is an http or https URL with a non-empty netloc."""
    if not s:
        return False
    parsed = urllib.parse.urlparse(s)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def download_url(url: str) -> str:
    """Download a video from a URL using yt-dlp. Returns the local file path.

    Supports YouTube, Instagram, Twitter/X, TikTok, and 1000+ other sites.
    Raises RuntimeError when yt-dlp is missing or the download fails.
    """
    yt_dlp = find_binary("yt-dlp")
    if not yt_dlp:
        raise RuntimeError("yt-dlp not found. Install it: brew install yt-dlp")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    output_template = str(DOWNLOADS_DIR / "%(title).80s_%(id)s.%(ext)s")

    cmd = [
        yt_dlp,
        "--no-playlist",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--print", "after_move:filepath",
        "--no-simulate",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

    # `--print after_move:filepath` should emit a path on stdout. Guard against
    # the case where yt-dlp exits 0 but emits nothing (rare, but reported on
    # some live streams and on certain extractor failures).
    lines = result.stdout.strip().splitlines()
    if not lines:
        raise RuntimeError("yt-dlp returned no after_move:filepath line")
    downloaded_path = lines[-1]
    if not os.path.exists(downloaded_path):
        raise RuntimeError(
            f"Download reported success but file not found: {downloaded_path}"
        )
    return downloaded_path
