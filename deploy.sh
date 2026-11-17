#!/bin/bash

# Exit on error
set -e

main() {
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

    cd "$DIR"

    # Get the current commit hash before pulling
    # If this is a fresh clone and there is no HEAD, this might fail, so we catch it
    OLD_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")

    # Pull the latest code
    echo "Pulling latest code from $BRANCH..."
    git fetch origin
    git reset --hard "origin/$BRANCH"

    # Check if frontend changed
    echo "Checking if frontend needs a rebuild..."
    if [ -z "$OLD_HEAD" ]; then
        FRONTEND_CHANGED="yes"
    else
        FRONTEND_CHANGED=$(git diff --name-only "$OLD_HEAD" HEAD | grep "^frontend/" || true)
    fi

    if [ -n "$FRONTEND_CHANGED" ] || [ ! -d "frontend/dist" ]; then
        echo "Frontend changes detected (or dist missing). Rebuilding frontend..."
        cd frontend
        npm ci
        export XDG_RUNTIME_DIR="/run/user/$(id -u)" 2>/dev/null || true
        if command -v systemd-run >/dev/null 2>&1 && systemd-run --user --scope -p MemoryMax=1500M -p CPUQuota=75% npm run build; then
            echo "Frontend build completed with systemd-run."
        else
            echo "systemd-run unavailable or failed; building frontend directly with memory limit..."
            NODE_OPTIONS="--max-old-space-size=1536" npm run build
        fi
        cd ..
    else
        echo "No frontend changes detected. Skipping frontend build."
    fi

    # Snapshot the database before migrations touch it. Best effort: a missing backup
    # directory (the timer isn't installed yet) must not stop a deploy.
    if [ "$ENVIRONMENT" == "prod" ] && [ -x "$DIR/backup/backup.sh" ]; then
        echo "Taking a pre-deploy database snapshot..."
        "$DIR/backup/backup.sh" predeploy || echo "WARNING: pre-deploy snapshot failed; continuing."
    fi

    # Check if backend requirements changed
    if [ -n "$OLD_HEAD" ]; then
        BACKEND_DEPS_CHANGED=$(git diff --name-only "$OLD_HEAD" HEAD | grep "^backend/requirements.txt" || true)
    else
        BACKEND_DEPS_CHANGED=""
    fi
    if [ -n "$BACKEND_DEPS_CHANGED" ]; then
        echo "Backend dependencies changed. Updating python packages..."
        "$DIR/.venv/bin/pip" install -r "$DIR/backend/requirements.txt"
    fi

    # Run backend migrations
    echo "Running database migrations..."
    cd backend
    "$DIR/.venv/bin/python" manage.py migrate
    cd ..

    # Restart the backend service
    echo "Restarting backend service..."
    sudo systemctl restart "$SERVICE_NAME"

    echo "Deployment to $ENVIRONMENT complete!"
}

main "$@"
