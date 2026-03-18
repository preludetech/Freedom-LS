#!/bin/bash
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""')

if [[ "$FILE_PATH" =~ \.py$ ]]; then
    RESULTS=$(uv run bandit -q -ll "$FILE_PATH" 2>&1) || true
    if [[ -n "$RESULTS" ]]; then
        echo "Bandit found issues in $FILE_PATH:"
        echo "$RESULTS"
    fi
fi

exit 0
