#!/bin/sh
# Base FLS development setup — shared across all FLS implementations.
# Project-specific steps go in the wrapper script at the project root.

# Ensure all submodules are present and up to date (concrete implementations
# pull FLS and the plugin in as submodules).
git submodule update --init --recursive

"$(dirname "$0")/rebuild_after_rebase.sh"

# Set up per-branch database
"$(dirname "$0")/dev_db_init.sh"

# Apply migrations
uv run manage.py migrate
