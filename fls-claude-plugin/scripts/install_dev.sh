#!/bin/sh
# Base FLS development setup — shared across all FLS implementations.
# Project-specific steps go in the wrapper script at the project root.

uv sync
npm i
npm run tailwind_build

# Set up per-branch database
./dev_db_init.sh

# Apply migrations
uv run manage.py migrate
