# Audit: Current .claude/ Directory for Plugin Extraction

Date: 2026-03-31
Scope: Full inventory of .claude/ directory

---

## Summary

The .claude/ directory contains 50+ files across 8 top-level categories. The majority of content is FreedomLS-generic and suitable for plugin extraction. A small number of files contain hardcoded paths or project-local overrides that must stay in .claude/ or be templated.

---

## File Inventory and Classification

### 1. Settings Files

#### settings.json -- Plugin candidate

Contains:
- Permissions (allow): Playwright MCP tools, Bash patterns for git/pytest/uv/npm/tailwind, Skill invocations, sleep/curl patterns
- Permissions (deny): dotenv files, config/settings_prod.py, git commit --no-verify, git push --force, PEM/key files
- Hooks (PostToolUse): ruff_fix.sh on Edit/Write, post-edit-bandit.sh on Edit/Write
- Hooks (PreToolUse): ruff+mypy+pytest before git commit, security-guard.sh on Bash/Write/Edit
- enabledPlugins: empty object {}

Notes:
- The config/settings_prod.py deny rule references a FreedomLS-specific path. This should either be generalized or remain as a project override.
- The pre-commit hook command (uv run ruff check . && uv run mypy . && uv run pytest --tb=short -q) is FreedomLS-generic (uses uv, ruff, mypy, pytest -- all part of the stack).
- Potential conflict: When a plugin provides settings.json and the project also has one, Claude Code merges them. The allow/deny lists merge additively. Hooks from both sources run. This should work without conflict as long as we don't duplicate hook entries.

#### settings.local.json -- Project-local

Contains:
- Additional allow rules: WebSearch, WebFetch for specific domains (imsglobal.org, brevo.com, svix.com, etc.), broader uv run:* allow, a one-off python3 command
- disabledMcpjsonServers: ["playwright"] -- disables Playwright MCP locally

Notes: This is explicitly a local override file. It stays in .claude/ and is user-specific. Not part of the plugin.

---

### 2. MCP Configuration

#### mcp.json -- Plugin candidate

Contains a single MCP server definition: Playwright via npx @playwright/mcp.

Notes: Generic to FreedomLS -- any project using FreedomLS would want Playwright MCP for QA workflows. Good plugin candidate.

---

### 3. Hook Scripts

#### hooks/ruff_fix.sh -- Plugin candidate

PostToolUse hook that runs uv run ruff check --fix and uv run ruff format on edited Python files. Uses $CLAUDE_FILE_PATHS env var.

Notes: Generic Python/Django linting. Part of the FreedomLS development stack.

#### hooks/post-edit-bandit.sh -- Plugin candidate

PostToolUse hook that runs uv run bandit -q -ll on edited Python files. Parses tool input JSON via jq.

Notes: Generic security scanning. Part of the FreedomLS development stack.

#### hooks/security-guard.sh -- Plugin candidate

PreToolUse hook with two functions:
1. Edit/Write guard: Blocks dangerous code patterns (raw SQL, unsafe marking, code execution functions, unsafe deserialization, request dict unpacking). Also blocks dotenv file modifications and existing migration file edits.
2. Bash guard: Blocks rm -rf, dotenv access, SSH key access, PEM/key access.

Notes: Entirely generic security policy for Django projects. Strong plugin candidate.

The full list of blocked patterns is in the sh file itself (see BLOCKED_PATTERNS array). Notably, this hook will also block writing documentation that mentions these patterns literally -- this is a known limitation.

---

### 4. Skills (14 SKILL.md files + supporting files)

#### Plugin candidates (core FreedomLS skills):

| Skill | Path | Notes |
|-------|------|-------|
| testing | skills/testing/SKILL.md | References @.claude/docs/testing.md and @.claude/docs/factory_boy.md. Generic to FreedomLS testing conventions. |
| htmx | skills/htmx/SKILL.md | HTMX patterns, view conventions, template patterns. Self-contained, no external refs except _base.html. |
| multi-tenant | skills/multi-tenant/SKILL.md | References @.claude/docs/multi_tenant.md. Core FreedomLS architecture. |
| template | skills/template/SKILL.md | References @.claude/docs/templates_and_cotton.md. Core template conventions. |
| frontend-styling | skills/frontend-styling/SKILL.md | References @.claude/docs/frontend_styling.md. Thin wrapper. |
| icon-usage | skills/icon-usage/SKILL.md | Self-contained. References freedom_ls/base/icons.py and freedom_ls/base/templates/cotton/icon.html. |
| admin-interface | skills/admin-interface/SKILL.md | References @.claude/docs/admin_interface.md. Thin wrapper. |
| brand-guidelines | skills/brand-guidelines/SKILL.md | Comprehensive brand identity doc. Self-contained. FreedomLS-specific brand. |
| markdown-content | skills/markdown-content/SKILL.md | References @.claude/docs/markdown_content.md. Core content system. |
| alpine-js | skills/alpine-js/SKILL.md | Self-contained, detailed Alpine.js CSP build conventions. References freedom_ls/base/static/base/js/alpine-components.js. |
| playwright-tests | skills/playwright-tests/SKILL.md | References @.claude/docs/playwright-testing.md and @.claude/docs/testing.md. |
| request-code-review | skills/request-code-review/SKILL.md + code-reviewer.md | Generic review workflow. Has a BROKEN reference (see below). |
| use-playwright | skills/use-playwright/SKILL.md | Interactive Playwright MCP usage. Contains hardcoded base URL http://127.0.0.1:8000 and hardcoded credentials demodev@email.com. These are dev defaults. |

#### Needs investigation:

| Skill | Path | Notes |
|-------|------|-------|
| git-worktree-setup | skills/git-worktree-setup/SKILL.md | Contains hardcoded absolute paths: /home/sheena/workspace/lms/freedom-ls-worktrees/. This is entirely project-local in its current form. The concept is generic (bare repo + worktrees), but the paths are not. Needs to be either templated or kept project-local. |

#### Cleanup needed (not for plugin):

| File | Notes |
|------|-------|
| skills/brand-guidelines/oldSKILL.md | Stale file. Previous version of brand guidelines. Uses Lucide Icons (project now uses Heroicons). Should be deleted, not included in plugin. |
| skills/brand-guidelines/todo | Contains a note about iconography using Lucide Icons -- outdated. Should be deleted. |

---

### 5. Commands (13 command files)

#### Plugin candidates (generic FreedomLS workflow commands):

| Command | Path | Notes |
|---------|------|-------|
| commit | commands/commit.md | Generic commit workflow using uv run pytest + uv run git commit. |
| tdd_implement | commands/tdd_implement.md | References testing skill. Generic TDD workflow. |
| do_todos | commands/do_todos.md | Searches for @claude comments. Generic. |
| security-review | commands/security-review.md | Uses bandit, pip-audit, detect-secrets. Generic security workflow. |
| catchup | commands/catchup.md | Generic git context gathering. |
| make_github_issue | commands/make_github_issue.md | Very minimal (1 line). Generic. |
| placeholder_page | commands/placeholder_page.md | References template skill. Generic Django page scaffolding. |
| threat-model | commands/threat-model.md | OWASP-based threat modeling. Generic. |
| address_pr_review | commands/address_pr_review.md | References ./fetch_pr_comments.sh. Generic PR workflow. |

#### Plugin candidates (spec-driven development workflow):

| Command | Path | Notes |
|---------|------|-------|
| spec_driven_dev/README.md | | Workflow overview document. |
| spec_driven_dev/spec_from_idea.md | | Creates spec from idea file. Generic. |
| spec_driven_dev/spec_review.md | | Reviews spec against project norms. References @.claude/docs/. |
| spec_driven_dev/plan_from_spec.md | | Creates implementation plan from spec. References ./find_available_port.sh. |
| spec_driven_dev/implement_plan.md | | Executes plans with sub-agents and code review. |
| spec_driven_dev/do_qa.md | | Playwright MCP QA execution. Contains hardcoded credentials demodev@email.com. References ./find_available_port.sh. |
| spec_driven_dev/improve_idea.md | | Research-based idea refinement. |
| spec_driven_dev/start_worktree.md | | Creates git worktree for spec. References spec_dd/ directory structure. |
| spec_driven_dev/finish_worktree.md | | Merges worktree back. References spec_dd/2. in progress/ and ./dev_db_delete.sh. |

Notes on spec_driven_dev commands:
- do_qa.md has hardcoded demodev@email.com credentials. These are FreedomLS dev defaults but could be considered project-specific configuration.
- start_worktree.md and finish_worktree.md reference the spec_dd/ directory convention. This is a FreedomLS development workflow convention.
- plan_from_spec.md and do_qa.md reference ./find_available_port.sh -- a project script that needs to exist.

---

### 6. Documentation Files (9 docs)

All doc files are plugin candidates -- they document FreedomLS conventions:

| Doc | Path | Notes |
|-----|------|-------|
| testing.md | docs/testing.md | References @.claude/docs/factory_boy.md. Comprehensive testing guide. |
| factory_boy.md | docs/factory_boy.md | Factory patterns. References freedom_ls/ paths. |
| templates_and_cotton.md | docs/templates_and_cotton.md | Template conventions. References freedom_ls/ paths. |
| admin_interface.md | docs/admin_interface.md | Django Unfold + SiteAwareModelAdmin patterns. |
| multi_tenant.md | docs/multi_tenant.md | Site isolation architecture. References freedom_ls/site_aware_models/. |
| frontend_styling.md | docs/frontend_styling.md | TailwindCSS v4 conventions. References tailwind.components.css. |
| markdown_content.md | docs/markdown_content.md | Markdown rendering pipeline. References freedom_ls/content_engine/. |
| email_templates.md | docs/email_templates.md | Email system with allauth integration. References freedom_ls/accounts/. |
| playwright-testing.md | docs/playwright-testing.md | Playwright E2E patterns. |

---

### 7. Agents (2 agent definitions + 1 memory directory)

#### agents/code-reviewer.md -- Plugin candidate

Comprehensive code review agent. Tools: Glob, Grep, Read, WebFetch, WebSearch. Model: opus.

Notes:
- References @.claude/agent-memory/code-reviewer/ for persistent memory.
- The agent itself is generic to FreedomLS review criteria.

#### agents/qa-data-helper.md -- Plugin candidate (with caveats)

QA data creation agent using factory_boy. Tools: Glob, Grep, Read, WebFetch, WebSearch, Bash. Model: opus.

Notes:
- Contains hardcoded absolute paths:
  - /home/sheena/workspace/lms/freedom-ls-worktrees/main/.claude/agent-memory/qa-data-factory/
  - /home/sheena/.claude/projects/... (session transcript path)
- References @.claude/docs/factory_boy.md (uses @ relative path -- good).
- References qa_helpers app and FreedomLS-specific factory patterns.
- The hardcoded paths in the "Searching past context" section need to be made relative or templated.

#### agent-memory/code-reviewer/MEMORY.md -- Project-local

This is accumulated memory from the code-reviewer agent. It contains project-specific knowledge about:
- Cohort course progress panel implementation details
- Student model refactoring history
- Role-based permissions system details
- Factory boy implementation specifics

This file should NOT be in the plugin. It is runtime state accumulated from this specific project. However, the agent-memory directory structure should be created by the plugin.

---

### 8. CLAUDE.md (Project Root)

#### CLAUDE.md -- Dual purpose (needs splitting)

The root CLAUDE.md contains:
1. FreedomLS-generic content: Stack description, conventions, app structure, coding standards -- all plugin candidates
2. Project-local content: Commands section (uv add, uv run pytest, etc.) -- these are generic to any FreedomLS project but might vary by installation

Recommendation: The plugin should provide its own CLAUDE.md content. The project CLAUDE.md would then extend/override with project-specific details.

---

## Cross-Cutting Concerns

### @ Path References

Many files use @.claude/docs/ and @.claude/skills/ relative paths. These are Claude Code built-in path resolution and will work correctly whether the files come from a plugin or from .claude/ directly. No changes needed for @ references as long as the plugin installs files in the expected locations.

Files using @ references:
- skills/testing/SKILL.md -> @.claude/docs/testing.md, @.claude/docs/factory_boy.md
- skills/multi-tenant/SKILL.md -> @.claude/docs/multi_tenant.md
- skills/template/SKILL.md -> @.claude/docs/templates_and_cotton.md
- skills/frontend-styling/SKILL.md -> @.claude/docs/frontend_styling.md
- skills/admin-interface/SKILL.md -> @.claude/docs/admin_interface.md
- skills/markdown-content/SKILL.md -> @.claude/docs/markdown_content.md
- skills/playwright-tests/SKILL.md -> @.claude/docs/playwright-testing.md, @.claude/docs/testing.md
- skills/request-code-review/SKILL.md -> @.claude/skills/requesting-code-review/code-reviewer.md (BROKEN PATH)
- commands/spec_driven_dev/spec_review.md -> @.claude/docs/
- docs/testing.md -> @.claude/docs/factory_boy.md
- agents/qa-data-helper.md -> @.claude/docs/factory_boy.md
- agents/code-reviewer.md -> @.claude/agent-memory/code-reviewer/

### Hardcoded Absolute Paths (Must Fix Before Plugin Extraction)

| File | Hardcoded Path | Fix Needed |
|------|---------------|------------|
| skills/git-worktree-setup/SKILL.md | /home/sheena/workspace/lms/freedom-ls-worktrees/ (2 occurrences) | Make relative or template |
| agents/qa-data-helper.md | /home/sheena/workspace/lms/freedom-ls-worktrees/main/.claude/agent-memory/qa-data-factory/ | Make relative |
| agents/qa-data-helper.md | /home/sheena/.claude/projects/... (session transcript path) | Make relative or remove |

### Hardcoded Credentials

| File | Credential | Risk |
|------|-----------|-----|
| skills/use-playwright/SKILL.md | demodev@email.com (email + password) | Dev-only, low risk. These are FreedomLS demo credentials. |
| commands/spec_driven_dev/do_qa.md | demodev@email.com | Same dev credentials. |

### Project-Specific Script References

Commands reference these project scripts that must exist:
- ./fetch_pr_comments.sh (used by address_pr_review.md)
- ./find_available_port.sh (used by plan_from_spec.md, do_qa.md)
- ./install_dev.sh (referenced in git-worktree-setup/SKILL.md)
- ./dev_db_init.sh (referenced in git-worktree-setup/SKILL.md)
- ./dev_db_delete.sh (referenced in finish_worktree.md, git-worktree-setup/SKILL.md)

These scripts are part of the FreedomLS project itself, not the .claude/ config. The plugin commands can reference them safely since they will exist in any FreedomLS checkout.

### Broken Reference

skills/request-code-review/SKILL.md line 103 references @.claude/skills/requesting-code-review/code-reviewer.md but the actual path is @.claude/skills/request-code-review/code-reviewer.md (uses "requesting" instead of "request"). This should be fixed regardless of plugin extraction.

---

## Classification Summary

### Plugin Candidates (42 files)

- settings.json (base permissions, hooks, deny rules)
- mcp.json
- hooks/ruff_fix.sh
- hooks/post-edit-bandit.sh
- hooks/security-guard.sh
- All 9 docs/*.md files
- 13 of 14 skills/*/SKILL.md files (all except git-worktree-setup)
- skills/request-code-review/code-reviewer.md
- All 13 commands/*.md files (including spec_driven_dev/)
- agents/code-reviewer.md
- agents/qa-data-helper.md (after fixing hardcoded paths)
- CLAUDE.md (the generic conventions portion)

### Project-Local (3 files)

- settings.local.json -- user-specific overrides, not committed
- agent-memory/code-reviewer/MEMORY.md -- runtime state from this project
- skills/brand-guidelines/oldSKILL.md -- stale, should be deleted

### Needs Investigation (3 files)

- skills/git-worktree-setup/SKILL.md -- concept is generic, but full of hardcoded paths. Could be templated or could stay project-local since worktree layout varies.
- skills/brand-guidelines/todo -- stale file, references outdated icon library (Lucide vs Heroicons). Likely should be deleted.
- CLAUDE.md (root) -- needs a strategy for splitting plugin-provided conventions from project-specific overrides

---

## Potential Conflicts Between Plugin and Project

1. settings.json merge behavior: Plugin and project both provide settings.json. Allow/deny lists merge additively (safe). Hooks from both run (could duplicate if same hook appears in both). The enabledPlugins key in the project settings.json is where the plugin gets activated.

2. CLAUDE.md stacking: Claude Code loads CLAUDE.md from multiple sources. The plugin can provide foundational conventions, and the project can override or extend. No conflict as long as they don't contradict.

3. Hook duplication risk: If both plugin and project define the same PostToolUse/PreToolUse hooks, they may run twice. The plugin should own the hook definitions, and the project should not duplicate them.

4. Skill name collisions: If plugin provides a skill named "testing" and project also has one, the behavior is undefined. The plugin should own all FreedomLS skills, and the project should not override them unless intentional.
