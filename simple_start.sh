#!/bin/bash
# simple_start.sh - Simple server start with basic cleanup

echo "🚀 Starting Flask Pi Server..."

# Change to the correct directory
cd /home/anders/pi_server

# Run simple cleanup
echo "Running simple cleanup..."
./simple_cleanup.sh

# Wait a moment
sleep 2

# Start the server
echo "Starting Flask server..."
python3 app.py
