# Research: Claude skill for "extract a Django app into its own installable package"

Research input for the extract-icons-app spec. Focused on what the skill should look like, not on doing the extraction.

## 1. Skill format conventions in this project

Local skills read for this research:

- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/icon-usage/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/template/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/multi-tenant/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/testing/SKILL.md` (longest)
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/htmx/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/admin-interface/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/markdown-content/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/playwright-tests/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/git-worktree-setup/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/alpine-js/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/frontend-styling/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/request-code-review/SKILL.md`
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/icon-usage/resources/configuring-icons.md` (resource)
- `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/skills/icon-usage/resources/custom-icon-backend.md` (resource)

### Frontmatter fields

Most skills use a four-field frontmatter:

```yaml
---
name: <kebab-case-id>
description: <one-sentence "use when..." trigger>
allowed-tools: Read, Grep, Glob
---
```

Observations:

- `name` is omitted in some skills (`htmx`, `alpine-js`, `request-code-review`, `git-worktree-setup`); when present it matches the directory name (often, though `icon-usage` declares `name: using-icons`).
- `description` is always present and uses the imperative "Use when..." voice. Length is typically a single sentence focused on triggering keywords.
- `allowed-tools` is usually `Read, Grep, Glob` (read-only). Skills that drive behaviour (the SDD slash commands) omit it. None of the inspected skills declare write/edit/bash tools, because the skills documented are reference/guidance skills, not action skills.

### Body conventions

- H1 = skill title.
- "When to Use This Skill" / "When to use" section with bullet triggers.
- "Key Rules" section (4-8 bullets) for the essence.
- Optional "Patterns", "Anti-pattern cheatsheet", "Existing Components" tables.
- A pointer to a resource file under `${CLAUDE_PLUGIN_ROOT}/resources/<topic>.md` for full detail. The skills file itself stays short (mostly < 50 lines, longest is `testing/SKILL.md` at 181 lines because it embeds opinionated TDD doctrine).
- Resource folder usage: skills use either `${CLAUDE_PLUGIN_ROOT}/resources/<topic>.md` (a global resources dir) **or** a local `resources/` folder beside `SKILL.md` (icon-usage uses the local pattern with `configuring-icons.md` and `custom-icon-backend.md`). Both are valid; the local pattern is appropriate when the resources are tightly coupled to the skill.

### Length

- Reference/lookup skills: 25-50 lines (admin-interface, multi-tenant, frontend-styling, icon-usage).
- Doctrine skills with tables and examples: up to ~200 lines (testing, alpine-js).
- Workflow skills (request-code-review): ~100 lines, more procedural.

The extraction skill is procedural/workflow, so it sits closer to `request-code-review` and `git-worktree-setup` in shape, with opinionated steps but heavy reliance on a resource file for the long checklist.

## 2. What "extracting a Django app" entails

Concrete steps, in roughly the order a human/Claude should perform them. The icons app is the first target; this list assumes generic reusable Django apps.

### A. Pre-flight: feasibility audit

1. Inventory host-project dependencies of the app under consideration:
   - `grep -rn "from freedom_ls\." <app>/ ` — any cross-app imports?
   - `grep -rn "AUTH_USER_MODEL\|accounts.User\|get_user_model" <app>/`
   - `grep -rn "SiteAwareModel\|site_aware_models" <app>/` — multi-tenant base class coupling
   - `grep -rn "from config" <app>/` — settings module imports
   - Inspect `apps.py` and the app's settings reads — what `settings.FOO` does it reference?
   - Inspect templates for `extends "_base.html"` and any cross-app cotton component dependencies (`<c-button>`, `<c-loading-indicator>`, etc.)
   - Inspect static asset coupling (e.g. iconify JSON living in host `node_modules/`).
   - Inspect management commands, migrations, signals, model dependencies.
2. Classify dependencies:
   - **Hard** (must be broken or pluggable before extraction — e.g. `accounts.User` FK, `SiteAwareModel` inheritance).
   - **Soft** (configurable via settings — e.g. iconify JSON path, icon set name).
   - **Test-only** (use only inside tests — replace with package-internal fixture).
3. Decision gate: is the app already cohesive enough? If hard dependencies exist, the spec must call for refactor work *before* extraction (this is per-app judgement, not skill-driven).

For the icons app specifically, the audit shows:
- Only one external reference: `config/settings_base.py:66` adds `"freedom_ls.icons"` to `INSTALLED_APPS`.
- No cross-app Python imports inside the app.
- No `User` or `SiteAwareModel` coupling.
- Templates: only `templates/cotton/icon.html` (self-contained).
- Soft dependency: `settings.BASE_DIR / node_modules / @iconify-json/<pkg>/icons.json` (iconify JSON path is hard-coded but parameterisable).
- No models, no migrations.

### B. Renaming module paths

1. Decide the new top-level package name (per-app judgement — see section 6).
2. Replace every `from freedom_ls.<app>` with `from <new_package>`. The icons app has 17 such imports across `backend.py`, `checks.py`, `apps.py`, `templatetags/icon_tags.py`, and the `tests/` files.
3. Update `apps.py`: `name = "<new_package>"`.
4. Update `templatetags/__init__.py` references if the templatetag library name changes (here it doesn't — `icon_tags` is fine, but it could clash in a host project).
5. Rename setting prefixes if the package is no longer FLS-specific (e.g. `FREEDOM_LS_ICON_SET` → `DJANGO_ICONS_ICON_SET` or keep with a deprecation alias). Per-app judgement.

### C. Package scaffolding

Files to create at the new repo root:

- `pyproject.toml` — PEP 621 metadata, `[project]`, `[project.optional-dependencies]`, `[tool.setuptools.packages.find]` (include `<new_package>*`, exclude `tests*`). Use the host `pyproject.toml` `[tool.setuptools.packages.find]` block as a pattern.
- `MANIFEST.in` — include templates, static, iconify JSON if shipped, README, LICENSE, CHANGELOG.
- `LICENSE` (per-app judgement — see section 6).
- `README.md` — install instructions, configuration, quickstart, contributing.
- `CHANGELOG.md` — start at `0.1.0`, follow Keep a Changelog.
- `.gitignore`, `.pre-commit-config.yaml` (mirror host).
- `.editorconfig` (optional; mirror host if present).

### D. Standalone test harness

- `tests/conftest.py` — pytest-django setup. Configure settings via `pytest-django`'s `DJANGO_SETTINGS_MODULE` pointing at `tests/settings.py`.
- `tests/settings.py` — minimal Django settings: `INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth", "<new_package>"]`, in-memory SQLite, `BASE_DIR` set to a fixture dir that contains the iconify JSON for icons specifically.
- `tests/fixtures/` — for the icons app, vendored iconify JSON snippets so tests don't need `node_modules`.
- Move the existing `freedom_ls/icons/tests/` into `tests/` (or keep under the package — convention varies; for an installable, a top-level `tests/` dir kept *out* of the wheel is cleanest).
- Update tests to import from the new top-level package.
- Address tests that rely on host-project state. `test_no_font_awesome.py` walks `freedom_ls/` for HTML — it cannot stay in the package as-is; it belongs in the host project. The skill should flag tests like this for human review.

### E. CI

- `.github/workflows/test.yml` — matrix across supported Python (3.13, 3.14) and Django (6.0, 6.1) versions. `uv sync`, `pytest`, `ruff`, `pyright`/`mypy`.
- `.github/workflows/release.yml` — trigger on tag `v*`, build wheel + sdist, publish to PyPI via `pypa/gh-action-pypi-publish` with trusted publishing.
- (Optional) Pre-commit CI.

### F. Templates / static / management commands decoupling

- Templates: ship under `<new_package>/templates/<new_package>/...`. For icons, the cotton component path becomes `<new_package>/templates/cotton/icon.html`. Cotton resolution is global by default — note this collision risk for the spec (different apps cannot ship a `cotton/icon.html` of the same name).
- Static: ship under `<new_package>/static/<new_package>/...`.
- Management commands: not applicable for icons; for other apps, place under `<new_package>/management/commands/` and document `manage.py <name>` usage in README.
- For icons specifically: the iconify JSON dependency. Options to document in README:
  1. Continue requiring host to `npm install @iconify-json/<pkg>` (current approach; still requires Node).
  2. Make the loader path configurable via `FREEDOM_LS_ICON_SET_PATH` so the host can supply any source.
  3. Vendor a small set of icons as JSON inside the package (large bundle).
  This is per-app judgement and should be settled in the spec.

### G. Versioning, first release, tagging

- Start `0.1.0` (pre-1.0 signals API instability — appropriate for first extraction).
- Tag `v0.1.0`, push tag, GitHub Actions publishes to PyPI.
- Add a "Compatibility" section to README listing supported Django/Python.

### H. New GitHub repo

- Create empty repo (`gh repo create`).
- Push extracted code as initial commit.
- Set up branch protection on `main`.
- Add issue/PR templates if desired.
- Configure PyPI trusted publishing on PyPI side (one-time, manual via PyPI web UI — cannot be automated).

### I. Update host project to depend on new package

- Add `"<new_package>>=0.1.0"` to host `pyproject.toml` `[project] dependencies`.
- Replace `INSTALLED_APPS` entry `"freedom_ls.icons"` with `"<new_package>"`.
- `git rm -r freedom_ls/icons` (after package is published and pinned).
- Run host test suite. Update any host code that imports from the old path (none for icons today, but the skill should grep to confirm).
- Document the migration in host CHANGELOG.

## 3. Repeatable parts vs app-specific parts

### Repeatable (skill should standardise)

- Inventory commands (the grep patterns for finding cross-app coupling).
- Pre-flight checklist questions and the dependency classification matrix.
- File scaffolding: `pyproject.toml` template, `MANIFEST.in`, `LICENSE` placeholder, `README.md` skeleton, `CHANGELOG.md` skeleton, GitHub Actions YAML for test + release matrices, `tests/settings.py` skeleton, `tests/conftest.py` skeleton.
- Module-rename procedure (a script-able find/replace given old and new module roots).
- Tag-and-release procedure.
- Host-project update procedure.
- A "do not do these" list (don't break public APIs without major version bump, don't ship test files in wheels, don't depend on host settings without documenting it).

### App-specific (per-app judgement; skill should flag and prompt)

- New PyPI/package name and Python module name (see section 6).
- Whether to keep the `FREEDOM_LS_*` setting prefix or rename (compatibility cost).
- Strategy for static / data file dependencies (icons' iconify JSON is the obvious one; a markdown content app might bundle CSS).
- How to handle host-project couplings discovered in pre-flight (refactor, abstract, or block extraction).
- Decision on whether to vendor data, ship a peer dependency, or document a runtime requirement.
- License choice.
- Whether to ship migrations / fixtures in the wheel.

## 4. Recommended skill structure

**Recommended: one `SKILL.md` plus a single companion checklist resource, plus a `templates/` resource directory.** Specifically:

```
fls-claude-plugin/skills/extract-django-app/
  SKILL.md                    # short trigger + workflow overview
  resources/
    extraction-checklist.md   # the long step-by-step checklist (sections A-I above)
    pre-flight-audit.md       # the inventory grep patterns + dependency classification
    package-scaffolding.md    # file-by-file what to create and why
    host-update.md            # how to switch the host project to the new package
    file-templates/           # literal templates for pyproject.toml, README.md, etc.
      pyproject.toml.tmpl
      tests-conftest.py.tmpl
      tests-settings.py.tmpl
      gh-workflows-test.yml.tmpl
      gh-workflows-release.yml.tmpl
      MANIFEST.in.tmpl
      CHANGELOG.md.tmpl
      README.md.tmpl
```

Reasoning:

- A single `SKILL.md` keeps the trigger surface simple — one skill name to discover and reference. Sub-skills (e.g. `extract-django-app:audit`, `extract-django-app:scaffold`) would be over-decomposed for what is fundamentally one workflow.
- The checklist is long enough that embedding it in `SKILL.md` violates the "skills stay short" convention seen in the testing skill (which still pushed the full TDD doctrine to a resource file in the global `resources/` directory). The local `resources/` folder pattern (used by `icon-usage`) keeps related material co-located.
- File templates are the highest-leverage repeatable artefact. Rendering them via simple variable substitution (`<<PACKAGE_NAME>>`, `<<MODULE_NAME>>`, `<<DESCRIPTION>>`, `<<AUTHOR>>`, `<<LICENSE>>`) is repeatable across all future extractions.
- Splitting the resource doc into `pre-flight-audit`, `package-scaffolding`, and `host-update` mirrors the natural phase boundaries (discover, build, switch over) and lets the skill author/agent jump to the relevant section quickly.

Alternative considered: a series of sub-skills (`fls:extract:audit`, `fls:extract:scaffold`, `fls:extract:release`). Rejected because:
- The phases are sequential and tightly coupled — there is no realistic flow that uses only one phase in isolation.
- Sub-skills add discovery surface (more names to learn/trigger) for no information gain.
- The SDD workflow under `fls:sdd:*` already shows a sub-skill pattern, but those are genuinely independent commands the user runs in different conversations. Extraction is one conversation.

## 5. Tools the skill should declare (`allowed-tools`)

The extraction skill is a **doing** skill, not a reference skill, so it needs more than `Read, Grep, Glob`:

```yaml
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
```

Justification per tool:

- `Read` — reading existing app code, templates, settings.
- `Grep` — running the inventory greps in the pre-flight audit.
- `Glob` — discovering templates, static, migrations, management commands.
- `Edit` — module-path renames, settings-prefix renames, host `pyproject.toml` edits.
- `Write` — writing scaffolded `pyproject.toml`, `README.md`, CI YAML, `tests/settings.py`, etc.
- `Bash` — `git worktree`, `git mv`, `gh repo create`, `uv build`, `uv publish`, `npm install`-style checks during test-harness validation, running `pytest` in the new package.

Note: per `CLAUDE.md`, `git commit` must use `uv run git commit ...` for pre-commit hooks. The skill must call this out.

The skill should NOT declare any MCP browser tools or anything else — the workflow is filesystem and git only.

## 6. What to leave to a human

The skill should explicitly stop and ask, never automate, the following:

1. **PyPI / Python package name.** PyPI namespace is global and irrevocable. Ask the user. (For icons, `freedom-ls-icons` vs `django-semantic-icons` vs `django-iconify-semantic` are all defensible; the answer affects branding and discoverability.)
2. **Top-level Python module name.** Often, but not always, derived from the PyPI name (`freedom_ls_icons` vs `django_semantic_icons`). Ask.
3. **License choice.** MIT, Apache 2.0, BSD-3, AGPL — has legal and ecosystem implications. Ask.
4. **Whether to rename `FREEDOM_LS_*` settings.** Renaming hurts existing users; keeping is a leaky abstraction. The skill should *recommend* keeping with deprecation alias but defer to user.
5. **Which Python and Django versions to target.** The host pins `python>=3.13` and `django>=6.0,<6.1`. The new package may want a wider matrix. Ask.
6. **Breaking API decisions.** If the extraction reveals an awkward public API, the skill should call it out and ask whether to fix-now (release as `0.1.0` with new shape) or fix-later (release as `0.1.0` faithful, then `0.2.0` with break).
7. **Where to host the new repo** (personal vs org account on GitHub). Ask.
8. **Whether to bundle vendored data** (e.g. the iconify JSON files). This is a bundle-size vs setup-friction tradeoff. The skill should describe the tradeoff and ask.
9. **Whether the host should depend on a published version vs a local path / git URL during transition.** Per-project migration timing.
10. **Final go/no-go on `git rm -r freedom_ls/<app>`** in the host. Skill should never delete the in-tree app without explicit confirmation that the new package is published and the host's tests pass against it.

The skill should also flag any existing `TODO` or `@claude` comments in the app being extracted — per `CLAUDE.md` these must not be deleted.

## Summary

A single `extract-django-app` skill with a local `resources/` folder containing a long checklist split by phase plus a `file-templates/` directory of literal scaffolding templates. Frontmatter declares `Read, Grep, Glob, Edit, Write, Bash`. The skill standardises grep patterns, file scaffolding, and procedural steps; it explicitly defers naming, licensing, version-matrix, breaking-API, and `rm` decisions to the human user.
