#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_PLUGINS_LOADED=1 claude \
  --plugin-dir "$SCRIPT_DIR/claude_plugins/django-stack-claude-plugin" \
  --plugin-dir "$SCRIPT_DIR/claude_plugins/fls-dev-claude-plugin" \
  --plugin-dir "$SCRIPT_DIR/claude_plugins/sdd-claude-plugin" \
  "$@"
