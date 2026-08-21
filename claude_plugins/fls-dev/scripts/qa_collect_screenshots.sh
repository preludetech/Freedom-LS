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
# ../../somewhere could move screenshots outside the project).
if [[ "$SPEC_DIR" != "${PROJECT_ROOT}/"* ]]; then
  echo "Error: spec-dir must be inside CLAUDE_PROJECT_DIR" >&2
  exit 1
fi

SRC_DIR="${PROJECT_ROOT}/qa-screenshots"
DEST_DIR="${SPEC_DIR}/screenshots"

mkdir -p "$DEST_DIR"

skipped=0

if [ -d "$SRC_DIR" ]; then
  # Move each entry individually (mv per file, never a recursive delete).
  # dotglob so a stray dotfile cannot silently strand the source directory.
  shopt -s nullglob dotglob
  entries=("$SRC_DIR"/*)
  shopt -u nullglob dotglob
  if [ "${#entries[@]}" -gt 0 ]; then
    moved=0
    for f in "${entries[@]}"; do
      # Only regular files are screenshots. Playwright MCP can write trace and
      # artifact subdirectories here; leave those where they are.
      if [ ! -f "$f" ]; then
        echo "Warning: skipping non-regular entry: $f" >&2
        skipped=1
        continue
      fi
      dest="$DEST_DIR/$(basename "$f")"
      # Don't silently clobber a same-named screenshot from an earlier collect;
      # warn and skip so the existing file (and its report reference) survives.
      if [ -e "$dest" ]; then
        echo "Warning: $dest already exists — skipping $(basename "$f")" >&2
        skipped=1
        continue
      fi
      mv "$f" "$dest"
      moved=$((moved + 1))
    done
    echo "Moved ${moved} file(s) to $DEST_DIR"
  else
    echo "No screenshots found in $SRC_DIR"
  fi
  # Remove the now-empty source directory (plain rmdir — safe only if empty).
  if rmdir "$SRC_DIR" 2>/dev/null; then
    echo "Removed $SRC_DIR"
  elif [ -d "$SRC_DIR" ]; then
    echo "Warning: $SRC_DIR not empty after collect; left in place" >&2
    skipped=1
  fi
else
  echo "Source directory $SRC_DIR does not exist; nothing to move."
fi

# Exit non-zero if anything was left behind, so the caller does not treat a
# partial collect as a clean one and link a previous run's screenshots.
exit "$skipped"
