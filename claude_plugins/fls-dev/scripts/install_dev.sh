#!/bin/sh
# Base FLS development setup — shared across all FLS implementations.
# Project-specific steps go in the wrapper script at the project root.

# Ensure all submodules are present and up to date (concrete implementations
# pull FLS and the plugin in as submodules).
git submodule update --init --recursive

# Every worktree shares one pre-commit hook. Keep it a shim that runs pre-commit from whichever
# worktree is committing, so a plain `git commit` runs the hooks everywhere.
"$(dirname "$0")/../../django-stack/scripts/install_pre_commit_hook.sh"

"$(dirname "$0")/rebuild_after_rebase.sh"

# Apply migrations
uv run manage.py migrate
