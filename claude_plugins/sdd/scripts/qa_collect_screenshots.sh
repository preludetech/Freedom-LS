#!/bin/bash
# qa_collect_screenshots.sh — Move screenshots from the shared output dir into the spec dir.
# Usage: qa_collect_screenshots.sh <spec-dir> <source-dir>
#
# Takes the QA run's spec directory as $1 and the screenshot source directory as $2,
# relative to the project root. Both must resolve to a path strictly inside the project.
# Moves every file from <source-dir> into <spec-dir>/screenshots/, then removes the
# now-empty source directory so it does not accumulate across runs.

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

if [ -z "${1:-}" ]; then
  echo "Error: spec-dir argument is required" >&2
  exit 1
fi

if [ -z "${2:-}" ]; then
  echo "Error: source-dir argument is required" >&2
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

# Both paths are checked against the project root (security: the script is
# allow-listed with arbitrary arguments, and the source directory can come from
# a project config file, so an unvalidated path such as ../../somewhere could
# move files out of or into places outside the project).
inside_project() {
  [[ "$1" == "${PROJECT_ROOT}/"* ]]
}

if ! inside_project "$SPEC_DIR"; then
  echo "Error: spec-dir must be inside CLAUDE_PROJECT_DIR" >&2
  exit 1
fi

# realpath -m resolves a source directory that does not exist yet, so a missing
# one is reported below as "nothing to move" rather than as an error.
# An absolute source-dir is refused outright: joining it to the root would turn
# /tmp into <root>//tmp and pass the prefix test.
if [[ "$2" == /* ]]; then
  echo "Error: source-dir must be relative to CLAUDE_PROJECT_DIR" >&2
  exit 1
fi
SRC_DIR="$(realpath -m "${PROJECT_ROOT}/$2")"
if ! inside_project "$SRC_DIR"; then
  echo "Error: source-dir must be inside CLAUDE_PROJECT_DIR" >&2
  exit 1
fi

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
