# Did I work on that bug last week?

The cross-session search workflow: find recordings by what was on screen.

## The situation

You half-remember debugging a `TypeError: cannot read property 'map' of undefined` sometime last week. You're pretty sure you recorded it. You don't remember which file, what you named it, or what folder you stashed it in. You really don't want to re-debug it from scratch — you already know you fixed it, you just need to find what you did.

## What you say to Claude

```text
I debugged a TypeError about reading 'map' of undefined sometime in the last
week or so. Can you find the recording and remind me what I did?
```

## What ScreenMind does

```text
screenmind_search(
  query="TypeError: cannot read property",
  since="7d"
)
```

## Sample report

```markdown
# ScreenMind Search Results

Query: "TypeError: cannot read property"
Window: last 7 days | Sessions searched: 14 | Matches: 2

## Match 1 — 2 days ago

Session: 2026-05-17-1623-orders-page-crash
Source: ~/Desktop/orders-page-crash.mov
Duration: 28.4s | Frames kept: 9
First frame: `~/.screenmind/sessions/2026-05-17-1623-orders-page-crash/frame_001.png`
Report: `~/.screenmind/sessions/2026-05-17-1623-orders-page-crash/report.md`

Snippet (frame 04, t=8.2s):
"Uncaught TypeError: cannot read property 'map' of undefined
at OrdersList (OrdersList.tsx:42:18)
at renderWithHooks (react-dom.development.js:14803)"

Snippet (frame 07, t=19.6s):
"+ const orders = data?.orders ?? [];

- const orders = data.orders;"

## Match 2 — 6 days ago

Session: 2026-05-13-0941-dashboard-empty-state
Source: ~/Desktop/dashboard-empty-state.mov
Duration: 14.1s | Frames kept: 6
First frame: `~/.screenmind/sessions/2026-05-13-0941-dashboard-empty-state/frame_001.png`
Report: `~/.screenmind/sessions/2026-05-13-0941-dashboard-empty-state/report.md`

Snippet (frame 03, t=5.7s):
"TypeError: cannot read property 'map' of undefined
at Dashboard.render (Dashboard.jsx:88)"
```

## What Claude does next

Match 1 is almost certainly the one — the snippet shows you already wrote the fix (`data?.orders ?? []`) in frame 07. Claude opens `~/.screenmind/sessions/2026-05-17-1623-orders-page-crash/report.md` for the full timeline, then reads frame 07 to confirm the exact diff. It tells you: "You fixed it in `OrdersList.tsx:42` by switching to optional chaining with a default — `const orders = data?.orders ?? [];`. The recording is still at `~/Desktop/orders-page-crash.mov` if you want me to re-run `screenmind_watch` for the full context around it."

## What makes this work

Every `screenmind_watch` call writes a `report.md` into `~/.screenmind/sessions/<session_id>/` and leaves it there. `screenmind_search` is a substring match across those reports — every OCR string and every transcript line is already in plain text on disk, so search is fast and works offline. No embeddings, no vector DB, no cloud index. Oldest sessions get reaped per the `max_sessions_kept` config (default 20).
