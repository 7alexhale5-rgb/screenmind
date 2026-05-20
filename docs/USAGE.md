# ScreenMind Usage Cookbook

Concrete examples for real workflows. Each recipe shows what to ask Claude, what the underlying MCP call looks like, and what you get back.

ScreenMind returns a text report containing a timeline, OCR text per frame, and absolute file paths to the keyframes. Claude opens specific frames with the `Read` tool when it needs to see them.

See also: [`CONFIGURATION.md`](./CONFIGURATION.md) for tuning, [`ARCHITECTURE.md`](./ARCHITECTURE.md) for how frame selection works, [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) when something breaks.

---

## "Walk me through this bug"

You recorded a flaky checkout flow and want Claude to trace what happened.

Ask Claude:

```text
I just recorded a bug at ~/Desktop/checkout-bug.mov. Walk me through what
happened and tell me where the failure starts.
```

What runs:

```text
screenmind_watch(file_path="~/Desktop/checkout-bug.mov")
```

What comes back is a Markdown report with a timeline of frames, OCR text from each frame, and file paths. Claude reads the report, decides which frames matter, and opens them with the `Read` tool. You get a behavioral trace ("at 4.2s the cart shows $40, at 4.7s the price updates to $0, the error dialog appears at 5.1s") rather than a generic "I see a screenshot."

If you didn't pass a path, ScreenMind picks the most recent recording in `capture_dir` (default `~/Desktop`).

---

## "What did the user see?" — OCR from a customer support video

A user sent a screen recording showing an error. You want the visible text without watching the whole video.

Ask Claude:

```text
Extract all visible text from ~/Downloads/support-ticket-447.mp4. I want to
know exactly what error message they saw.
```

What runs:

```text
screenmind_watch(
    file_path="~/Downloads/support-ticket-447.mp4",
    focus="capture every error message and dialog text"
)
```

OCR text for each kept frame is inlined in the report under a `**Visible text:**` block. Long blocks are truncated at 500 characters in the report itself — Claude can `Read` the raw frame if it needs more.

OCR requires `tesseract` and `pytesseract`. If they aren't installed, the report shows `**OCR:** unavailable` and frames still come back without text. See [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md).

---

## "Diff two recordings"

You have a before and after of a UI change and want to know what's different.

Ask Claude:

```text
Compare these two recordings and tell me what changed in the form layout:
  before: ~/Desktop/form-v1.mov
  after:  ~/Desktop/form-v2.mov
```

What runs (two separate calls):

```text
screenmind_watch(file_path="~/Desktop/form-v1.mov", focus="form layout — note field order and labels")
screenmind_watch(file_path="~/Desktop/form-v2.mov", focus="form layout — note field order and labels")
```

Claude gets two reports back, each with their own timeline and OCR. It can then open matching frames side by side (`Read` the path from report A, then the path from report B) and describe the diff in plain English.

Pro move: keep both recordings the same length and start state. The closer the timelines line up, the easier the diff.

---

## Focused segments — re-examining a specific window

The first pass came back with too much noise. You want to zoom in on the 30–45 second range where the actual bug happens.

Ask Claude:

```text
Re-run the analysis on ~/Desktop/checkout-bug.mov but only look at 30s to 45s,
and use 20 frames so I get more detail.
```

What runs:

```text
screenmind_watch(
    file_path="~/Desktop/checkout-bug.mov",
    start_time=30,
    end_time=45,
    max_frames=20
)
```

`start_time` and `end_time` are seconds (floats accepted). `max_frames` overrides `default_max_frames` for this run only.

When you narrow the window, ScreenMind picks a higher extraction FPS automatically (2.0 fps for ≤15s windows). Combined with a higher `max_frames`, you get dense coverage of the slice that matters.

---

## Watching a YouTube tutorial

You want Claude to summarize a tutorial without you watching it.

Ask Claude:

```text
Watch this tutorial and tell me the three main steps:
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

What runs:

```text
screenmind_watch(file_path="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
```

ScreenMind detects the URL, calls `yt-dlp` to download into `~/.screenmind/downloads/`, then processes it like any local file. The full local path appears in the report so you can re-process the same file later without re-downloading.

Requires `yt-dlp` (`brew install yt-dlp`). Supports YouTube, Instagram, Twitter/X, TikTok, and the 1000+ other sites yt-dlp handles.

---

## Watching Instagram Reels and TikToks

Same flow as YouTube. Paste the URL.

```text
What's in this Reel? https://www.instagram.com/reel/C5xY8AbcDEF/
```

```text
Summarize this TikTok: https://www.tiktok.com/@username/video/7234567890123456789
```

Both run as:

```text
screenmind_watch(file_path="<the URL>")
```

Short clips like Reels and TikToks (typically under 60s) get the 1.0 fps extraction rate, which usually keeps `max_frames=15` from being a bottleneck. For very short clips (≤15s), the 2.0 fps rate kicks in.

---

## Custom focus hints

`focus` is a freeform string passed through to the report header. Claude sees it in context and uses it to guide which frames matter when reading the timeline.

```text
screenmind_watch(
    file_path="~/Desktop/onboarding.mov",
    focus="track the form submission flow — I care about validation errors"
)
```

```text
screenmind_watch(
    file_path="~/Desktop/demo.mov",
    focus="watch the pricing dialog appearance and disappearance"
)
```

This does not change the frame selection algorithm itself — selection is mechanical (first/last, scene changes, OCR-change, even distribution). The hint shapes Claude's reading, not the underlying pipeline. If you want different frame coverage, change `max_frames`, `scene_change_threshold`, or the time window.

---

## Power-user: tuning frame budget

Default is 15 frames per session. Override per call with `max_frames`.

Dense recording (lots of UI changes, code editing, fast clicks):

```text
screenmind_watch(file_path="~/Desktop/pair-session.mov", max_frames=40)
```

Quick scan of a long recording (you only need a rough outline):

```text
screenmind_watch(file_path="~/Desktop/hour-long-demo.mov", max_frames=8)
```

Trade-offs:

- More frames → more OCR work, longer processing time, bigger context dump to Claude.
- Fewer frames → faster, cheaper, but you may miss intermediate states.

To make a new value the default for every run, set `default_max_frames` in `~/.screenmind/config.json`. See [`CONFIGURATION.md`](./CONFIGURATION.md).

---

## Recording from inside Claude

You can also record without leaving the conversation.

```text
screenmind_record_start(duration=60, output_name="bug-repro")
```

Returns immediately. Recording continues in the background. Stop early with:

```text
screenmind_record_stop()
```

ScreenMind sends `SIGINT` to ffmpeg first so the `.mov` file gets a proper trailer and is immediately playable. If ffmpeg doesn't exit in 10 seconds it gets `SIGKILL` as a fallback.

First time you record, macOS will prompt for Screen Recording permission. If you get a black-screen `.mov`, see [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md).

---

## Listing past recordings

```text
screenmind_list(limit=20)
```

Returns the 20 most recent files matching `file_patterns` in `capture_dir`, newest first, with size and mtime. Useful when you want Claude to pick a recording without you typing the path.

---

## Checking dependencies and status

```text
screenmind_status()
```

Shows whether a recording is active, how many sessions are stored, current config values, and which optional dependencies are available (`ssim`, `ocr`, `whisper`, `ffmpeg`, `ffprobe`, `tesseract`, `yt-dlp`). Run this first if anything feels off.

---

## "Tell me when the build finishes"

You kick off a slow build, switch windows, and want Claude to notice when the terminal output changes meaningfully — e.g., the build prompt reappears or an error dialog pops up.

Ask Claude:

```text
Watch my screen and let me know when something changes. Give it 5 minutes.
```

What runs:

```text
screenmind_wait_for_change(threshold=0.95, max_wait_seconds=300)
```

ScreenMind snaps a baseline frame, then samples every second comparing SSIM similarity. The first sample whose similarity drops below `threshold` (default 0.95) ends the call and returns the changed frame's path + the elapsed time + the SSIM score. If nothing changes within `max_wait_seconds` (hard-capped at 600), you get a timed-out report.

Tuning:

- Lower `threshold` (e.g., `0.85`) → less sensitive, only reacts to bigger changes (window switches, dialog popups).
- Higher `threshold` (e.g., `0.98`) → very sensitive, fires on subtle UI updates (cursor blink, indicator spinners).
- Raise `poll_interval` to 2–5 seconds when you don't need sub-second latency — uses less CPU.

Requires `scikit-image`. Skips with a clear install instruction when missing.

---

## "Did I work on that bug last week?"

You half-remember solving an error a week ago and want to find the recording.

Ask Claude:

```text
Search my past sessions for the "TypeError: cannot read property" message from the last week.
```

What runs:

```text
screenmind_search(query="TypeError: cannot read property", since="7d")
```

ScreenMind walks every persisted `report.md` under `~/.screenmind/sessions/` whose mtime falls inside the window, substring-matches against OCR text and audio transcript, and returns a ranked hit list with `session_id`, timestamp, matched snippet, and a `first_frame` pointer.

`since` accepts:

- ISO date — `"2026-05-01"`
- Relative — `"30m"`, `"24h"`, `"7d"`

Pass nothing to search all sessions.

---

## "Watch this YouTube tutorial and write notes"

You want notes from a Loom or YouTube walkthrough without watching it yourself.

Ask Claude:

```text
Watch https://www.youtube.com/watch?v=ABC123 and pull out the key steps with timestamps.
```

What runs:

```text
screenmind_watch(file_path="https://www.youtube.com/watch?v=ABC123")
```

With `faster-whisper` installed, the report includes an `## Audio Transcript` section with timestamped segments. Claude combines the visual timeline (scene changes, OCR text from on-screen captions) with the spoken transcript to write structured notes — no manual watching required.

First Whisper call downloads the configured model (default `tiny.en`, ≈75 MB). Subsequent calls reuse the cached model in-process. Bigger models (`base.en`, `small.en`) trade speed for accuracy — configure via `whisper_model` in `~/.screenmind/config.json`.
