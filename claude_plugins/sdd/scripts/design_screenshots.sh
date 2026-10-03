#!/bin/bash
# design_screenshots.sh — Screenshot every screen of a registered design.
# Usage: design_screenshots.sh <spec-dir>
#
# Renders every page at the top level of <spec-dir>/design_source/ (the entry file named in
# <spec-dir>/design.md first) and writes one PNG per screen into <spec-dir>/design_screenshots/:
# a canvas project's artboards, the fixed frames a .dc.html page draws, or the whole page when it
# draws neither. design_screenshots.py says how each is found and named.
#
# Thin wrapper around design_screenshots.py. It exists so callers have a stable path to invoke
# and so the playwright package and Chromium are present without a project-level install.
# <spec-dir> is relative to the caller's working directory.

set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# A no-op when Chromium is already installed.
uv run --with playwright playwright install chromium
exec uv run --with playwright python "${SCRIPT_DIR}/design_screenshots.py" "$@"
