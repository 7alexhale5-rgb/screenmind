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
    # The house standard is 2 fps, every frame, for anything the user drops
    # (~/.claude/skills/screenmind/SKILL.md). It used to be opt-in via max_frames and
    # every one of the first 8 real calls missed it; 4 passed no max_frames at
    # all and silently got 15 frames for a multi-minute recording. A safe path
    # nobody takes is not a safe path, so the standard is now the default.
    "target_fps": 2.0,
    "default_max_frames": 900,   # 7.5 min at 2 fps; the budget, not a summary
    "frame_budget_ceiling": 900,
    "frame_quality": 80,
    "frame_max_width": 1280,
    # Drop only virtually identical frames. 0.95 was a keyframe-dedup
    # summariser that discarded real UI changes between them.
    "dedup_threshold": 0.995,
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
        # Defensive: a corrupt or hand-edited config shouldn't crash the server.
        # Fall back to defaults silently rather than refuse to start.
        try:
            with open(CONFIG_PATH) as f:
                user_config = json.load(f)
        except (json.JSONDecodeError, ValueError, OSError):
            user_config = {}
        if not isinstance(user_config, dict):
            user_config = {}
        return {**DEFAULT_CONFIG, **user_config}

    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    return dict(DEFAULT_CONFIG)
