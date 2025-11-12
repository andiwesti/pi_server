#!/bin/bash
# Clean restart script for the Flask server

echo "🔄 Clean Restart Script"
echo "======================="

# Change to the correct directory
cd /home/anders/pi_server

echo "1. Cleaning up old processes..."
./simple_cleanup.sh

echo ""
echo "2. Waiting for cleanup to complete..."
sleep 3

echo ""
echo "3. Starting fresh server..."
./simple_start.sh &

echo ""
echo "4. Waiting for server to start..."
sleep 5

echo ""
echo "5. Testing server..."
if curl -s http://localhost:5000/health > /dev/null; then
    echo "✅ Server is running and healthy"
    echo "✅ LED control: curl -X POST http://localhost:5000/led -H 'Content-Type: application/json' -d '{\"state\": \"on\"}'"
    echo "✅ Live stream: http://localhost:5000/camera/stream"
else
    echo "❌ Server failed to start"
    echo "Check logs or try manual start: python3 app.py"
fi

echo ""
echo "📋 To use this script in the future:"
echo "   ./restart_clean.sh"
