#!/usr/bin/env bash
set -euo pipefail

PYTHON="python3"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

BACKEND_SERVICE="splitwise_backend.service"
BACKEND_SERVICE_PATH="/etc/systemd/system/$BACKEND_SERVICE"

FRONTEND_SERVICE="splitwise_frontend.service"
FRONTEND_SERVICE_PATH="/etc/systemd/system/$FRONTEND_SERVICE"

echo "==> [setup.sh] Checking for $PYTHON..."
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Error: $PYTHON not found. Please install Python 3 and retry."
  exit 1
fi

echo "==> [setup.sh] Ensuring python3-venv and essential tools are installed..."
sudo dpkg --configure -a || true
if ! python3 -m venv test_venv_check 2>/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y python3-venv python3-pip python3-dev build-essential nodejs npm || true
else
  rm -rf test_venv_check
fi

echo "==> [setup.sh] Creating virtual environment ($VENV_DIR) if missing..."
if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
  rm -rf "$VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

echo "==> [setup.sh] Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "==> [setup.sh] Upgrading pip & installing dependencies..."
python -m pip install --upgrade pip setuptools wheel
if [ -f "$PROJECT_DIR/backend/requirements.txt" ]; then
  pip install -r "$PROJECT_DIR/backend/requirements.txt"
fi
pip install gunicorn

echo "==> [setup.sh] Running Django database migrations..."
cd "$PROJECT_DIR/backend"
python manage.py migrate --noinput

echo "==> [setup.sh] Seeding initial 5 users (venkatesh, rahul, akash, anish, aatesh)..."
python manage.py setup_initial_users

echo "==> [setup.sh] Installing Node & building frontend on port 5001..."
cd "$PROJECT_DIR/frontend"
if command -v npm >/dev/null 2>&1; then
  npm install
  npm run build
  npm install -g serve || true
fi

cd "$PROJECT_DIR"

echo "==> [setup.sh] Creating systemd service: $BACKEND_SERVICE (Port 5002)"
sudo bash -c "cat > '$BACKEND_SERVICE_PATH'" <<EOF
[Unit]
Description=Gunicorn for Splitwise Backend (Port 5002)
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(id -gn)
WorkingDirectory=$PROJECT_DIR/backend
Environment=PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=$VENV_DIR/bin/gunicorn --bind 0.0.0.0:5002 splitwise_backend.wsgi:application --workers 3
Restart=always
RestartSec=3
KillSignal=SIGQUIT
TimeoutStopSec=10
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "==> [setup.sh] Creating systemd service: $FRONTEND_SERVICE (Port 5001)"
NODE_SERVE_BIN="$(command -v serve || echo "/usr/local/bin/serve")"
sudo bash -c "cat > '$FRONTEND_SERVICE_PATH'" <<EOF
[Unit]
Description=Production Frontend for Splitwise (Port 5001)
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(id -gn)
WorkingDirectory=$PROJECT_DIR/frontend
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:\$PATH
ExecStart=npx serve -s dist -l 5001
Restart=always
RestartSec=3
KillSignal=SIGQUIT
TimeoutStopSec=10
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "==> [setup.sh] Reloading systemd & enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable "$BACKEND_SERVICE" "$FRONTEND_SERVICE"
sudo systemctl restart "$BACKEND_SERVICE" "$FRONTEND_SERVICE"

echo "==> ✅ Splitwise Server Setup complete."
sudo systemctl status "$BACKEND_SERVICE" "$FRONTEND_SERVICE" --no-pager || true
