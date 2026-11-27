#!/bin/sh
# Sourced, not executed: the export below has to reach the caller's later
# `uv run` calls, which would otherwise re-sync and replace the link.
set -eu

PANEL_FRAMEWORK_REPO="${PANEL_FRAMEWORK_REPO:-/home/sheena/workspace/software_factory/django-panel-framework.git}"
panel_framework_dir="${PANEL_FRAMEWORK_DIR:-$PANEL_FRAMEWORK_REPO/$(git branch --show-current)}"

if [ -f "$panel_framework_dir/pyproject.toml" ]; then
    uv pip install --no-deps -e "$panel_framework_dir"
    export UV_NO_SYNC=1
else
    echo "No panel framework worktree at $panel_framework_dir: the locked copy stays in use."
fi
# No `exit`: it would end the script that sourced this one.
