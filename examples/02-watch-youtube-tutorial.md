# Watch this tutorial and write me notes

The URL workflow: paste a link, get structured notes back.

## The situation

A teammate dropped a 12-minute Loom walkthrough in Slack: "watch this when you get a chance, it's how I fixed the slow dashboard query." You don't have 12 minutes. You want notes with timestamps so you can jump to the part that matters and keep the rest as reference.

## What you say to Claude

```text
Watch this and write me notes with timestamps — focus on what the actual fix was
and the EXPLAIN output if there's one:

https://www.loom.com/share/abc123def456
```

(The same pattern works for YouTube, Instagram Reels, TikTok, X video posts, and 1000+ other sources.)

## What ScreenMind does

```text
screenmind_watch(
  file_path="https://www.loom.com/share/abc123def456",
  focus="fix and EXPLAIN output"
)
```

ScreenMind detects the URL, hands it to yt-dlp, downloads the video to `~/.screenmind/downloads/`, then runs the same pipeline as a local file: frame extraction, scene detection, OCR, and (if `faster-whisper` is installed) an audio transcript.

## Sample report

```markdown
# ScreenMind Report — session 2026-05-19-1402-loom-dashboard-fix

Source: https://www.loom.com/share/abc123def456
Downloaded: ~/.screenmind/downloads/loom-abc123def456.mp4
Duration: 11m 47s | Resolution: 1920x1080 | Extracted: 354 frames | Kept: 15

## Timeline

### Frame 01 — t=0:08

Path: `~/.screenmind/sessions/2026-05-19-1402-loom-dashboard-fix/frame_001.png`
OCR: "Dashboard query is slow — 3.4s p95 | Goal: under 200ms"

### Frame 04 — t=2:31 — scene change

Path: `~/.screenmind/sessions/2026-05-19-1402-loom-dashboard-fix/frame_004.png`
OCR: "SELECT \* FROM events WHERE org_id = $1 AND created_at > now() -
interval '30 days' AND status = 'completed' ORDER BY created_at DESC"

### Frame 07 — t=4:18 — scene change

Path: `~/.screenmind/sessions/2026-05-19-1402-loom-dashboard-fix/frame_007.png`
OCR: "Seq Scan on events (cost=0.00..184213.00 rows=12 width=284)
(actual time=3284.112..3284.118 rows=8 loops=1)
Filter: ((org_id = 42) AND (status = 'completed'))
Rows Removed by Filter: 2847193"

### Frame 11 — t=7:02 — scene change

Path: `~/.screenmind/sessions/2026-05-19-1402-loom-dashboard-fix/frame_011.png`
OCR: "CREATE INDEX events_org_status_created_idx ON events (org_id,
created_at DESC) WHERE status = 'completed';"

### Frame 14 — t=9:46 — scene change

Path: `~/.screenmind/sessions/2026-05-19-1402-loom-dashboard-fix/frame_014.png`
OCR: "Index Scan using events_org_status_created_idx on events
(actual time=0.067..0.071 rows=8 loops=1)
Planning Time: 0.184 ms | Execution Time: 0.094 ms"

## Audio Transcript

[0:00 - 0:42] Quick context — the events dashboard has been taking three and a
half seconds at the 95th percentile and we need to get it under 200 milliseconds
before the customer demo on Friday.

[2:14 - 3:08] So here's the query the dashboard runs. Looks innocent — org_id,
a 30-day window, status equals completed, ordered by created_at descending.
The problem is what Postgres actually does with it.

[4:05 - 4:55] EXPLAIN ANALYZE tells the whole story. Sequential scan, three
point three seconds, and look at this — rows removed by filter is two point
eight million. We're reading the entire events table to return eight rows.

[6:48 - 7:30] The fix is a partial index. Org_id and created_at descending,
filtered to status equals completed. Partial because ninety percent of events
are not completed and we never query those from this dashboard.

[9:30 - 10:12] After the index — index scan, ninety-four microseconds. From
three point three seconds to under a millisecond, roughly a thirty-five
thousand times improvement. The Friday demo is safe.
```

## What Claude does next

Claude lines up the transcript timestamps with the visual scene changes and produces structured notes: "At 2:31 the speaker shows the slow query (full SELECT in frame 04). At 4:18 the EXPLAIN ANALYZE confirms a sequential scan removing 2.8M rows (frame 07). The fix at 7:02 is a partial index on `(org_id, created_at DESC) WHERE status = 'completed'` (frame 11). At 9:46 the same query runs as an index scan in 94 microseconds (frame 14)." Claude reads frame 11 to copy the exact `CREATE INDEX` statement into your notes file.

## Other URL sources

yt-dlp supports YouTube, Loom, Instagram Reels, TikTok, X/Twitter video, Vimeo, and 1000+ other sites — anything yt-dlp handles, ScreenMind handles.
