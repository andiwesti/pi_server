#!/bin/bash
# cleanup.sh - Clean up all Python processes and free port 5000

echo "🧹 Cleaning up old processes..."

# Kill all Python processes related to app.py
echo "Killing Python app processes..."
pkill -f "python3 app.py" 2>/dev/null || true
pkill -f "python.*app\.py" 2>/dev/null || true

# Wait a moment for processes to terminate
sleep 2

# Force kill any remaining Python processes if needed
echo "Force killing any remaining Python processes..."
sudo pkill -9 -f "python3 app.py" 2>/dev/null || true

# Check if port 5000 is still in use and kill the process
echo "Checking port 5000..."
PORT_PID=$(sudo lsof -ti :5000 2>/dev/null || true)
if [ ! -z "$PORT_PID" ]; then
    echo "Killing process $PORT_PID using port 5000..."
    sudo kill -9 $PORT_PID 2>/dev/null || true
fi

# Wait for cleanup
sleep 1

# Verify cleanup
REMAINING=$(ps aux | grep -E "(python.*app\.py|python3.*app\.py)" | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  Warning: Some processes may still be running"
    ps aux | grep -E "(python.*app\.py|python3.*app\.py)" | grep -v grep
else
    echo "✅ Cleanup completed successfully"
fi

echo "Port 5000 status:"
sudo lsof -i :5000 2>/dev/null || echo "Port 5000 is free"
