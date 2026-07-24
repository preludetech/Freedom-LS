# SDD Plugin Configuration

The spec-driven-development (sdd) workflow is enabled for this project. Product-specific SDD steps
and dev credentials live in `.claude/fls-dev/` (written by `/fls-dev:init`), not here.

## Worktree Scripts

Paths are relative to the project root. Leave a value blank if this project has no such step.

- Setup script: .claude/fls-dev/scripts/install_dev.sh
- Teardown script: .claude/fls-dev/scripts/dev_db_delete.sh
