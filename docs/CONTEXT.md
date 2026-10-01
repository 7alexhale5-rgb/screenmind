# Docs room: what users of ScreenMind read

One job: keep the public docs true to the shipped code. Paths are relative to the repo root.

## Inputs

- The merged code change and its `CHANGELOG.md` entry.
- Current docs: `README.md`, `docs/USAGE.md`, `docs/CONFIGURATION.md`, `docs/ARCHITECTURE.md`,
  `docs/TROUBLESHOOTING.md`, `docs/POSITIONING.md`, `examples/`, `CONTRIBUTING.md`.
- Stable facts: `_reference/decisions.md` and `screenmind/config.py` `DEFAULT_CONFIG`.
- Missing input: a behaviour with no code or test behind it is not documented.

## Process

1. Find every doc line the change makes false: `grep -rn "<old value>" README.md docs examples`.
2. Rewrite those lines to match the code. Defaults come from `DEFAULT_CONFIG`, never memory.
3. Keep screenshots in `docs/assets/`.

## Outputs

- Edited `README.md`, `docs/*.md`, `examples/*.md`; images in `docs/assets/`.

## Human check

Alex spot-checks each changed default against `screenmind/config.py`. Pass: no doc states a
value the code does not use. Fail: correct the doc in the same branch before merge.
