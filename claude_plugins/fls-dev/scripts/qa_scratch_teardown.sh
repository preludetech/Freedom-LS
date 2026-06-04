#!/bin/bash
# qa_scratch_teardown.sh — Remove specific QA scratch files produced by a single run.
# Usage: ./qa_scratch_teardown.sh <file1> [<file2> ...]
#
# Takes an explicit list of file paths as arguments. For each path:
#   - Resolves it with realpath.
#   - Refuses to act unless it is a regular file inside ${CLAUDE_PROJECT_DIR}/.sdd-work/.
#   - Removes it with rm -f.
#
# NEVER accepts directories, globs, or a bare invocation with no arguments.
# The .sdd-work/ directory itself is SHARED with other SDD commands and is
# never wiped wholesale — only the specific named files are removed.

set -euo pipefail

: "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR must be set}"

SCRATCH_DIR="${CLAUDE_PROJECT_DIR}/.sdd-work"

if [ "${#}" -eq 0 ]; then
  echo "Error: at least one file path argument is required" >&2
  exit 1
fi

for arg in "$@"; do
  # Resolve to an absolute path. realpath will fail if the file does not exist,
  # so check existence first and skip gracefully.
  if [ ! -e "$arg" ]; then
    echo "Skipping (does not exist): $arg"
    continue
  fi

  RESOLVED="$(realpath "$arg")"

  # Refuse directories — only regular files are accepted.
  if [ -d "$RESOLVED" ]; then
    echo "Error: refusing to remove directory: $RESOLVED" >&2
    exit 1
  fi

  # Require the file to be inside .sdd-work/ (exact prefix match).
  if [[ "$RESOLVED" != "${SCRATCH_DIR}/"* ]]; then
    echo "Error: refusing to remove file outside .sdd-work/: $RESOLVED" >&2
    exit 1
  fi

  rm -f "$RESOLVED"
  echo "Removed: $RESOLVED"
done
