#!/bin/bash
# concrete_projects.sh — Shared helpers for the concrete-project wrapper scripts. Sourced, never run.
#
# require_listed_project <path> prints the realpath of <path> when it is a bullet under
# `## Concrete Projects` in the FLS config, and exits non-zero otherwise. The section in
# .claude/fls-dev/config.local.md replaces the one in .claude/fls-dev/config.md when both hold
# it, the same rule /fls-dev:update_concrete_projects applies when it reads the project list.

: "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR must be set}"

# Prints the bullets of the `## Concrete Projects` section of $1, one per line, and returns
# non-zero when the file or the section is absent.
concrete_project_bullets() {
  local file="$1"
  [ -f "$file" ] || return 1
  grep -q '^## Concrete Projects[[:space:]]*$' "$file" || return 1
  awk '
    /^## / { in_section = ($0 ~ /^## Concrete Projects[[:space:]]*$/); next }
    in_section && /^- \// { sub(/^- /, ""); sub(/[[:space:]]+$/, ""); print }
  ' "$file"
}

require_listed_project() {
  local candidate="$1"
  local config_dir="${CLAUDE_PROJECT_DIR}/.claude/fls-dev"
  local bullets resolved listed

  if [[ "$candidate" != /* ]]; then
    echo "Error: project root must be an absolute path: $candidate" >&2
    exit 1
  fi
  if [ ! -d "$candidate" ]; then
    echo "Error: project root does not exist: $candidate" >&2
    exit 1
  fi
  resolved="$(realpath "$candidate")"

  if ! bullets="$(concrete_project_bullets "${config_dir}/config.local.md")"; then
    bullets="$(concrete_project_bullets "${config_dir}/config.md" || true)"
  fi

  while IFS= read -r listed; do
    [ -n "$listed" ] || continue
    [ -d "$listed" ] || continue
    if [ "$(realpath "$listed")" = "$resolved" ]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done <<< "$bullets"

  echo "Error: not a listed concrete project (see ## Concrete Projects in .claude/fls-dev/config.local.md): $candidate" >&2
  exit 1
}
