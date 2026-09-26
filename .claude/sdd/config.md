# SDD Plugin Configuration

The spec-driven-development (sdd) workflow is enabled for this project. Product-specific SDD steps
and dev credentials live in `.claude/fls-dev/` (written by `/fls-dev:init`), not here.

## Worktree Scripts

Paths are relative to the project root. Leave a value blank if this project has no such step.

- Setup script: .claude/fls-dev/scripts/install_dev.sh
- Teardown script: .claude/fls-dev/scripts/dev_db_delete.sh

## Rebase Hooks

Followed by the pre-step rebase before every feature-branch SDD step. Each value is a command
or helper file that is read and followed, not a script. Leave a value blank if this project has
no such step.

- Rebase command: claude_plugins/django-stack/commands/rebase_main.md
- Front-end check:

## Vocabulary Sources

Where this project's domain vocabulary is defined, most authoritative first.

- `.claude/skills/domain-glossary/SKILL.md` — the index over every domain noun, where each one is
  defined, and the words that are already taken.
- `freedom_ls/*/models.py` — the canonical nouns; the vocabulary of last resort.
- `docs/product/` — concept-level prose.
- `docs/app_structure.md` — the canonical app names.
