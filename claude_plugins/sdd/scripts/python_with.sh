#!/bin/bash
# python_with.sh — Run Python with one extra package available.
# Usage: python_with.sh <package> [python arguments...]
#
# The command comes from the `Python with packages` key under `## Script Hooks` in
# .claude/sdd/config.local.md, then .claude/sdd/config.md. `{packages}` in the value is replaced
# by <package>, and the arguments are appended. A blank or missing key means plain `python3`,
# which works when the package is already installed for it.

set -euo pipefail

KEY="Python with packages"

if [ $# -lt 1 ]; then
  echo "Usage: python_with.sh <package> [python arguments...]" >&2
  exit 64
fi
PACKAGE="$1"
shift

# The Bash tool does not reliably export CLAUDE_PROJECT_DIR. The git work tree is the
# project root; outside one there is no config to read, so the script stops.
if [ -z "${CLAUDE_PROJECT_DIR:-}" ]; then
  CLAUDE_PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "Error: CLAUDE_PROJECT_DIR is unset and the working directory is not a git work tree" >&2
    exit 1
  }
fi

RUNNER=""
for config in "$CLAUDE_PROJECT_DIR/.claude/sdd/config.local.md" "$CLAUDE_PROJECT_DIR/.claude/sdd/config.md"; do
  [ -f "$config" ] || continue
  RUNNER="$(sed -n "s/^- ${KEY}:[[:space:]]*\(.*[^[:space:]]\)[[:space:]]*$/\1/p" "$config" | head -n 1)"
  [ -z "$RUNNER" ] || break
done

if [ -z "$RUNNER" ]; then
  exec python3 "$@"
fi

read -ra COMMAND <<< "${RUNNER//\{packages\}/$PACKAGE}"
exec "${COMMAND[@]}" "$@"
