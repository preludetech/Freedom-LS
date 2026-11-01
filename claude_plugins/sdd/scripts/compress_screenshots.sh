#!/bin/bash
# compress_screenshots.sh — Compress oversized QA screenshots under a directory (default spec_dd/).
# Usage: compress_screenshots.sh [--max-kb N] [--quality N] [DIR]
#
# Thin wrapper around compress_screenshots.py. It exists so callers have a stable
# claude_plugins/sdd/scripts/ path to invoke: the Python script must be located
# relative to the plugin, and ${CLAUDE_PLUGIN_ROOT} is not reliably exported into
# the Bash tool environment (and resolves to the wrong plugin when the caller is
# an agent from a different plugin).
#
# compress_screenshots.py scans DIR (default spec_dd/) relative to the project root and
# refuses a DIR outside it, so it must run from the project root; this wrapper enforces that rather than relying on
# the caller's working directory.

set -euo pipefail

# The Bash tool does not reliably export CLAUDE_PROJECT_DIR. The git work tree is the
# project root; outside one there is no safe default, so the script stops.
if [ -z "${CLAUDE_PROJECT_DIR:-}" ]; then
  CLAUDE_PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "Error: CLAUDE_PROJECT_DIR is unset and the working directory is not a git work tree" >&2
    exit 1
  }
fi
export CLAUDE_PROJECT_DIR

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_ROOT="$(realpath "$CLAUDE_PROJECT_DIR")"

cd "$PROJECT_ROOT"
# uv run is the one project tool this script assumes: it gives pillow an isolated runner.
exec uv run --with pillow python "${SCRIPT_DIR}/compress_screenshots.py" "$@"
