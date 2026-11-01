#!/bin/bash
# Pulls the server's database snapshots to this Mac.   bash backup/pull_backup.sh
#
# The server keeps the newest 14 dailies; this keeps more (KEEP_LOCAL), so a
# problem noticed late can still be rolled back. Nothing is ever deleted on the
# server from here, and a bad pull never overwrites a good local copy.
set -euo pipefail

HOST="${SPLITWISE_HOST:-ubuntu@130.210.44.146}"
KEY="${SPLITWISE_KEY:-$HOME/.ssh/oracle_vm}"
REMOTE=/var/backups/splitwise
DEST="${SPLITWISE_LOCAL_BACKUPS:-$HOME/Backups/splitwise}"
KEEP_LOCAL=60

# Snapshots contain session tokens, so only this user can read them.
mkdir -p "$DEST"
chmod 700 "$DEST"
umask 077

stage=$(mktemp -d "$DEST/.pull.XXXXXX")
trap 'rm -rf "$stage"' EXIT

# --ignore-existing: a snapshot, once taken, never changes.
rsync -a --ignore-existing --include='splitwise-*.db' --exclude='*' \
  -e "ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=15" \
  "$HOST:$REMOTE/" "$stage/"

new=0
for f in "$stage"/splitwise-*.db; do
  [ -e "$f" ] || continue
  name=$(basename "$f")
  [ -e "$DEST/$name" ] && continue
  # Verify before keeping: a truncated transfer must not look like a backup.
  if [ "$(sqlite3 "$f" 'PRAGMA integrity_check;')" != "ok" ]; then
    echo "integrity check failed for $name; not keeping it" >&2
    continue
  fi
  mv "$f" "$DEST/$name"
  new=$((new + 1))
done

for kind in daily predeploy; do
  ls -1 "$DEST"/splitwise-"$kind"-*.db 2>/dev/null | sort -r | tail -n +$((KEEP_LOCAL + 1)) | xargs -I{} rm -- {} || true
done

latest=$(ls -1 "$DEST"/splitwise-*.db 2>/dev/null | sort | tail -1)
[ -n "$latest" ] || { echo "no snapshots on the server yet" >&2; exit 1; }
echo "pulled $new new; $(ls -1 "$DEST"/splitwise-*.db | wc -l | tr -d ' ') kept in $DEST; newest: $(basename "$latest")"
