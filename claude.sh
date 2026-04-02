#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLS_PLUGIN=1 claude --plugin-dir "$SCRIPT_DIR/fls-claude-plugin" "$@"
