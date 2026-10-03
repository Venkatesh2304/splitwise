#!/bin/bash
# Script to sync Production Database to UAT Database.
# Run this script on the server as the 'rama' user: bash sync-prod-db-to-uat.sh

echo "Syncing Production Database to UAT..."

PROD_DB="/opt/splitwise/backend/db.sqlite3"
UAT_DB="/opt/splitwise-uat/backend/db.sqlite3"
BACKUP_DB="/opt/splitwise-uat/backend/db.sqlite3.backup_$(date +%F_%T)"

if [ ! -f "$PROD_DB" ]; then
    echo "Error: Production database not found at $PROD_DB"
    exit 1
fi

if [ ! -d "/opt/splitwise-uat/backend" ]; then
    echo "Error: UAT backend directory not found. Have you run the setup script?"
    exit 1
fi

# Stop the UAT service to prevent writes during copy
echo "Stopping UAT service..."
sudo systemctl stop splitwise_backend_uat.service

# Backup current UAT DB if it exists
if [ -f "$UAT_DB" ]; then
    echo "Backing up current UAT database to $BACKUP_DB"
    cp "$UAT_DB" "$BACKUP_DB"
fi

# Copy Prod DB to UAT
echo "Copying Prod DB to UAT..."
cp "$PROD_DB" "$UAT_DB"

# Ensure proper permissions
chown rama:rama "$UAT_DB"

# Start the UAT service
echo "Starting UAT service..."
sudo systemctl start splitwise_backend_uat.service

echo "Database sync complete! UAT now has fresh data from Production."
