#!/bin/bash
# Snapshot of the production database. Run as the app's own user (rama) by
# splitwise-backup.timer, and by deploy.sh just before migrations run.
#
#   backup.sh [daily|predeploy]     (default: daily)
#
# sqlite3 .backup rather than cp: it copies through SQLite's backup API, so a
# write landing mid-copy cannot produce a torn file the way copying the raw
# database can.
#
# To restore: stop the backend, copy a snapshot over db.sqlite3, start it.
#   sudo systemctl stop splitwise_backend.service
#   cp /var/backups/splitwise/splitwise-daily-YYYY-MM-DD.db /opt/splitwise/backend/db.sqlite3
#   sudo systemctl start splitwise_backend.service
set -euo pipefail

KIND="${1:-daily}"
SRC="${SPLITWISE_DB:-/opt/splitwise/backend/db.sqlite3}"
DEST="${SPLITWISE_BACKUP_DIR:-/var/backups/splitwise}"

case "$KIND" in
  daily)     STAMP=$(date +%F);        KEEP=14 ;;
  predeploy) STAMP=$(date +%F_%H%M%S); KEEP=10 ;;
  *) echo "usage: $0 [daily|predeploy]" >&2; exit 2 ;;
esac

[ -f "$SRC" ] || { echo "no database at $SRC" >&2; exit 1; }

tmp="$DEST/.splitwise-$KIND-$STAMP.db.partial"
trap 'rm -f "$tmp"' EXIT

sqlite3 "$SRC" ".backup '$tmp'"
# A snapshot nobody checked is a guess. Refuse to keep a damaged one, and leave
# the previous snapshots alone.
if [ "$(sqlite3 "$tmp" 'PRAGMA integrity_check;')" != "ok" ]; then
  echo "integrity check failed; keeping earlier backups untouched" >&2
  exit 1
fi
# The database holds session tokens, so it is not world-readable. The group
# (ubuntu) is what lets the Mac pull it over ssh.
chmod 640 "$tmp"
mv "$tmp" "$DEST/splitwise-$KIND-$STAMP.db"
trap - EXIT

# Names sort by date. Newest first; drop everything past the first $KEEP of this kind.
ls -1 "$DEST"/splitwise-"$KIND"-*.db | sort -r | tail -n +$((KEEP + 1)) | xargs -r rm --
echo "backed up: splitwise-$KIND-$STAMP.db"
