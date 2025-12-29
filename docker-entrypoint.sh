#!/bin/bash
set -e

# Fix permissions for media directory if it exists
if [ -d "/app/media" ]; then
    # Ensure appuser (UID 1000) owns the media directory
    chown -R appuser:appuser /app/media
fi

# Fix permissions for logs directory if it exists
if [ -d "/app/logs" ]; then
    chown -R appuser:appuser /app/logs
fi

# Switch to appuser and execute the command
exec gosu appuser "$@"
