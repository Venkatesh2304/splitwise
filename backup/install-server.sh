#!/bin/bash
# One-time install of the backup timer. Run on the server:  sudo bash backup/install-server.sh
# from /opt/splitwise (after this branch has been deployed there).
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

DIR=/opt/splitwise/backup
BACKUPS=/var/backups/splitwise

# rama writes the snapshots; the ubuntu group can read them.
install -d -o rama -g ubuntu -m 2750 "$BACKUPS"
chmod 755 "$DIR/backup.sh"

install -m 644 "$DIR/splitwise-backup.service" /etc/systemd/system/
install -m 644 "$DIR/splitwise-backup.timer"   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now splitwise-backup.timer

# Take the first snapshot now rather than waiting for 03:30, and prove it works.
systemctl start splitwise-backup.service
ls -la "$BACKUPS"
systemctl list-timers splitwise-backup.timer --no-pager
