# ScreenMind Examples

Real walkthroughs of how ScreenMind fits into a Claude Code session. Each one is a complete loop: the situation, what you say, what ScreenMind does, what the output looks like, and what Claude does with it.

If you're new here, start with the debug walkthrough — it's the workflow that sold us on building this.

## Index

| Example                                                              | Workflow                                                                |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [01 — Debug walkthrough](./01-debug-walkthrough.md)                  | Hand Claude a screen recording of a bug and get a behavioral trace back |
| [02 — Watch a YouTube/Loom tutorial](./02-watch-youtube-tutorial.md) | Paste a URL, get structured notes with timestamps                       |
| [03 — Find a past recording](./03-find-past-recording.md)            | Cross-session search across every recording you've ever processed       |

## The common shape

Every example follows the same pattern:

1. You point Claude at something (a file, a URL, a phrase you half-remember)
2. Claude calls one ScreenMind tool
3. ScreenMind returns a Markdown report with file paths to frames
4. Claude reads the frames it actually needs via the `Read` tool
5. You get a behavioral answer, not "I see an image"

Frames live under `~/.screenmind/sessions/<session_id>/`. Reports are persistent. Search is substring across reports. No embeddings, no database, no cloud.
