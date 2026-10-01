"""Sample-density lines for the top of every screenmind_watch report.

~/.claude/skills/screenmind/SKILL.md promises that every report opens with a Sample
density line, and a DENSITY SHORTFALL block when the pass came in under
target. A thin sample reads exactly like a thorough one unless the report says
so, which is the whole point of printing it.
"""

import math
from typing import Optional


def density_lines(
    duration: float,
    target_fps: float,
    extraction_fps: float,
    interval_extracted: int,
    scene_extracted: int,
    before_dedup: int,
    kept_after_dedup: int,
    retained: int,
    ceiling: int,
    scene_status: Optional[str] = None,
) -> list[str]:
    """Return the Sample density line, plus a DENSITY SHORTFALL block when under target.

    Target is duration * target_fps (2 fps by default). The shortfall test runs
    on the frames the reader actually gets (`retained`), which can never exceed
    the frames kept after SSIM dedup, so any dedup shortfall is caught too.
    """
    target_frames = math.ceil(duration * target_fps)
    lines = [
        f"**Sample density:** target {target_fps:g} fps = {target_frames} frames over "
        f"{duration:.1f}s | sampled at {extraction_fps:.3g} fps | extracted "
        f"{interval_extracted} interval + {scene_extracted} scene | "
        f"{kept_after_dedup} of {before_dedup} kept after SSIM dedup | {retained} retained",
    ]
    if retained >= target_frames:
        return lines

    lines += [
        "",
        f"> **DENSITY SHORTFALL:** {retained} of {target_frames} target frames "
        f"({retained / max(target_frames, 1):.0%}). Causes:",
    ]
    if extraction_fps < target_fps:
        window = ceiling / target_fps
        windows = math.ceil(duration / window)
        lines.append(
            f"> - Sampled at {extraction_fps:.3g} fps, under the {target_fps:g} fps target, "
            f"because {duration:.0f}s exceeds the {ceiling}-frame budget. Re-run as "
            f"{windows} windows of {window:.0f}s with start_time/end_time for full density."
        )
    expected_interval = math.floor(duration * extraction_fps)
    if interval_extracted < expected_interval - 1:
        lines.append(
            f"> - The interval pass returned {interval_extracted} frames, "
            f"expected about {expected_interval} at {extraction_fps:.3g} fps."
        )
    dedup_dropped = before_dedup - kept_after_dedup
    if dedup_dropped > 0:
        lines.append(
            f"> - {dedup_dropped} frames dropped as near-identical by SSIM dedup "
            f"(the screen did not change between them)."
        )
    budget_dropped = kept_after_dedup - retained
    if budget_dropped > 0:
        lines.append(
            f"> - {budget_dropped} frames cut to fit the frame budget (max_frames or "
            f"default_max_frames). Omit max_frames for a full pass."
        )
    if scene_status:
        lines.append(f"> - Scene detection {scene_status}.")
    return lines
