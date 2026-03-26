#!/usr/bin/env bash
# Watches ~/Desktop for new screen recordings and sends a macOS notification.
# Designed to be triggered by launchd WatchPaths on ~/Desktop.
#
# When you see the notification, just type "/watch" in Claude Code.

CAPTURE_DIR="${HOME}/Desktop"
PATTERNS=("*.mov" "*.mp4" "*.mkv")
STATE_FILE="${HOME}/.screenmind/last_notify_check"

mkdir -p "$(dirname "$STATE_FILE")"

# Find files newer than last check
NEWEST=""
NEWEST_TIME=0

for pattern in "${PATTERNS[@]}"; do
    while IFS= read -r -d '' file; do
        mtime=$(stat -f '%m' "$file" 2>/dev/null || echo 0)
        if [ "$mtime" -gt "$NEWEST_TIME" ]; then
            NEWEST="$file"
            NEWEST_TIME="$mtime"
        fi
    done < <(find "$CAPTURE_DIR" -maxdepth 1 -name "$pattern" -print0 2>/dev/null)
done

# Check if this is newer than our last notification
LAST_CHECK=0
if [ -f "$STATE_FILE" ]; then
    LAST_CHECK=$(cat "$STATE_FILE")
fi

if [ "$NEWEST_TIME" -gt "$LAST_CHECK" ] && [ -n "$NEWEST" ]; then
    BASENAME=$(basename "$NEWEST")
    osascript -e "display notification \"${BASENAME}\" with title \"ScreenMind\" subtitle \"New recording detected\" sound name \"Submarine\""
    echo "$NEWEST_TIME" > "$STATE_FILE"
fi
