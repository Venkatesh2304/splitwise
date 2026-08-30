#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "==> [sync.sh] Pulling latest changes from remote..."
git stash --include-untracked || true
git pull --ff

chmod +x *.sh || true

echo "==> [sync.sh] Activating virtual environment..."
if [ -d "$PROJECT_DIR/.venv" ]; then
  source "$PROJECT_DIR/.venv/bin/activate"
elif [ -d "$PROJECT_DIR/backend/.venv" ]; then
  source "$PROJECT_DIR/backend/.venv/bin/activate"
fi

if [ -f "$PROJECT_DIR/backend/requirements.txt" ]; then
  echo "==> [sync.sh] Installing backend dependencies..."
  pip install -r "$PROJECT_DIR/backend/requirements.txt"
fi

echo "==> [sync.sh] Running Django database migrations..."
cd "$PROJECT_DIR/backend"
python manage.py migrate --noinput

echo "==> [sync.sh] Seeding initial 5 users (venkatesh, rahul, akash, anish, aatesh)..."
python manage.py setup_initial_users

echo "==> [sync.sh] Building frontend asset bundle..."
cd "$PROJECT_DIR/frontend"
if command -v npm >/dev/null 2>&1; then
  npm install
  npm run build
fi

cd "$PROJECT_DIR"
echo "==> [sync.sh] Restarting systemd services..."
sudo systemctl restart splitwise_backend.service || echo "Warning: splitwise_backend service restart pending."
sudo systemctl restart splitwise_frontend.service || echo "Warning: splitwise_frontend service restart pending."

echo "==> ✅ Sync completed successfully."
