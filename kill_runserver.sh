#! /bin/sh

# s -tlnp | grep 8000
# Example output: LISTEN 0      10                       127.0.0.1:8000       0.0.0.0:*    users:(("python3",pid=2853093,fd=4))

PID=$(ss -tlnp | grep 8000 | grep -oP 'pid=\K[0-9]+')

if [ -n "$PID" ]; then
    kill "$PID"
    echo "Killed process $PID on port 8000"
else
    echo "No process found on port 8000"
fi
