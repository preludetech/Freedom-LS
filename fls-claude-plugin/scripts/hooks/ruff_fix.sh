#!/bin/bash
# PostToolUse hook: run ruff on edited Python files only
py_files=""
for f in $CLAUDE_FILE_PATHS; do
  if [[ "$f" == *.py ]]; then
    py_files="$py_files $f"
  fi
done

if [ -n "$py_files" ]; then
  uv run ruff check --fix "$py_files" && uv run ruff format "$py_files"
fi
