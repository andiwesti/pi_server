#!/bin/bash
# Stable server startup with connection management

echo "🚀 Starting Stable Flask Server"
echo "==============================="

# Change to the correct directory
cd /home/anders/pi_server

echo "1. Cleaning up any existing processes..."
./simple_cleanup.sh

echo ""
echo "2. Waiting for cleanup..."
sleep 3

echo ""
echo "3. Starting server with connection management..."
# Start server with proper connection handling
python3 app.py &

echo ""
echo "4. Waiting for server to initialize..."
sleep 5

echo ""
echo "5. Testing server functionality..."

# Test health endpoint
if curl -s http://localhost:5000/health > /dev/null; then
    echo "✅ Health endpoint: OK"
else
    echo "❌ Health endpoint: FAILED"
    exit 1
fi

# Test LED endpoint
if curl -s -X POST http://localhost:5000/led -H "Content-Type: application/json" -d '{"state": "on"}' > /dev/null; then
    echo "✅ LED endpoint: OK"
else
    echo "❌ LED endpoint: FAILED"
fi

# Test camera stream (quick test)
echo "Testing camera stream..."
timeout 2 curl -s http://localhost:5000/camera/stream > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Camera stream: OK"
else
    echo "⚠️  Camera stream: May need camera connection"
fi

echo ""
echo "📊 Server Status:"
echo "================="
echo "Server PID: $(pgrep -f 'python3 app.py')"
echo "Port 5000: $(sudo lsof -i :5000 | grep LISTEN | wc -l) listener(s)"
echo "Memory usage: $(ps aux | grep 'python3 app.py' | grep -v grep | awk '{print $4"%"}')"

echo ""
echo "🌐 For Cloudflare tunnel:"
echo "========================="
echo "1. Start tunnel: cloudflared tunnel --url http://localhost:5000"
echo "2. Test: curl https://your-tunnel-url.trycloudflare.com/health"
echo "3. If issues: Stop tunnel, wait 10s, restart tunnel"

echo ""
echo "✅ Server is ready!"
echo "LED control: curl -X POST http://localhost:5000/led -H 'Content-Type: application/json' -d '{\"state\": \"on\"}'"
echo "Live stream: http://localhost:5000/camera/stream"


