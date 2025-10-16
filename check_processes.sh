#!/bin/bash
# check_processes.sh - Check for running Python processes and port usage

echo "🔍 Checking for running processes..."

echo "Python processes:"
ps aux | grep -E "(python.*app\.py|python3.*app\.py)" | grep -v grep || echo "No Python app processes found"

echo ""
echo "Port 5000 usage:"
sudo lsof -i :5000 2>/dev/null || echo "Port 5000 is free"

echo ""
echo "All Python processes:"
ps aux | grep python | grep -v grep || echo "No Python processes found"
