"""Config-loading behavior — first-run creation, override merge, default backfill."""

import json


def test_first_run_creates_default_config(tmp_screenmind_dir):
    import screenmind.config as cfg
    assert not cfg.CONFIG_PATH.exists()

    result = cfg.load_config()

    assert cfg.CONFIG_PATH.exists(), "load_config must create the file on first run"
    assert result == cfg.DEFAULT_CONFIG
    on_disk = json.loads(cfg.CONFIG_PATH.read_text())
    assert on_disk == cfg.DEFAULT_CONFIG


def test_user_override_wins_over_default(tmp_screenmind_dir):
    import screenmind.config as cfg
    cfg.CONFIG_PATH.write_text(json.dumps({"default_max_frames": 99, "whisper_model": "base.en"}))

    result = cfg.load_config()

    assert result["default_max_frames"] == 99
    assert result["whisper_model"] == "base.en"
    # Untouched keys must keep defaults
    assert result["capture_dir"] == cfg.DEFAULT_CONFIG["capture_dir"]
    assert result["dedup_threshold"] == cfg.DEFAULT_CONFIG["dedup_threshold"]


def test_missing_keys_backfill_from_defaults(tmp_screenmind_dir):
    """A user config saved before v0.3.0 lacks whisper_model — load_config backfills it."""
    import screenmind.config as cfg
    cfg.CONFIG_PATH.write_text(json.dumps({"capture_dir": "/tmp/custom"}))

    result = cfg.load_config()

    assert result["capture_dir"] == "/tmp/custom"
    assert "whisper_model" in result
    assert result["whisper_model"] == cfg.DEFAULT_CONFIG["whisper_model"]
    assert "audio_transcription_enabled" in result


def test_corrupt_json_falls_back_to_defaults(tmp_screenmind_dir):
    """A hand-edited config with broken JSON shouldn't crash the server."""
    import screenmind.config as cfg
    cfg.CONFIG_PATH.write_text("{this is not valid json")

    result = cfg.load_config()

    assert result == cfg.DEFAULT_CONFIG


def test_non_object_json_falls_back_to_defaults(tmp_screenmind_dir):
    """JSON that parses but isn't a dict (e.g. a list) also falls back cleanly."""
    import screenmind.config as cfg
    cfg.CONFIG_PATH.write_text(json.dumps(["not", "a", "dict"]))

    result = cfg.load_config()

    assert result == cfg.DEFAULT_CONFIG
