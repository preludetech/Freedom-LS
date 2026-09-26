#!/bin/sh
# Rebuilds generated assets a rebase can make stale: dependencies, then the
# compiled Tailwind CSS. Run before the test suite so pytest-playwright or a
# browser never sees pre-rebase output.

set -eu

uv sync
npm i
npm run tailwind_build
