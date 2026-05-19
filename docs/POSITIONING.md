# ScreenMind — Positioning & Naming

Audit conducted 2026-05-19 against GitHub, PyPI, and npm.

## Naming landscape

Five other repositories carry the "ScreenMind" name on GitHub. None occupy the MCP-server / Claude-Code-tooling lane this project lives in, and none ship to PyPI or npm.

| Project                                                              | Lane                               | Stack        | Conflict? |
| -------------------------------------------------------------------- | ---------------------------------- | ------------ | --------- |
| [ArgenTimo/ScreenMind](https://github.com/ArgenTimo/ScreenMind)      | Hotkey → Telegram screenshot QA    | Consumer     | No        |
| [richardvane-droid/ScreenMind](https://github.com/richardvane-droid) | Emotional-health monitor           | macOS / iOS  | No        |
| [FirdavsJurakulov/screenMindr](https://github.com/FirdavsJurakulov)  | Productivity time-tracker          | Web app      | No        |
| CQUPT-CZL/ScreenMind                                                 | Empty repo                         | —            | No        |
| Sambhav242005/ScreenMind                                             | Empty repo                         | —            | No        |
| **7alexhale5-rgb/screenmind** (this project)                         | Recording-comprehension MCP server | Python + MCP | —         |

Where the name overlaps, the audience does not. Hotkey-Telegram users will not encounter Python MCP installs and vice versa. No PyPI or npm slot is occupied, so a future package release keeps the simple name.

## What ScreenMind is

A local MCP server that turns screen recordings — local files or video URLs via yt-dlp — into a structured timeline of keyframes, OCR text, scene boundaries, and (as of v0.3.0) audio transcript. Output is text + file paths; Claude reads frames with the Read tool.

## What ScreenMind is not

- Not a continuous-capture screen memory (see [screenpipe](https://github.com/mediar-ai/screenpipe))
- Not a live screen-share / read-only screen primitive (see [claude-screen-mcp](https://github.com/lfzds4399-cpu/claude-screen-mcp))
- Not an accessibility-tree desktop automation agent (see [ghost-os](https://github.com/ghostwright/ghost-os))
- Not Anthropic's official Computer Use ([docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool))

See the `## How ScreenMind compares` table in [README.md](../README.md) for a feature-axis comparison.
