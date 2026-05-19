# ScreenMind Backlog

Project-scope work staged via `/ci-ingest`. Pulled in by `/planning-stack` when working in this repo.

Order: P0 first, then P1, then P2, then P3.

---

## screenmind_wait_for_change — long-poll primitive — INTEGRATE

- **CI source**: `~/Projects/memory-vault/continuous-improvement/2026-05-19-screenmind-eyes-gap-audit.md`
- **Priority**: P0
- **Verdict + reason**: INTEGRATE — claude-screen-mcp's `wait_for_change` is the most-cited primitive in the live-watch space; ScreenMind has no equivalent. Closes the largest single capability gap and extends naturally from the existing scene-detection pipeline.
- **What to do**: Add a new MCP tool `screenmind_wait_for_change(threshold=0.95, max_wait_seconds=300, region=None)`. Server-side long-poll: take a baseline frame (ffmpeg avfoundation single-shot), then loop comparing each new frame to the baseline via SSIM (existing `_get_ssim_func()` import). Return the first frame where similarity drops below `threshold`, or `{"timed_out": true}` after `max_wait_seconds`. Hard cap `max_wait_seconds` at 300 to match claude-screen-mcp. Frames go to `~/.screenmind/sessions/wait_<timestamp>/`. Implementation lives in `server.py` next to `screenmind_record_start`.
- **Effort estimate**: 2-4 hours
- **Acceptance criterion**: `screenmind_wait_for_change` registered as MCP tool; integration test that triggers a screen change mid-call returns the changed frame's path + timestamp within 2s of the change; timeout path returns `timed_out=true` without orphaning the subprocess.

---

## Whisper audio transcription — INTEGRATE

- **CI source**: `~/Projects/memory-vault/continuous-improvement/2026-05-19-screenmind-eyes-gap-audit.md`
- **Priority**: P1
- **Verdict + reason**: INTEGRATE — screenpipe ships audio transcription as a primary feature; ScreenMind's "watch a YouTube tutorial" use case is significantly weaker without it. Whisper (faster-whisper) bindings are mature, runs on-device, no API key.
- **What to do**: Extract audio with `ffmpeg -i input.mov -vn -acodec mp3 audio.mp3` inside `screenmind_watch`. If `faster-whisper` is importable (graceful degradation — match existing SSIM/OCR pattern), transcribe with `tiny.en` or `base.en` model (configurable in `~/.screenmind/config.json` as `whisper_model`). Emit transcript text into the session report under a `## Audio Transcript` section, with rough timestamps from Whisper's segments. Skip silently if `faster-whisper` missing — same graceful-degradation pattern as SSIM/OCR.
- **Effort estimate**: 3-5 hours
- **Acceptance criterion**: `screenmind_watch` on a YouTube tutorial URL returns transcript in the report; transcript has speaker timestamps; `pip uninstall faster-whisper` leaves the rest of the pipeline working with a note that transcription is unavailable.

---

## Cross-session search — INTEGRATE

- **CI source**: `~/Projects/memory-vault/continuous-improvement/2026-05-19-screenmind-eyes-gap-audit.md`
- **Priority**: P1
- **Verdict + reason**: INTEGRATE — screenpipe's "what was I looking at yesterday at 3pm" is a high-value workflow. ScreenMind already persists sessions to `~/.screenmind/sessions/` with OCR text in the report file; only thing missing is the search layer.
- **What to do**: New MCP tool `screenmind_search(query, limit=10, since=None)`. Walk `~/.screenmind/sessions/<id>/` directories, glob for `report.md` files (also start writing reports to a known file in each session dir as part of this work — currently the report is only returned in-MCP, not persisted). Run substring + fuzzy match on the OCR blocks; return ranked list of `{session_id, timestamp, matched_frame_path, snippet, score}`. Skip embeddings v1 — substring on OCR text is enough for the workflow.
- **Effort estimate**: 3-4 hours
- **Acceptance criterion**: After running `screenmind_watch` on three recordings, `screenmind_search "error dialog"` returns the matching session(s) with frame path + snippet. Empty-result path returns empty list, not error.

---

## screenmind_diff — INTEGRATE

- **CI source**: `~/Projects/memory-vault/continuous-improvement/2026-05-19-screenmind-eyes-gap-audit.md`
- **Priority**: P2
- **Verdict + reason**: INTEGRATE — "what changed between this build and the broken one" is a recurring Claude Code workflow that currently requires running `watch` twice and diffing by hand.
- **What to do**: New MCP tool `screenmind_diff(file_a, file_b, focus=None)`. Run the existing `screenmind_watch` pipeline against both files (or accept two existing session IDs to skip re-processing). For each, align by relative timestamp; compute per-frame SSIM between aligned pairs; emit a report flagging frames where SSIM drops below a configurable threshold AND OCR text differs. Output structure: `## Differences` section with frame pairs + side-by-side paths + OCR delta.
- **Effort estimate**: 4-6 hours
- **Acceptance criterion**: Diff of two recordings of the same flow with one UI difference (e.g., button color) returns the frame pair where the change happens, ranked by SSIM delta.

---

## Naming + positioning audit — INTEGRATE

- **CI source**: `~/Projects/memory-vault/continuous-improvement/2026-05-19-screenmind-eyes-gap-audit.md`
- **Priority**: P2
- **Verdict + reason**: INTEGRATE (research action, not code). "ScreenMind" appears in Perplexity output as a generic category placeholder, suggesting there may be 2-3 projects under similar names. Defensive check before any public push (HN/Reddit/awesome-mcp PR).
- **What to do**: 30-min audit: GitHub search `screenmind` (qualified by `language:Python` + `mcp` topic), npmjs.com, glama.ai, mcpservers.org. Document findings in `docs/POSITIONING.md`. If a clear conflict exists, propose 2-3 alternate names (e.g., `ScreenScribe`, `Reelmind`, `Watchpipe`). Decision: rename or keep + explicit "vs Project X" docs.
- **Effort estimate**: 1 hour audit + 0-2 hours rename if needed
- **Acceptance criterion**: `docs/POSITIONING.md` ships with the audit results + decision; if rename happens, all `screenmind_*` tool prefixes update consistently across server.py, install.sh, CLAUDE.md, README, docs/.

---

## README "vs screenpipe / claude-screen-mcp" comparison — DOCUMENT

- **CI source**: `~/Projects/memory-vault/continuous-improvement/2026-05-19-screenmind-eyes-gap-audit.md`
- **Priority**: P3
- **Verdict + reason**: DOCUMENT — the research artifact has a clean comparison table the README is missing. Helps drive-by visitors place ScreenMind in the landscape and avoid wrong-tool-for-the-job adoption.
- **What to do**: Add a "## How ScreenMind compares" section to README between "How It Works" and "Configuration". Markdown table with rows for screenpipe, claude-screen-mcp, ghost-os, computer-use, ScreenMind. Columns: License, Lane (live watch vs recording comprehension), URL ingest, Cross-platform, Audio. Two-sentence explainer pointing readers to the docs/ deep dives for each comparison axis.
- **Effort estimate**: 30 min
- **Acceptance criterion**: Section lands in README.md; cross-references the four projects with real GitHub URLs; positions ScreenMind on the recording-comprehension axis explicitly.

---

## Deferred / not-now

- **AX-tree integration** — ghost-os lane, macOS-only, requires Swift sidecar. Reeval if Alex's workflow needs it.
- **Live capture-while-watching** — pair screen recording with concurrent AX-tree snapshots. Same dependency.
- **On-device VLM (Ollama)** — screenpipe uses Apple Intelligence on supported Macs. Reeval if token cost on Claude vision becomes a real budget item.
