#!/bin/bash

# Exit on error
set -e

# Validate arguments
ENVIRONMENT=$1
if [ "$ENVIRONMENT" != "prod" ] && [ "$ENVIRONMENT" != "uat" ]; then
    echo "Usage: $0 [prod|uat]"
    exit 1
fi

# Set variables based on environment
if [ "$ENVIRONMENT" == "prod" ]; then
    BRANCH="main"
    SERVICE_NAME="splitwise_backend.service"
    DIR="/opt/splitwise"
else
    BRANCH="uat"
    SERVICE_NAME="splitwise_backend_uat.service"
    DIR="/opt/splitwise-uat"
fi

echo "Deploying $ENVIRONMENT environment from branch $BRANCH..."

cd $DIR

# Get the current commit hash before pulling
# If this is a fresh clone and there is no HEAD, this might fail, so we catch it
OLD_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")

# Pull the latest code
echo "Pulling latest code from $BRANCH..."
git fetch origin
git reset --hard origin/$BRANCH

# Check if frontend changed
echo "Checking if frontend needs a rebuild..."
if [ -z "$OLD_HEAD" ]; then
    FRONTEND_CHANGED="yes"
else
    FRONTEND_CHANGED=$(git diff --name-only $OLD_HEAD HEAD | grep "^frontend/" || true)
fi

if [ -n "$FRONTEND_CHANGED" ] || [ ! -d "frontend/dist" ]; then
    echo "Frontend changes detected (or dist missing). Rebuilding frontend..."
    cd frontend
    npm ci
    systemd-run --user --scope -p MemoryMax=1500M -p CPUQuota=75% npm run build
    cd ..
else
    echo "No frontend changes detected. Skipping frontend build."
fi

# Run backend migrations
echo "Running database migrations..."
cd backend
../.venv/bin/python manage.py migrate
cd ..

# Restart the backend service
echo "Restarting backend service..."
sudo systemctl restart $SERVICE_NAME

echo "Deployment to $ENVIRONMENT complete!"
