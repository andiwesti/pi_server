# ~/pi_server/start_server.sh
#!/bin/bash
set -euo pipefail

# Kör från mappen som INNEHÅLLER app.py
APP_ROOT="/home/anders/pi_server"
cd "$APP_ROOT"

# (valfritt) miljö
export PYTHONUNBUFFERED=1

echo "🚀 Starting Flask server from $APP_ROOT ..."
exec /usr/bin/python3 app.py

