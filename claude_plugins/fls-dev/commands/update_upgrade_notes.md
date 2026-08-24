---
description: Author the structured upgrade_notes.md for downstream FLS projects
allowed-tools: Read, Write, Glob, Edit, Bash, Agent
---

Author `upgrade_notes.md` for the current feature, so downstream projects that extend FLS know what they need to do after pulling the change.

This command runs at **depth 0**. It reads the spec, plan, and actual git diff to produce a single structured artifact. No fan-out is needed for a single output file — keep it lean.

## upgrade_notes.md schema

Every run must produce a file with this exact shape. The YAML frontmatter carries machine-readable flags that `update_fls` can parse reliably; the markdown body carries human-readable prose.

```markdown
---
requires_migrations: false
requires_template_review: false
changed_template_paths: []          # populated when requires_template_review is true
requires_settings_change: false
changed_settings: []                # keys/settings when requires_settings_change is true
                                    # when populated, use the block-sequence form so each
                                    # entry can be annotated hard vs optional:
                                    #   changed_settings:
                                    #     - COURSE_ACCESS_BACKEND  # hard: enforced at boot
                                    #     - REPORT_PAGE_SIZE       # optional
requires_package_upgrade: false
changed_packages: []                # package==version entries when true
requires_npm_install: false
changed_npm_packages: []            # package@version npm entries to add to the project's package.json
requires_tailwind_rebuild: false
---

# Upgrade notes: <spec-name>

## Breaking changes
<prose, or "None">

## Manual steps
<prose, or "None">
```

Flag semantics:

- **`requires_migrations`** — the feature adds or alters models; downstream must run `migrate`.
- **`requires_template_review`** — one or more templates that downstream projects typically override were changed. List paths in `changed_template_paths`.
- **`requires_settings_change`** — new or renamed settings keys. List them in `changed_settings`. Distinguish a **hard requirement** (the downstream must supply the value — usually because a new or changed FLS system check enforces it at boot) from an optional/informational change. For a hard requirement, set the flag `true`, name the specific keys, and say in the prose that a boot-time check enforces it, so `update_fls` can point the downstream at `manage.py check` (`freedom_ls_course_access.E001` for `COURSE_ACCESS_BACKEND` and `freedom_ls_content_engine.E001` for `ADMONITION_TYPES` are current examples of such checks, not an exhaustive list — write this rule generally so a future check follows it automatically). Mark hard vs optional entries with an inline `#` comment against each entry — this needs the block-sequence YAML form (`changed_settings:` followed by `- KEY  # ...` lines), since the empty `changed_settings: []` flow style has no entries to attach a per-entry comment to. The schema block above shows the annotated form.
- **`requires_package_upgrade`** — new or updated Python packages. List `package==version` entries in `changed_packages`.
- **`requires_npm_install`** — new or updated npm packages (e.g. a new `@iconify-json/*` icon set or a build tool). Downstream projects keep their **own** `package.json`, so `uv sync` can't pick these up — they must be mirrored into it and `npm install` run. List `package@version` entries in `changed_npm_packages`.
- **`requires_tailwind_rebuild`** — Tailwind source changed; downstream must rebuild the CSS bundle.

A renumbered or repurposed system check ID is itself a hard settings change, even when no setting's value changes: name `SILENCED_SYSTEM_CHECKS` in `changed_settings`. The sharp case is `freedom_ls_course_access.E001`, which was repurposed to mean "a required setting is unset" — a downstream project that had silenced `freedom_ls_course_access.E001` keeps silencing successfully after the change, but is now silencing a different check, with no error to tell them.

Every unused list stays `[]` and every unused flag stays `false`; a list you populate switches to the block-sequence form shown in the schema.

## Step 1: Locate the spec directory

Find the spec directory for the current feature. In order:

1. If the caller named a path, use it.
2. Match the current branch name to a directory under `spec_dd/2. in progress/`.
3. If ambiguous, use `AskUserQuestion` to confirm before proceeding.

The spec directory is the directory that contains `1. spec.md` (and usually `2. plan.md`).

## Step 2: Gather inputs

Read these files (they drive the content of the upgrade notes):

- `<spec-dir>/1. spec.md` — what the feature does and what it changes.
- `<spec-dir>/2. plan.md` — implementation decisions that affect downstream projects.

Then run the following Bash commands to get the actual diff:

```bash
# All commits on this branch since it diverged from main
git log main..HEAD --oneline

# Full diff of everything this branch has changed
git diff main..HEAD
```

Read the output. Focus on:

- New or changed migration files → `requires_migrations`
- Changed templates under `freedom_ls/` → `requires_template_review` + `changed_template_paths`
- New or changed `settings` keys or `config/` files → `requires_settings_change` + `changed_settings`. A new required setting, or a `checks.py` change that starts enforcing one at boot, is a **hard** requirement (see flag semantics above); a renumbered or repurposed check ID is a hard change too, even with no setting's value changed.
- Changes to `pyproject.toml` or `requirements*.txt` → `requires_package_upgrade` + `changed_packages`
- New or changed npm dependencies in `package.json` / `package-lock.json` → `requires_npm_install` + `changed_npm_packages`. Adding a new `@iconify-json/*` icon pack typically sets **both** this flag and `requires_tailwind_rebuild`.
- Changes to Tailwind source files (e.g. `tailwind.config.*`, input CSS, any `*.html` that introduces new Tailwind utility classes a downstream bundle must include) → `requires_tailwind_rebuild`

## Step 3: Write upgrade_notes.md

Write `<spec-dir>/upgrade_notes.md` using the schema above.

Rules for the prose sections:

- **Facts only.** Base every statement on the spec, the plan, and the actual diff. Do not speculate.
- **Right altitude.** The audience is a developer maintaining a downstream FLS project. Name settings, migration commands, and template paths explicitly when relevant. Skip internal implementation details they don't need.
- **Breaking changes** — list anything a downstream project must change in their own code to stay working (renamed settings, removed template blocks, changed URLs, altered model fields). Write "None" if there are none.
- **Manual steps** — list concrete actions the downstream developer must take after pulling (e.g. "run `manage.py migrate`", "rebuild Tailwind", "review and re-apply customisations to `freedom_ls/learner_interface/templates/…`"). Write "None" if there are none.

Keep the prose short and actionable. If there is genuinely nothing for downstream projects to do, say so plainly — an honest "no action needed" is more useful than padding.

## Step 4: Tick the todo

Delegate the todo tick to `sdd:sdd-mechanic`. Spawn the mechanic with this instruction:

> Read the helper file at `claude_plugins/sdd/commands/protected/update_todo.md` and follow its steps with:
> - `<todo-path>`: the `todo.md` in the spec directory for the current feature
> - `tick:"Run \`/update_upgrade_notes\` to author the structured upgrade_notes.md for downstream projects"`

The mechanic edits `todo.md` directly.
