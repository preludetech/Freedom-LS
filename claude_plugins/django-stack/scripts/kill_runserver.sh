#! /bin/sh

# Usage: ./kill_runserver.sh [port]
# Example: ./kill_runserver.sh 8010

PORT=${1:-8000}

# ss -tlnp | grep $PORT
# Example output: LISTEN 0      10                       127.0.0.1:8000       0.0.0.0:*    users:(("python3",pid=2853093,fd=4))

PID=$(ss -tlnp | grep ":$PORT " | grep -oP 'pid=\K[0-9]+')

if [ -n "$PID" ]; then
    kill "$PID"
    echo "Killed process $PID on port $PORT"
else
    echo "No process found on port $PORT"
fi
