---
description: Update the concrete-project template repo when an FLS feature changes something new projects need
allowed-tools: Read, Write, Glob, Edit, Bash, Agent
---

Update the **template repo** — the scaffold new concrete FLS projects are created from — so that projects created *after* this feature ships start with the change already in place.

This is the upstream counterpart to `/update_fls`. `/update_fls` propagates a completed FLS spec into an **existing** downstream project; this command propagates it into the **scaffold** that new downstream projects are generated from. The template repo is the source of the files `fls:init` deliberately does *not* create: `config/`, `pyproject.toml`, the Tailwind config, the `CLAUDE.md` skeleton, and the baseline `.claude/settings.json`.

This command runs at **depth 0**. It edits files in a *separate* git repository on the local machine, so it never commits there automatically — it leaves the edits in the template repo's working tree and reports them for the user to review and commit.

## Step 1: Locate the spec directory

Find the spec directory for the current feature. In order:

1. If the caller named a path, use it.
2. Match the current branch name to a directory under `spec_dd/2. in progress/`.
3. If ambiguous, use `AskUserQuestion` to confirm before proceeding.

The spec directory is the directory that contains `1. spec.md` (and usually `2. plan.md` and `upgrade_notes.md`).

## Step 2: Resolve the template repo path from local config

The template repo path is machine-specific, so it lives in the gitignored local config file `.claude/fls/config.local.md` (see the `## Template Repo` section).

1. Read `.claude/fls/config.local.md`.
2. Find the `Template repo path:` entry and take its value.
3. If the entry is missing or blank, **stop** and tell the user:
   > No template repo path is configured. Add it under a `## Template Repo` section in `.claude/fls/config.local.md`:
   > ```
   > ## Template Repo
   > - Template repo path: /absolute/path/to/your/template-repo
   > ```
   > Then re-run `/update_template_repo`. If you don't maintain the template repo locally, tick this step by hand and skip it.
4. Validate the path: confirm the directory exists and is a git repository (`git -C <path> rev-parse --is-inside-work-tree`). If it isn't, stop and report the bad path.

## Step 3: Determine what (if anything) the template repo needs

Read the change's downstream impact. Prefer the structured notes; fall back to the diff.

1. Read `<spec-dir>/upgrade_notes.md` if it exists and parse its frontmatter flags.
2. Run `git diff main..HEAD --stat` (and inspect specific files as needed) to see what actually changed.

First read `${CLAUDE_PLUGIN_ROOT}/resources/template_repo_manifest.md` — the manifest for the concrete-implementation template repo. Its file-tree listing and `config/` content contract tell you the scaffold's actual layout and what each file is expected to contain, so you can map an FLS change to the right template file with confidence. Use it alongside the signal→file table below.

Map the changes to template-repo-relevant categories. Only these matter here — the template repo carries the project *scaffold*, not FLS's own source. The paths below are the template repo's actual layout:

| Signal | Template repo file(s) to update |
|---|---|
| `requires_settings_change` / changes under FLS's `config/` | `config/settings_base.py` for shared keys/defaults; `config/settings_dev.py` / `config/settings_prod.py` for environment-specific values; `config/urls.py` if FLS exposes new root URLs new projects must wire up |
| `requires_package_upgrade` / `pyproject.toml` changes | `pyproject.toml`. **Don't hand-edit `uv.lock`** — note that the user must run `uv lock` in the template repo to refresh it |
| `requires_npm_install` / `package.json` changes | `package.json` — add the new npm deps from `changed_npm_packages` (e.g. a new `@iconify-json/*` icon set or Tailwind version). **Don't hand-edit `package-lock.json`** — note that the user must run `npm i` in the template repo to refresh it |
| `requires_tailwind_rebuild` / Tailwind/theming changes | `tailwind.input.css` — its `@source` globs mirror `FLS_THEMES_DIRS` in `config/settings_base.py`, so keep the two in sync; and `themes/custom/static/themes/custom/theme.css` for theme tokens (npm package bumps for new icon sets are handled by the `requires_npm_install` row above) |
| Changes to project conventions documented in FLS's `CLAUDE.md` | the root `CLAUDE.md` skeleton |
| Changes to the recommended baseline `.claude/settings.json` | `.claude/settings.json` |

Notes:

- **Never edit anything under the template repo's `submodules/`** — that's the FLS submodule, a read-only dependency. All scaffold changes go in the template repo's own files (`config/`, `themes/custom/`, `templates/`, root config files, project apps under `apps/`).
- `requires_template_review` / `changed_template_paths` in `upgrade_notes.md` refers to **Django HTML templates** that downstream projects override — that is a different concern handled by `/update_fls`, not this step. Don't conflate the two.

## Step 4: If nothing is relevant, report and finish

If none of the categories above apply, the template repo needs no change. Say so plainly, then go straight to Step 6 (tick the todo). An honest "no template repo update needed" is the correct output for most features.

## Step 5: Make the edits in the template repo

For each relevant category, apply the corresponding edit **inside the template repo** at the configured path. Edit only what new projects genuinely need — mirror the change, don't copy FLS internals.

- Make the smallest change that brings the scaffold in line with the feature (e.g. add the new setting with its default in `config/settings_base.py`, add the new package to `pyproject.toml`, add the `@source` glob to `tailwind.input.css`).
- Match the template repo's own conventions and formatting.
- Never touch the template repo's `submodules/` directory — only its own scaffold files.
- Do **not** run migrations, builds, or tests in the template repo, and do **not** commit there. The template repo is a separate repository with its own review process.
- Don't hand-edit lockfiles. If you changed `pyproject.toml`, note that the user must run `uv lock` in the template repo; if you changed npm deps in `package.json`, note that they must run `npm i`.

Use `${CLAUDE_PLUGIN_ROOT}/resources/template_repo_manifest.md` as your reference while editing:

- Its **`config/` content contract** is the completeness checklist for settings/middleware/URL changes — check `INSTALLED_APPS` ordering and required keys against it when you add or adjust a setting.
- Its **"What must be absent"** exclusion table is the authority on FLS-internal dev items (`freedom_ls.qa_helpers`, `FORCE_SITE_NAME`, the DemoDev role module/mapping, FirstClass demo branding, the demo `"regulation"` admonition, etc.) that must **never** be copied into the scaffold. This is the concrete form of "mirror the change, don't copy FLS internals" above. Note the scaffold *does* intentionally carry the branch-aware multi-worktree dev setup (branch→db logic, `SESSION_COOKIE_NAME`, `debug_branch_info`, `HEADLESS_SERVE_SPECIFICATION`) — see the manifest's `settings_dev.py` contract and "Multi-worktree dev setup" section.

After editing, run `git -C <path> status --short` and `git -C <path> diff` and include a concise summary of every file you touched — plus any lockfile-regeneration the user still needs to run — in your report, so they can review and commit in the template repo themselves.

## Step 6: Tick the todo

Delegate the todo tick to `fls:sdd-mechanic`. Spawn the mechanic with this instruction:

> Read the helper file at `fls-claude-plugin/commands/sdd/protected/update_todo.md` and follow its steps with:
> - `<todo-path>`: the `todo.md` in the spec directory for the current feature
> - `tick:"Run \`/update_template_repo\` to update the template repo for new projects"`

The mechanic edits `todo.md` directly.
