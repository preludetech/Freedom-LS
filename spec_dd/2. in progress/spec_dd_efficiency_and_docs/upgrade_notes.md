---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: spec_dd_efficiency_and_docs

This change touches only the Claude Code plugins under `claude_plugins/` (`sdd`, `django-stack`,
`fls-dev`) and their per-project configuration. No Django code, settings, models, templates or
packages change. A project that does not use these plugins has nothing to do.

## Breaking changes

- The `django-stack` script `claude_plugins/django-stack/scripts/fetch_pr_comments.sh` and its
  wrapper template are gone, and `sdd` no longer reads a `## PR Hooks` section. A project whose
  `.claude/ds/scripts/fetch_pr_comments.sh` wrapper was created by `ds:init` now has a wrapper
  pointing at a script that no longer exists.

## Manual steps

For projects that use the `sdd` and `django-stack` plugins:

- Delete `.claude/ds/scripts/fetch_pr_comments.sh`, and remove its three allow entries from
  `.claude/settings.json` (`Bash(.claude/ds/scripts/fetch_pr_comments.sh:*)`, and the `bash ` and
  `./` forms of it).
- Delete the `## PR Hooks` section (its `Fetch PR comments` key) from `.claude/sdd/config.md`.
  Nothing reads it any more.
- Optionally add `- Flaky test guide: <path>` under `## Test Hooks` in `.claude/sdd/config.md`.
  `/sdd:finish_worktree` hands that file to the sub-agent that fixes an order-dependent or flaky
  test. Blank is valid: the sub-agent then works without a guide.
- Re-run `/sdd:init` (or add the entries by hand) so `.claude/settings.json` allows
  `Bash(python3 <PLUGINS_ROOT>/claude_plugins/sdd/scripts/<name>.py:*)` for
  `measure_prompt_size.py`, `full_run_record.py` and `check_diagrams.py`, with no `./` prefix
  when `PLUGINS_ROOT` is `.`. Without them each call to these scripts prompts, and a
  non-interactive agent returns `blocked`.
