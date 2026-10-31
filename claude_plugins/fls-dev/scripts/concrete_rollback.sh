#!/bin/bash
# concrete_rollback.sh — Return a concrete project to its last good commit after a failed cell.
# Usage: concrete_rollback.sh <project-root> <last-good-sha>
#
# Run from the FLS main worktree by /fls-dev:update_concrete_projects. It is the Rollback recipe
# of claude_plugins/fls-dev/resources/concrete_spec_integration.md as one allow-listed call:
#   1. reset --hard to <last-good-sha> and restore the submodule to its recorded pointer;
#   2. delete every untracked file, then each directory that deletion left empty;
#   3. uv sync, and npm install when package.json or package-lock.json changed.
#
# Every untracked file is the failed integration's own, because the command only starts a cell
# on a clean tree. That precondition is what makes step 2 safe.
#
# Refuses unless <project-root> is listed under ## Concrete Projects in the FLS config and
# <last-good-sha> is a hex SHA that is HEAD or an ancestor of HEAD. Empty-directory removal runs
# on paths relative to the project root, so it never climbs above the root.

set -euo pipefail

# shellcheck source=concrete_projects.sh disable=SC1091 # resolved from the script's own directory at run time
source "$(dirname "$(realpath "$0")")/concrete_projects.sh"

if [ "${#}" -ne 2 ]; then
  echo "Usage: concrete_rollback.sh <project-root> <last-good-sha>" >&2
  exit 1
fi

project_root="$(require_listed_project "$1")"
last_good="$2"

if [[ ! "$last_good" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "Error: last good must be a hex SHA: $last_good" >&2
  exit 1
fi

if [ "$(git -C "$project_root" rev-parse --show-toplevel 2> /dev/null)" != "$project_root" ]; then
  echo "Error: not a git checkout: $project_root" >&2
  exit 1
fi

if ! git -C "$project_root" merge-base --is-ancestor "$last_good" HEAD 2> /dev/null; then
  echo "Error: $last_good is not HEAD or an ancestor of HEAD" >&2
  exit 1
fi

npm_changed=0
if ! git -C "$project_root" diff --quiet "$last_good" -- package.json package-lock.json; then
  npm_changed=1
fi

git -C "$project_root" reset --quiet --hard "$last_good"
git -C "$project_root" submodule update --init submodules/Freedom-LS

untracked=()
while IFS= read -r -d '' entry; do
  if [[ "$entry" == '?? '* ]]; then
    untracked+=("${entry:3}")
  fi
done < <(git -C "$project_root" status --porcelain -z --untracked-files=all)

if [ "${#untracked[@]}" -gt 0 ]; then
  git -C "$project_root" clean -f -- "${untracked[@]}"

  # Deepest first, so a parent is only tried once its children are gone.
  while IFS= read -r dir; do
    if [ -n "$dir" ] && [ "$dir" != "." ] && [ -d "${project_root}/${dir}" ]; then
      (cd "$project_root" && rmdir -p --ignore-fail-on-non-empty -- "$dir")
    fi
  done < <(for path in "${untracked[@]}"; do dirname -- "$path"; done | sort -u -r)
fi

uv sync --directory "$project_root"
if [ "$npm_changed" -eq 1 ]; then
  npm --prefix "$project_root" install
else
  echo "Skipping npm install: package.json and package-lock.json unchanged"
fi

echo "Rolled back to ${last_good}"
