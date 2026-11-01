#!/bin/bash
# One-time install of the daily pull on this Mac.   bash backup/install-mac.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.splitwise.backup.plist"

mkdir -p "$HOME/Backups/splitwise" "$HOME/Library/LaunchAgents"
chmod 700 "$HOME/Backups/splitwise"
sed -e "s#__REPO__#$REPO#g" -e "s#__HOME__#$HOME#g" "$REPO/backup/com.splitwise.backup.plist" > "$PLIST"

launchctl bootout "gui/$(id -u)/com.splitwise.backup" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed: pulls daily at 09:00 into ~/Backups/splitwise (log: pull.log)"
