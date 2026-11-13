#!/bin/bash
# qa_cleanup.sh — Remove the previous QA run's artifacts from a spec directory.
# Usage: ./qa_cleanup.sh <spec-dir>
#
# Takes the QA run's spec directory as $1, relative to the project root, and
# removes the qa_report.md and screenshots/ directory it holds (with its
# screenshots/<subfolder>/ directories), so the next run
# starts clean.

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

# Resolve the project root with realpath so the boundary check below compares
# like-for-like with the realpath-resolved SPEC_DIR. Without this, a symlinked
# component in CLAUDE_PROJECT_DIR would make the prefix check falsely reject a
# legitimate in-project spec dir.
PROJECT_ROOT="$(realpath "$CLAUDE_PROJECT_DIR")"

# A relative spec-dir is joined to the project root, not the caller's working
# directory, so the script behaves the same from any cwd. An absolute one is
# taken as given and still has to pass the boundary check below.
if [[ "$1" == /* ]]; then
  SPEC_DIR="$1"
else
  SPEC_DIR="${PROJECT_ROOT}/$1"
fi

if [ ! -d "$SPEC_DIR" ]; then
  echo "Error: spec-dir is not a directory: $SPEC_DIR" >&2
  exit 1
fi

SPEC_DIR="$(realpath "$SPEC_DIR")"

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

# Remove a screenshots directory file-by-file, then rmdir it. The recursive
# force-delete form is blocked by the security-guard hook by design, and a
# per-file loop keeps the blast radius visible. Subfolders (screenshots/fixed/)
# go one level deep, through the same loop; anything deeper is left in place.
remove_shots_dir() {
  local dir="$1" depth="$2" f
  shopt -s nullglob dotglob
  for f in "$dir"/*; do
    if [ -f "$f" ]; then
      rm -f "$f"
    elif [ -d "$f" ] && [ ! -L "$f" ] && [ "$depth" -eq 0 ]; then
      remove_shots_dir "$f" 1
    else
      echo "Warning: leaving entry in place: $f" >&2
    fi
  done
  shopt -u nullglob dotglob
  if rmdir "$dir" 2>/dev/null; then
    echo "Removed ${dir}/"
  else
    echo "Warning: ${dir}/ not empty after cleanup; left in place" >&2
  fi
}

SHOTS_DIR="${SPEC_DIR}/screenshots"
if [ -d "$SHOTS_DIR" ]; then
  remove_shots_dir "$SHOTS_DIR" 0
fi
