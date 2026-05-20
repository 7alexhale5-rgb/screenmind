# ScreenMind Troubleshooting

Problem → cause → fix, for the issues people actually hit. Start with `screenmind_status` — it tells you which binaries and optional deps are present, what the current config looks like, and whether a recording is active.

See also: [`CONFIGURATION.md`](./CONFIGURATION.md) for what each setting does, [`ARCHITECTURE.md`](./ARCHITECTURE.md) for why the pipeline behaves the way it does.

---

## Recording captures a black screen

**Problem:** `screenmind_record_start` succeeds and writes a `.mov`, but the file is entirely black when played back.

**Cause:** macOS requires explicit Screen Recording permission per binary. The ffmpeg binary that ScreenMind uses has not been granted that permission, so ffmpeg silently captures black frames.

**Fix:**

1. Find the ffmpeg path ScreenMind is using:

```text
screenmind_status
```

Look at the `**ffmpeg:**` line.

2. Open System Settings → Privacy & Security → Screen Recording.
3. Click the `+` button and add that exact ffmpeg binary (typically `/opt/homebrew/bin/ffmpeg` on Apple Silicon).
4. Toggle the entry on.
5. Fully quit and restart your terminal (and Claude Code). The permission only applies to processes that started after it was granted.

If you upgrade ffmpeg later, you may need to re-grant — macOS sometimes treats the new binary as a different identity.

---

## "ffmpeg not found"

**Problem:** `screenmind_record_start` or `screenmind_watch` reports `ffmpeg not found. Install with: brew install ffmpeg`.

**Cause:** ffmpeg is not installed, or it is installed but not on the MCP process's `PATH` (Claude Code launches MCP servers with a minimal environment).

**Fix:**

```bash
brew install ffmpeg
```

ScreenMind checks `/opt/homebrew/bin/ffmpeg` before falling back to `PATH`, so a standard Homebrew install on Apple Silicon should be found automatically. If you're on Intel Mac and Homebrew installs to `/usr/local/bin`, that location is on `PATH` by default and `shutil.which` finds it.

If ffmpeg is installed somewhere unusual:

```bash
which ffmpeg
ls -la /opt/homebrew/bin/ffmpeg   # check the location ScreenMind prefers
```

You can symlink your install into `/opt/homebrew/bin/` to make the cached lookup work. After installing ffmpeg, restart Claude Code so the binary cache picks it up — see [`ARCHITECTURE.md`](./ARCHITECTURE.md) for why.

---

## "yt-dlp not found" when watching a URL

**Problem:** Passing a URL to `screenmind_watch` returns `Download failed: yt-dlp not found. Install it: brew install yt-dlp`.

**Cause:** `yt-dlp` is an optional dependency. It's only needed for URL ingestion; local file paths work without it.

**Fix:**

```bash
brew install yt-dlp
```

Then restart Claude Code so the binary cache refreshes.

---

## OCR text is empty in the report

**Problem:** Report shows frames but no `**Visible text:**` blocks. Header says `**OCR:** unavailable` or `**OCR:** disabled`.

**Cause(s):**

1. `tesseract` is not installed.
2. `pytesseract` (the Python binding) is not installed in the same Python environment as the MCP server.
3. `ocr_enabled` is `false` in `~/.screenmind/config.json`.

**Fix:**

```bash
# System binary
brew install tesseract

# Python binding — install into the same venv ScreenMind runs from
/Users/alexhale/Projects/ideas/screenmind/.venv/bin/pip install pytesseract Pillow
```

Then check:

```text
screenmind_status
```

The `**OCR:**` line should now say `available`. If it still says `not installed`, the Python binding went into a different environment — install it into the venv whose Python is registered with `claude mcp add`.

If OCR is available but the report says `**OCR:** disabled`, edit `~/.screenmind/config.json`:

```json
"ocr_enabled": true
```

---

## SSIM dedup says "unavailable" in the report

**Problem:** Report header shows `**SSIM dedup:** unavailable (install scikit-image)`. The pipeline still runs but keeps near-duplicate frames.

**Cause:** `scikit-image` is not installed in the MCP server's Python environment.

**Fix:**

```bash
/Users/alexhale/Projects/ideas/screenmind/.venv/bin/pip install scikit-image
```

`scikit-image` pulls in `numpy` and `scipy` — install can take a minute. After installing, restart Claude Code so the next `_get_ssim_func()` import attempt succeeds (the import result isn't cached across server processes, but you do need a fresh process to pick up newly-installed packages).

Verify:

```text
screenmind_status
```

`**SSIM dedup:**` should now say `available`.

---

## Recording captures the wrong display

**Problem:** You record on a multi-monitor setup and the output shows the secondary display when you wanted the primary, or vice versa.

**Cause:** `avfoundation_screen_index` in `~/.screenmind/config.json` points at the wrong device.

**Fix:**

1. List your avfoundation devices:

```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

You'll see output like:

```text
[AVFoundation indev @ 0x...] AVFoundation video devices:
[AVFoundation indev @ 0x...] [0] FaceTime HD Camera
[AVFoundation indev @ 0x...] [1] Capture screen 0
[AVFoundation indev @ 0x...] [2] Capture screen 1
```

2. The number in brackets is the index. Edit `~/.screenmind/config.json` (keep it as a string):

```json
"avfoundation_screen_index": "2"
```

3. Start a new recording. No restart needed — config is reloaded on each tool call.

---

## Too few or too many frames in the report

**Problem:** Reports either skip moments that mattered, or include a wall of near-identical frames.

**Cause:** Frame budget (`default_max_frames`) and scene sensitivity (`scene_change_threshold`) aren't matched to your recording style.

**Fix:**

Per-call override is the fastest path:

```text
screenmind_watch(file_path="<path>", max_frames=30)
```

For permanent changes, edit `~/.screenmind/config.json`:

- Missing intermediate states → raise `default_max_frames` (try 25) or lower `scene_change_threshold` (try `0.2`).
- Too many near-duplicates → lower `dedup_threshold` (try `0.90`) so SSIM is more aggressive about dropping similar frames.
- Too many false scene changes from hover/cursor motion → raise `scene_change_threshold` (try `0.4` or `0.5`).

See [`CONFIGURATION.md`](./CONFIGURATION.md) for the full tuning guide and [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the selection priority order.

---

## yt-dlp fails on a specific site

**Problem:** `screenmind_watch` with a URL returns `Download failed: yt-dlp failed: ERROR: ...`. Other sites work fine.

**Cause:** The site changed its page structure or auth requirements and the installed yt-dlp version no longer handles it. yt-dlp gets these updates fast, but only if you update.

**Fix:**

```bash
yt-dlp -U
```

If you installed via Homebrew:

```bash
brew upgrade yt-dlp
```

Re-run the same URL. If it still fails, paste the full error into your issue tracker — yt-dlp's error messages are usually specific enough to identify the broken extractor.

For sites that require login (private Instagram, age-restricted YouTube), yt-dlp supports cookies and credentials but ScreenMind doesn't surface those flags. Download manually with your preferred flags, then pass the local path to `screenmind_watch`.

---

## "Permission denied" creating `~/.screenmind/`

**Problem:** First-run tool call fails with a permission error on `~/.screenmind/` or one of its subdirectories.

**Cause:** A previous process created `~/.screenmind/` with the wrong owner, or your home directory has unusual permissions.

**Fix:**

```bash
ls -la ~/.screenmind
```

Check the owner column. If it's not your user:

```bash
sudo chown -R "$(whoami):staff" ~/.screenmind
```

If `~/.screenmind` doesn't exist yet but creation is failing, check parent permissions:

```bash
ls -la ~ | grep -E "^\..*screenmind|^d" | head
```

Worst case, blow it away and let ScreenMind recreate it (you'll lose stored sessions):

```bash
rm -rf ~/.screenmind
```

The next tool call will create a fresh `~/.screenmind/config.json` with defaults.

---

## Old sessions piling up under `~/.screenmind/sessions/`

**Problem:** Disk usage from `~/.screenmind/sessions/` keeps growing past `max_sessions_kept`.

**Cause:** Session cleanup runs **only during `screenmind_watch`**. If you record but don't watch (or watch infrequently), nothing prunes the old sessions.

**Fix:**

Easiest — run any `screenmind_watch` call. Cleanup happens at the end of every successful watch.

Manual cleanup:

```bash
rm -rf ~/.screenmind/sessions/*
```

This is safe — sessions are derived data, not source recordings. Your original `.mov` files in `capture_dir` are untouched.

Downloaded URL videos under `~/.screenmind/downloads/` are **not** auto-pruned at all. Delete them manually when you want the space:

```bash
rm -rf ~/.screenmind/downloads/*
```

---

## MCP server not appearing in Claude Code

**Problem:** ScreenMind tools (`screenmind_watch`, `screenmind_record_start`, etc.) aren't available in a Claude Code session.

**Cause:** The MCP server isn't registered, or the registration points at a wrong path, or Claude Code hasn't picked up the registration yet.

**Fix:**

1. List registered MCP servers:

```bash
claude mcp list
```

If `screenmind` isn't there, register it (adjust the path if your install is elsewhere):

```bash
claude mcp add screenmind -- /Users/alexhale/Projects/Ideas/screenmind/.venv/bin/python /Users/alexhale/Projects/Ideas/screenmind/server.py
```

This is the same command in `install.sh`.

2. Verify the registered Python and server paths actually exist:

```bash
ls -la /Users/alexhale/Projects/Ideas/screenmind/.venv/bin/python
ls -la /Users/alexhale/Projects/Ideas/screenmind/server.py
```

3. Restart Claude Code. MCP registration is read at startup — an already-running session won't see a newly-registered server.

4. Sanity check from inside Claude:

```text
screenmind_status
```

If you get a response, the server is live. If you get an error like "tool not found," registration didn't stick — re-run `claude mcp add` and restart.

---

## `wait_for_change` returns "requires scikit-image"

**Problem:** `screenmind_wait_for_change` immediately returns `wait_for_change requires scikit-image`.

**Cause:** The long-poll tool needs SSIM to compare consecutive frames against the baseline. `scikit-image` is an optional dependency — `install.sh` tries to install it but the install may have failed silently if the venv was missing build tools at the time.

**Fix:**

```bash
/path/to/screenmind/.venv/bin/pip install scikit-image
```

Then re-register the MCP server or restart Claude Code so the Python process picks up the new package.

---

## Whisper transcript section is missing or says "unavailable"

**Problem:** `screenmind_watch` runs successfully but the report ends without an `## Audio Transcript` section, or shows `Audio transcription: unavailable`.

**Cause:** One of three things:

1. `faster-whisper` is not installed in the venv.
2. The video has no audio stream (silent screen recordings without microphone input).
3. ffmpeg audio extraction failed (broken file, unsupported codec).

**Fix:** Run `screenmind_status` — it has an `Audio transcription:` line that distinguishes "not installed" from "available." If "not installed":

```bash
/path/to/screenmind/.venv/bin/pip install faster-whisper
```

If "available" but the report still says "unavailable," the video probably has no audio track. Run `ffprobe -i your-video.mov` and look for an audio stream entry. If missing, that's expected — set `audio_transcription_enabled: false` in `~/.screenmind/config.json` to suppress the unavailability line.

---

## `screenmind_search` returns "No matches" but you know you saw the text

**Problem:** A search query that should match an earlier session returns no hits.

**Cause:** Three common reasons:

1. The session was created **before v0.3.0** introduced per-session `report.md` persistence. Older sessions have frames but no report file, so they're invisible to search. Re-run `screenmind_watch` on the original recording to backfill.
2. Your `since` filter is too narrow — relative durations like `24h` are relative to *now*, not to your last work session.
3. The OCR pass was disabled or failed, so the visible text never made it into the report. Re-run `screenmind_watch` after fixing OCR (see the OCR troubleshooting section).

**Fix:** Drop the `since` filter and search broadly first:

```text
screenmind_search(query="<term>")
```

If that returns nothing, the text was never indexed. Re-run `screenmind_watch` on the original recording with OCR enabled.
