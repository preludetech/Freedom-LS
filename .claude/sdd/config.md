# SDD Plugin Configuration

## Worktree Scripts

- Setup script: .claude/fls-dev/scripts/install_dev.sh
- Teardown script: .claude/fls-dev/scripts/dev_db_delete.sh

## Rebase Hooks

- Rebase command: claude_plugins/django-stack/commands/rebase_main.md
- Front-end check: claude_plugins/fls-dev/commands/protected/frontend_check.md

## Design Hooks

- Design check: claude_plugins/fls-dev/commands/protected/design_check.md

## Test Hooks

- Test tiers: claude_plugins/django-stack/resources/test_tiers.md

## Vocabulary Sources

- .claude/skills/domain-glossary/SKILL.md
- freedom_ls/*/models.py
- docs/product/
- docs/app_structure.md
