"""Config loading + filesystem layout."""

import json
from pathlib import Path

SCREENMIND_DIR = Path.home() / ".screenmind"
SESSIONS_DIR = SCREENMIND_DIR / "sessions"
DOWNLOADS_DIR = SCREENMIND_DIR / "downloads"
CONFIG_PATH = SCREENMIND_DIR / "config.json"

DEFAULT_CONFIG = {
    "capture_dir": "~/Desktop",
    "file_patterns": ["*.mov", "*.mp4", "*.mkv"],
    "max_recording_duration": 120,
    "default_max_frames": 15,
    "frame_quality": 80,
    "frame_max_width": 1280,
    "dedup_threshold": 0.95,
    "scene_change_threshold": 0.3,
    "ocr_enabled": True,
    "audio_transcription_enabled": True,
    "whisper_model": "tiny.en",
    "avfoundation_screen_index": "1",
    "max_sessions_kept": 20,
}


def load_config() -> dict:
    """Load config from ~/.screenmind/config.json, creating defaults if missing.

    Merges any user file over DEFAULT_CONFIG so newly-added keys backfill cleanly.
    """
    SCREENMIND_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            user_config = json.load(f)
        return {**DEFAULT_CONFIG, **user_config}

    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    return dict(DEFAULT_CONFIG)
