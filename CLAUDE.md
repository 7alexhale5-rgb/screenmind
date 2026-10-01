# ScreenMind

> Status: active | Type: lab (MCP server)

## What It Does

Local MCP server that turns a screen recording into keyframes + OCR + a timeline document, giving Claude behavioral context from interaction sequences (click flows, UI transitions, error chains). Accepts both local recording files and URLs — YouTube, Instagram, TikTok, Twitter/X, and 1000+ other sites via yt-dlp. Output is a text comprehension document with file paths; Claude reads individual frames via the Read tool (no base64 in the response).

## Where to go

This repo follows ICM (Jake Van Clief's folder method): this file routes, each room's
`CONTEXT.md` holds its contract.

| Task | Go to | Read | Skills |
| --- | --- | --- | --- |
| Change server, pipeline, package or tests | `screenmind/` | [screenmind/CONTEXT.md](screenmind/CONTEXT.md) | `/build-stack`, `/review-stack` |
| Update user docs, examples, changelog | `docs/` | [docs/CONTEXT.md](docs/CONTEXT.md) | none |
| Stage, plan or pick up backlog work | `.planning/` | [.planning/CONTEXT.md](.planning/CONTEXT.md) | `/planning-stack`, `/ci-ingest` |
| Look up a decision, a config key or which file does what | `_reference/` | [_reference/decisions.md](_reference/decisions.md) | none |

Root files stay where their tools expect them: `server.py` (named by every `claude mcp add`
registration), `install.sh` (README), `new-recording-notify.sh` and the plist template
(launchd), `pyproject.toml`, `requirements*.txt`, `README.md`, `CHANGELOG.md`, `LICENSE`.

## Naming

Python modules snake_case, docs and notes kebab-case `.md`, dated notes `YYYY-MM-DD-slug.md`.

## Dev Commands

```bash
# Compile check
python3 -m py_compile server.py screenmind/*.py

# Run the test suite
pip install -r requirements-dev.txt
pytest -q

# Run directly (stdio mode)
python3 server.py

# Install / reinstall
./install.sh

# Register with Claude Code (install.sh prints the exact command for your path)
claude mcp add screenmind -- /path/to/screenmind/.venv/bin/python /path/to/screenmind/server.py
```
