#!/bin/bash
# simple_cleanup.sh - Simple cleanup without complex process management

echo "🧹 Simple cleanup..."

# Kill any Python processes running app.py
pkill -f "python3 app.py" 2>/dev/null || true

# Wait a moment
sleep 1

# Check if port 5000 is free
if sudo lsof -i :5000 >/dev/null 2>&1; then
    echo "Port 5000 still in use, force killing..."
    sudo pkill -9 -f "python3 app.py" 2>/dev/null || true
    sleep 1
fi

echo "✅ Simple cleanup completed"
