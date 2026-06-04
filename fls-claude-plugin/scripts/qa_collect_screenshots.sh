#!/bin/bash
# qa_collect_screenshots.sh — Move screenshots from the shared output dir into the spec dir.
# Usage: ./qa_collect_screenshots.sh <spec-dir>
#
# Takes the QA run's spec directory as $1. Moves every file from
# ${CLAUDE_PROJECT_DIR}/qa-screenshots/ into <spec-dir>/screenshots/,
# then removes the now-empty qa-screenshots/ directory so it does not
# accumulate across runs.

set -euo pipefail

: "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR must be set}"

if [ -z "${1:-}" ]; then
  echo "Error: spec-dir argument is required" >&2
  exit 1
fi

SPEC_DIR="$(realpath "$1")"

# Validate the spec dir is inside the project (security: the script is
# allow-listed with arbitrary arguments, so an unvalidated path such as
# ../../somewhere could move screenshots outside the project).
if [[ "$SPEC_DIR" != "${CLAUDE_PROJECT_DIR}/"* ]]; then
  echo "Error: spec-dir must be inside CLAUDE_PROJECT_DIR" >&2
  exit 1
fi

SRC_DIR="${CLAUDE_PROJECT_DIR}/qa-screenshots"
DEST_DIR="${SPEC_DIR}/screenshots"

mkdir -p "$DEST_DIR"

if [ -d "$SRC_DIR" ]; then
  # Move each file individually (mv glob, not recursive delete).
  shopt -s nullglob
  files=("$SRC_DIR"/*)
  if [ "${#files[@]}" -gt 0 ]; then
    mv "${files[@]}" "$DEST_DIR/"
    echo "Moved ${#files[@]} file(s) to $DEST_DIR"
  else
    echo "No screenshots found in $SRC_DIR"
  fi
  # Remove the now-empty source directory (plain rmdir — safe only if empty).
  if rmdir "$SRC_DIR" 2>/dev/null; then
    echo "Removed $SRC_DIR"
  fi
else
  echo "Source directory $SRC_DIR does not exist; nothing to move."
fi
