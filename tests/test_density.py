"""The Sample density line and DENSITY SHORTFALL block (skills/screenmind/SKILL.md)."""

from screenmind.density import density_lines


def _lines(**overrides):
    args = dict(
        duration=190.9, target_fps=2.0, extraction_fps=2.0,
        interval_extracted=382, scene_extracted=27, before_dedup=395,
        kept_after_dedup=395, retained=395, ceiling=900,
    )
    args.update(overrides)
    return density_lines(**args)


def test_density_line_reports_target_actual_and_kept():
    lines = _lines()
    assert lines[0].startswith("**Sample density:** target 2 fps = 382 frames over 190.9s")
    assert "sampled at 2 fps" in lines[0]
    assert "extracted 382 interval + 27 scene" in lines[0]
    assert "395 of 395 kept after SSIM dedup" in lines[0]
    assert "395 retained" in lines[0]


def test_no_shortfall_block_at_or_above_target():
    assert len(_lines()) == 1
    assert not any("DENSITY SHORTFALL" in line for line in _lines(retained=382, kept_after_dedup=382))


def test_shortfall_when_dedup_leaves_fewer_than_duration_times_two():
    lines = _lines(kept_after_dedup=250, retained=250)
    text = "\n".join(lines)
    assert "DENSITY SHORTFALL:** 250 of 382 target frames (65%)" in text
    assert "145 frames dropped as near-identical by SSIM dedup" in text
    # Nothing was sampled thin, so no window advice.
    assert "windows" not in text


def test_shortfall_over_budget_says_how_many_windows_to_run():
    # 53 minutes: the 900-frame budget forces 0.283 fps.
    lines = _lines(
        duration=3180, extraction_fps=900 / 3180, interval_extracted=900,
        scene_extracted=0, before_dedup=900, kept_after_dedup=900, retained=900,
    )
    text = "\n".join(lines)
    assert "900 of 6360 target frames" in text
    assert "Re-run as 8 windows of 450s" in text


def test_shortfall_names_a_max_frames_skim():
    text = "\n".join(_lines(retained=15))
    assert "380 frames cut to fit the frame budget" in text


def test_shortfall_names_a_skipped_scene_pass():
    text = "\n".join(_lines(
        scene_extracted=0, before_dedup=382, kept_after_dedup=300, retained=300,
        scene_status="timed out; scene frames skipped, interval frames only",
    ))
    assert "Scene detection timed out; scene frames skipped" in text


def test_shortfall_flags_a_thin_interval_pass():
    text = "\n".join(_lines(interval_extracted=100, before_dedup=127,
                            kept_after_dedup=127, retained=127))
    assert "interval pass returned 100 frames, expected about 381" in text
