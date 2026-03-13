#!/usr/bin/env bash
START_PORT=8000
PORT=$((START_PORT + RANDOM % 1000))

while ss -tlnp | grep -q ":${PORT} "; do
    PORT=$((PORT + 1))
done

echo "$PORT"
