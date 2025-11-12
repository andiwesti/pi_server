#!/bin/bash
# Fix Cloudflare tunnel connection issues

echo "🔧 Fixing Cloudflare Tunnel Connection Issues"
echo "============================================="

echo ""
echo "The 'context canceled' error indicates Cloudflare tunnel connection problems."
echo "This usually happens when:"
echo "1. Server becomes unresponsive"
echo "2. Too many connections accumulate"
echo "3. Memory/CPU issues"
echo ""

echo "🛠️  SOLUTION STEPS:"
echo "=================="

echo ""
echo "1. Clean restart the server:"
echo "   ./restart_clean.sh"

echo ""
echo "2. If that doesn't work, restart Cloudflare tunnel:"
echo "   - Stop the current tunnel (Ctrl+C)"
echo "   - Wait 10 seconds"
echo "   - Start tunnel again: cloudflared tunnel --url http://localhost:5000"

echo ""
echo "3. Check server resources:"
echo "   - Monitor CPU usage: top"
echo "   - Monitor memory: free -h"
echo "   - Check for memory leaks"

echo ""
echo "4. If persistent issues, try:"
echo "   - Reboot the Raspberry Pi"
echo "   - Check for other processes using resources"
echo "   - Monitor server logs for errors"

echo ""
echo "📊 Current server status:"
echo "========================"

# Check server health
if curl -s http://localhost:5000/health > /dev/null; then
    echo "✅ Local server is responding"
else
    echo "❌ Local server is not responding"
fi

# Check processes
echo ""
echo "Python processes:"
ps aux | grep "python3 app.py" | grep -v grep || echo "No Python processes found"

echo ""
echo "Port 5000 usage:"
sudo lsof -i :5000 || echo "Port 5000 is free"

echo ""
echo "💡 Quick fix - restart everything:"
echo "======================================"
echo "1. Stop Cloudflare tunnel (Ctrl+C)"
echo "2. Run: ./restart_clean.sh"
echo "3. Start new Cloudflare tunnel"
echo "4. Test the connection"
