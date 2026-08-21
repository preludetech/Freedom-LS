#!/bin/bash
# qa_cleanup.sh — Remove the previous QA run's artifacts from a spec directory.
# Usage: ./qa_cleanup.sh <spec-dir>
#
# Takes the QA run's spec directory as $1 and removes the qa_report.md and
# screenshots/ directory it holds, so the next run starts clean.

set -euo pipefail

: "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR must be set}"

if [ -z "${1:-}" ]; then
  echo "Error: spec-dir argument is required" >&2
  exit 1
fi

if [ ! -d "$1" ]; then
  echo "Error: spec-dir is not a directory: $1" >&2
  exit 1
fi

# Resolve the project root with realpath so the boundary check below compares
# like-for-like with the realpath-resolved SPEC_DIR. Without this, a symlinked
# component in CLAUDE_PROJECT_DIR would make the prefix check falsely reject a
# legitimate in-project spec dir.
PROJECT_ROOT="$(realpath "$CLAUDE_PROJECT_DIR")"
SPEC_DIR="$(realpath "$1")"

# Validate the spec dir is inside the project (security: the script is
# allow-listed with arbitrary arguments, so an unvalidated path such as
# ../../somewhere could delete files outside the project).
if [[ "$SPEC_DIR" != "${PROJECT_ROOT}/"* ]]; then
  echo "Error: spec-dir must be inside CLAUDE_PROJECT_DIR" >&2
  exit 1
fi

if [ -f "${SPEC_DIR}/qa_report.md" ]; then
  rm -f "${SPEC_DIR}/qa_report.md"
  echo "Removed ${SPEC_DIR}/qa_report.md"
fi

# Remove the screenshots directory file-by-file, then rmdir it. The recursive
# force-delete form is blocked by the security-guard hook by design, and a
# per-file loop keeps the blast radius visible.
SHOTS_DIR="${SPEC_DIR}/screenshots"
if [ -d "$SHOTS_DIR" ]; then
  shopt -s nullglob dotglob
  for f in "$SHOTS_DIR"/*; do
    if [ -f "$f" ]; then
      rm -f "$f"
    else
      echo "Warning: leaving non-regular entry in place: $f" >&2
    fi
  done
  shopt -u nullglob dotglob
  if rmdir "$SHOTS_DIR" 2>/dev/null; then
    echo "Removed ${SHOTS_DIR}/"
  else
    echo "Warning: ${SHOTS_DIR}/ not empty after cleanup; left in place" >&2
  fi
fi
