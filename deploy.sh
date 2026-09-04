#!/usr/bin/env bash
set -euo pipefail

# Remote SSH configuration
REMOTE_HOST="ubuntu@13.235.142.203"
SSH_KEY="/home/venkatesh/Downloads/billingv2.pem"
REMOTE_PROJECT_DIR="/home/ubuntu/splitwise"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> [deploy.sh] Building frontend bundle locally..."
cd "$PROJECT_DIR/frontend"
npm run build

cd "$PROJECT_DIR"
echo "==> [deploy.sh] Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
  echo "==> Committing local changes & built frontend/dist..."
  git add .
  git commit -m "Auto-deploy update with pre-built dist $(date '+%Y-%m-%d %H:%M:%S')" || true
fi

echo "==> [deploy.sh] Pushing latest changes & dist to GitHub..."
git push origin main -f || git push origin MASTER -f || git push origin -f

echo "==> [deploy.sh] Copying latest db.sqlite3 to remote server..."
scp -o StrictHostKeyChecking=no -4 -i "$SSH_KEY" "$PROJECT_DIR/backend/db.sqlite3" "$REMOTE_HOST:$REMOTE_PROJECT_DIR/backend/db.sqlite3"

echo "==> [deploy.sh] SSH connecting to remote server $REMOTE_HOST..."
ssh -o StrictHostKeyChecking=no -4 -i "$SSH_KEY" "$REMOTE_HOST" bash <<EOF
  set -eu
  if [ ! -d "$REMOTE_PROJECT_DIR" ]; then
    echo "[Remote] Creating project directory $REMOTE_PROJECT_DIR..."
    mkdir -p "$REMOTE_PROJECT_DIR"
  fi
  cd "$REMOTE_PROJECT_DIR"
  echo "[Remote] Triggering sync.sh on server..."
  bash sync.sh
EOF

echo "==> ✅ Remote deployment and sync completed successfully!"
