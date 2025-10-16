# Process Management Solution

## Problem
When Cloudflare tunnel shuts down, old Python processes don't get cleaned up properly. When starting a new tunnel, these old processes interfere with new ones, causing LED and server functionality issues.

## Solution Files Created

### 1. `simple_cleanup.sh` - Simple cleanup (RECOMMENDED)
```bash
./simple_cleanup.sh
```
- Kills Python app processes
- Frees port 5000
- Simple and reliable

### 2. `simple_start.sh` - Simple server start (RECOMMENDED)
```bash
./simple_start.sh
```
- Runs simple cleanup first
- Starts server cleanly
- No complex process management

### 3. `cleanup.sh` - Advanced cleanup (if needed)
```bash
./cleanup.sh
```
- More thorough cleanup
- Use if simple cleanup doesn't work

### 4. `start_server.sh` - Advanced start (if needed)
```bash
./start_server.sh
```
- More complex startup
- Use if simple start doesn't work

### 3. `check_processes.sh` - Monitor running processes
```bash
./check_processes.sh
```
- Shows all Python processes
- Checks port 5000 usage
- Helps diagnose issues

## Usage Instructions

### When Cloudflare Tunnel Shuts Down:
1. Run simple cleanup: `./simple_cleanup.sh`
2. Verify: `./check_processes.sh`
3. Start server: `./simple_start.sh`

### When Starting New Tunnel:
1. Always run simple cleanup first: `./simple_cleanup.sh`
2. Start server: `./simple_start.sh`
3. Test: `curl -s http://localhost:5000/health`

### If Simple Solution Doesn't Work:
1. Use advanced cleanup: `./cleanup.sh`
2. Start with advanced script: `./start_server.sh`

### Emergency Cleanup:
If processes are stuck, use:
```bash
sudo pkill -9 python3
sudo lsof -i :5000  # Check if port is free
```

## Server Improvements
- Added signal handlers for graceful shutdown
- LED initialization moved to main() function
- Better cleanup on exit
- Process conflict prevention

## Testing
- Health check: `curl -s http://localhost:5000/health`
- LED test: `curl -X POST http://localhost:5000/led -H "Content-Type: application/json" -d '{"state": "on"}'`
- Process check: `./check_processes.sh`
