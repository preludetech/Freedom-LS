#!/bin/bash
# compress_screenshots.sh — Compress oversized QA screenshots under spec_dd/.
# Usage: ./compress_screenshots.sh [--max-kb N] [--quality N]
#
# Thin wrapper around compress_screenshots.py. It exists so callers have a stable
# .claude/fls-dev/scripts/ path to invoke: the Python script must be located
# relative to the plugin, and ${CLAUDE_PLUGIN_ROOT} is not reliably exported into
# the Bash tool environment (and resolves to the wrong plugin when the caller is
# an agent from a different plugin).
#
# compress_screenshots.py scans ${CLAUDE_PROJECT_DIR}/spec_dd/ and must therefore
# run from the project root; this wrapper enforces that rather than relying on
# the caller's working directory.

set -euo pipefail

: "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR must be set}"

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_ROOT="$(realpath "$CLAUDE_PROJECT_DIR")"

cd "$PROJECT_ROOT"
exec uv run --with pillow python "${SCRIPT_DIR}/compress_screenshots.py" "$@"
