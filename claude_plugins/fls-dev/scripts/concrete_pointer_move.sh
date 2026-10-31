#!/bin/bash
# concrete_pointer_move.sh — Move a concrete project's FLS submodule pointer to a commit on FLS origin/main.
# Usage: concrete_pointer_move.sh <project-root> <sha|origin/main>
#
# Run from the FLS main worktree by /fls-dev:update_concrete_projects, in place of a bare
# `git -C <p>/submodules/Freedom-LS checkout <sha>`, which would prompt on every cell.
#
# Refuses unless:
#   - <project-root> is listed under ## Concrete Projects in the FLS config;
#   - <project-root>/submodules/Freedom-LS is a git checkout;
#   - the target is a hex SHA (7 to 40 characters) or the literal origin/main, so no option or
#     other ref can reach git;
#   - after fetching origin main, the target is an ancestor of origin/main.
#
# Only the submodule checkout moves. Staging and committing the pointer stay with the caller.

set -euo pipefail

# shellcheck source=concrete_projects.sh disable=SC1091 # resolved from the script's own directory at run time
source "$(dirname "$(realpath "$0")")/concrete_projects.sh"

if [ "${#}" -ne 2 ]; then
  echo "Usage: concrete_pointer_move.sh <project-root> <sha|origin/main>" >&2
  exit 1
fi

project_root="$(require_listed_project "$1")"
target="$2"
submodule="${project_root}/submodules/Freedom-LS"

if [[ ! "$target" =~ ^[0-9a-f]{7,40}$ ]] && [ "$target" != "origin/main" ]; then
  echo "Error: target must be a hex SHA or origin/main: $target" >&2
  exit 1
fi

if [ ! -d "$submodule" ] || ! git -C "$submodule" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  echo "Error: not a git checkout: $submodule" >&2
  exit 1
fi

git -C "$submodule" fetch --quiet origin main

if ! git -C "$submodule" merge-base --is-ancestor "$target" origin/main 2> /dev/null; then
  echo "Error: $target is not on FLS origin/main" >&2
  exit 1
fi

old_sha="$(git -C "$submodule" rev-parse HEAD)"
git -C "$submodule" checkout --quiet "$target"
new_sha="$(git -C "$submodule" rev-parse HEAD)"

echo "submodules/Freedom-LS: ${old_sha} -> ${new_sha}"
