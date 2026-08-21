#!/bin/bash
# delete_sdd_work_files.sh — Remove specific scratch files from the shared .sdd-work/ dir.
# Usage: ./delete_sdd_work_files.sh <file1> [<file2> ...]
#
# Takes an explicit list of file paths as arguments. For each path:
#   - Resolves it with realpath.
#   - Refuses to act unless it is a regular file inside ${CLAUDE_PROJECT_DIR}/.sdd-work/.
#   - Removes it.
#
# NEVER accepts directories, globs, or a bare invocation with no arguments.
# The .sdd-work/ directory is SHARED across all SDD commands and is never wiped
# wholesale — only the specific named files passed as arguments are removed.
#
# Rejected paths do not abort the run: every argument is processed, and the
# script exits non-zero at the end if any were refused. Aborting mid-list would
# leave some files deleted and others not, with no way to tell which.

set -euo pipefail

: "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR must be set}"

# Resolve both the project root and the .sdd-work directory itself with realpath
# so the boundary prefix check compares like-for-like with the resolved file
# paths below. Resolving only the root is not enough: if .sdd-work/ is itself a
# symlink, the resolved file path would not share the unresolved prefix and every
# legitimate file would be refused.
PROJECT_ROOT="$(realpath "$CLAUDE_PROJECT_DIR")"
SCRATCH_DIR="${PROJECT_ROOT}/.sdd-work"
if [ -d "$SCRATCH_DIR" ]; then
  SCRATCH_DIR="$(realpath "$SCRATCH_DIR")"
fi

if [ "${#}" -eq 0 ]; then
  echo "Error: at least one file path argument is required" >&2
  exit 1
fi

refused=0

for arg in "$@"; do
  # Resolve to an absolute path. realpath fails on a nonexistent path, so check
  # first. -e follows symlinks, so also accept a dangling symlink via -L,
  # otherwise a broken link in .sdd-work/ could never be cleaned up.
  if [ ! -e "$arg" ] && [ ! -L "$arg" ]; then
    echo "Skipping (does not exist): $arg"
    continue
  fi

  RESOLVED="$(realpath -m "$arg")"

  # Require the path to be inside .sdd-work/ (exact prefix match). Checked before
  # the file-type test so a traversal attempt is always reported as such.
  if [[ "$RESOLVED" != "${SCRATCH_DIR}/"* ]]; then
    echo "Error: refusing to remove path outside .sdd-work/: $RESOLVED" >&2
    refused=1
    continue
  fi

  # Only regular files (and symlinks to them) are accepted — never directories,
  # fifos, sockets or device nodes.
  if [ -d "$RESOLVED" ]; then
    echo "Error: refusing to remove directory: $RESOLVED" >&2
    refused=1
    continue
  fi
  if [ ! -f "$RESOLVED" ] && [ ! -L "$arg" ]; then
    echo "Error: refusing to remove non-regular file: $RESOLVED" >&2
    refused=1
    continue
  fi

  rm -f "$RESOLVED"
  echo "Removed: $RESOLVED"
done

exit "$refused"
