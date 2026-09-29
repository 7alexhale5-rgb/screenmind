# Planning room: backlog and plans

One job: hold work that is decided but not built. Paths are relative to the repo root.

## Inputs

- Ideas and verdicts from `/ci-ingest`, reviews, or Alex.
- Current backlog: `.planning/BACKLOG.md`.
- Missing input: an item with no acceptance criterion stays in the backlog until it gets one.

## Process

1. Add or update the item in `.planning/BACKLOG.md`: title, verdict, what to do, acceptance
   criterion, effort.
2. When an item is picked up, write its plan with `/planning-stack` and link it from the item.
3. When it ships, move it to the SHIPPED section with the version and date.

## Outputs

- `.planning/BACKLOG.md` entries. Brainstorm notes go to `.planning/BRAINSTORM.md`, never here.

## Human check

Alex approves an item before it is built (`/planning-stack` confirmation gate). Pass: the item
names a falsifiable acceptance criterion. Fail: it stays unscheduled.
