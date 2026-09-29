#!/bin/sh
# Rebuilds generated assets a rebase can make stale: dependencies, then the
# compiled Tailwind CSS. Also ensures the fls_dev role and this worktree's
# per-branch databases exist, since a rebase can be the first thing run in a
# freshly created worktree. Run before the test suite so pytest-playwright or
# a browser never sees pre-rebase output.

set -eu

uv sync
npm i
npm run tailwind_build
"$(dirname "$0")/dev_db_init.sh"
