#!/bin/bash
# One-time root setup script for the UAT environment on the constrained 1GB RAM server.
# Run this script with: sudo bash setup-uat-root.sh

# 1. Ensure running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo bash setup-uat-root.sh)"
  exit 1
fi

echo "Starting UAT Environment Setup..."

# 2. Setup UAT Directory Structure
UAT_DIR="/opt/splitwise-uat"
if [ ! -d "$UAT_DIR" ]; then
    echo "Creating UAT directory from Prod..."
    cp -r /opt/splitwise "$UAT_DIR"
    chown -R rama:rama "$UAT_DIR"
    
    # Configure UAT Git to track 'uat' branch
    sudo -u rama bash -c "cd $UAT_DIR && git checkout -b uat || git checkout uat"
else
    echo "UAT directory already exists at $UAT_DIR."
fi

# 3. Create UAT Systemd Service
echo "Creating UAT Systemd Backend Service..."
cat << 'EOF' > /etc/systemd/system/splitwise_backend_uat.service
[Unit]
Description=Splitwise UAT backend (gunicorn, 127.0.0.1:5003), run as rama
After=network.target

[Service]
Type=simple
User=rama
Group=rama
WorkingDirectory=/opt/splitwise-uat/backend
Environment=PATH=/opt/splitwise-uat/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=/opt/splitwise-uat/.venv/bin/gunicorn --bind 127.0.0.1:5003 splitwise_backend.wsgi:application --workers 2
Restart=always
RestartSec=3
KillSignal=SIGQUIT
TimeoutStopSec=10
PrivateTmp=true
NoNewPrivileges=true
MemoryMax=250M

[Install]
WantedBy=multi-user.target
EOF

# 4. Grant 'rama' user passwordless sudo for the UAT service
echo "Configuring sudo permissions for 'rama' to restart UAT service..."
echo "rama ALL=(root) NOPASSWD: /usr/bin/systemctl start splitwise_backend_uat.service, /usr/bin/systemctl stop splitwise_backend_uat.service, /usr/bin/systemctl restart splitwise_backend_uat.service" > /etc/sudoers.d/rama-splitwise-uat
chmod 0440 /etc/sudoers.d/rama-splitwise-uat

# 5. Create UAT Caddy Configuration
echo "Creating UAT Caddy Configuration..."
cat << 'EOF' > /etc/caddy/sites/splitwise-uat.caddy
# Splitwise UAT Environment
uat-ramasplit.duckdns.org, uat-130-210-44-146.sslip.io {
	encode zstd gzip

	@backend path /api/* /admin/*
	handle @backend {
		reverse_proxy 127.0.0.1:5003
	}

	handle {
		root * /opt/splitwise-uat/frontend/dist
		@hashed path /assets/*
		header @hashed Cache-Control "public, max-age=31536000, immutable"
		@fresh not path /assets/*
		header @fresh Cache-Control "no-cache"
		try_files {path} /index.html
		file_server
	}
}
EOF

# 6. Apply Configurations
echo "Reloading systemd daemon and enabling UAT backend service..."
systemctl daemon-reload
systemctl enable splitwise_backend_uat.service
systemctl restart splitwise_backend_uat.service

echo "Reloading Caddy to apply UAT frontend routes..."
systemctl reload caddy

echo ""
echo "=========================================================="
echo "✅ UAT Setup Complete!"
echo "UAT Backend running on port 5003."
echo "UAT Frontend available at uat-ramasplit.duckdns.org"
echo "GitHub Actions CI pipeline can now deploy automatically!"
echo "=========================================================="
