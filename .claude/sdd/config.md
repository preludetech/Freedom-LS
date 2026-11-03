# SDD Plugin Configuration

## Worktree Scripts

- Setup script: .claude/fls-dev/scripts/install_dev.sh
- Teardown script: .claude/fls-dev/scripts/dev_db_delete.sh
- Parallel batches: 3

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

- Comment standard: claude_plugins/django-stack/skills/code-comments/SKILL.md
- Test standard: claude_plugins/fls-dev/skills/testing/SKILL.md

## Documentation Hooks

- App map: ds:app_map
- Upgrade notes: fls-dev:update_upgrade_notes
- Product docs: fls-dev:update_product_docs
- Course-author plugin: fls-dev:update_claude_plugin_fls_content

## QA Hooks

- QA command: sdd:do_qa
- Playwright MCP: mcp__plugin_ds_playwright__
- Screenshot directory: qa-screenshots
- Port finder: .claude/ds/scripts/find_available_port.sh
- Dev server start: uv run --directory <PROJECT_ROOT> python manage.py runserver <PORT>
- Dev server stop: .claude/ds/scripts/kill_runserver.sh <PORT>
- Branch badge: debug-branch-badge
- Diff scoping: claude_plugins/django-stack/resources/qa_diff_scoping.md
- Data helper guide: claude_plugins/fls-dev/resources/qa_data_helper.md
- Screenshot prep: if #djDebugToolbar is visible, click #djHideToolBarButton so the Django debug toolbar collapses to its tab
- Layout regions: {"header": "#interface-main > div:first-of-type", "content": "#interface-main > :not(div:first-of-type)", "sidebar": "dialog.side-panel-dialog"}

## QA Login

- Admin email: demodev@email.com
- Admin password: demodev@email.com  # pragma: allowlist secret
- Base URL: http://127.0.0.1:8000

## QA Dev Data

- Content reset: uv run python manage.py danger_content_delete --yes
- DB drop: .claude/fls-dev/scripts/dev_db_delete.sh
- DB create: .claude/fls-dev/scripts/dev_db_init.sh
- Migrate: uv run python manage.py migrate

## Testing Skills

- ds:testing
- fls-dev:testing
- ds:playwright-tests
- fls-dev:playwright-tests

## PR Hooks

- Fetch PR comments: .claude/ds/scripts/fetch_pr_comments.sh

## Rule Files

- Brand visual system: .claude/skills/brand-guidelines/visual.md
- Brand voice and copy: .claude/skills/brand-guidelines/voice.md
- Panel framework pages: claude_plugins/fls-dev/skills/panel-framework/SKILL.md

## Vocabulary Sources

- claude_plugins/fls-dev/skills/domain-glossary/SKILL.md
- freedom_ls/*/models.py
- docs/product/
- docs/app_structure.md
