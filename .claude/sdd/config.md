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

## Plan Review Hooks

- Structure: claude_plugins/fls-dev/resources/plan_review_structure.md
- FLS threats: claude_plugins/fls-dev/resources/plan_review_fls_threats.md

## Review Hooks

- Comment standard: .claude/skills/code-comments/SKILL.md
- Test standard: claude_plugins/fls-dev/skills/testing/SKILL.md

## Documentation Hooks

- App map: claude_plugins/django-stack/commands/app_map.md
- Upgrade notes: claude_plugins/fls-dev/commands/update_upgrade_notes.md
- Product docs: claude_plugins/fls-dev/commands/update_product_docs.md
- Course-author plugin: claude_plugins/fls-dev/commands/update_claude_plugin_fls_content.md

## Vocabulary Sources

- .claude/skills/domain-glossary/SKILL.md
- freedom_ls/*/models.py
- docs/product/
- docs/app_structure.md
