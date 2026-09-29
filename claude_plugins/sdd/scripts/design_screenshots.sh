#!/bin/bash
# design_screenshots.sh — Screenshot every artboard of a registered design.
# Usage: design_screenshots.sh <spec-dir>
#
# Renders the entry file named in <spec-dir>/design.md from <spec-dir>/design_source/ and writes
# one PNG per [data-artboard] element into <spec-dir>/design_screenshots/.
#
# Thin wrapper around design_screenshots.py. It exists so callers have a stable path to invoke
# and so the playwright package and Chromium are present without a project-level install.
# <spec-dir> is relative to the caller's working directory.

set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# A no-op when Chromium is already installed.
uv run --with playwright playwright install chromium
exec uv run --with playwright python "${SCRIPT_DIR}/design_screenshots.py" "$@"
