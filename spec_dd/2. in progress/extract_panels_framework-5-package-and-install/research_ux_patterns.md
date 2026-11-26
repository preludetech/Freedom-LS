# Research: developer-experience patterns for the package install and dev loop

Topic `ux_patterns`. The "users" here are developers (FLS developers, agents, First-Class, the concrete template). Nothing in this spec changes an end-user screen.

## 1. README shape for a reusable Django app

Source: Django's "Advanced tutorial: How to write reusable apps" (https://docs.djangoproject.com/en/stable/intro/reusable-apps/). Its README has a **Quick start** with a short numbered list, each step one action plus one code line:

1. Add the app to `INSTALLED_APPS`.
2. Include the URLconf in the project `urls.py`.
3. Run `python manage.py migrate`.
4. Start the dev server and check one URL.

The Django tutorial's own naming advice is a `django-` distribution prefix and `django_` module prefix, with a unique app label. That matches `django-panel-framework` / `panel_framework`.

Recommended README order for `django-panel-framework` (fits the idea's settled facts):

1. One-line description and licence line: "MIT licensed. Outside contributions (pull requests, patches) are not accepted for now." No `CONTRIBUTING.md`.
2. **Requirements**: Python, Django, PostgreSQL, Node/Tailwind v4 versions.
3. **Install**: the git-tag form, because there is no PyPI.
   ```
   uv add "django-panel-framework @ git+https://github.com/preludetech/django-panel-framework.git@v0.1.0"
   ```
   Also show the `pyproject.toml` PEP 508 line, since that is what FLS and Docker use. Say once: "Pin a tag, never a branch. Upgrade by changing the tag and running `uv lock`."
4. **Quick start**, numbered, each step a code block:
   - `INSTALLED_APPS += ["panel_framework"]`
   - `path("panel/", include("panel_framework.urls"))` (use the real include the host contract defines)
   - Settings: a table of every setting with default and "required / optional" (the settings helper from spec 3 is the source). Mark required ones so the system check message and README agree.
   - `python manage.py migrate`
   - Tailwind: generate the source file with the spec 4 command, import it in `tailwind.input.css`, rebuild. State the `not-ignored:` reason in one sentence, because `.venv` is gitignored.
5. **Host contract**: site-resolver hook, what the host must provide.
6. **Upgrading**: "Read `CHANGELOG.md` for every tag between yours and the target. Each entry carries flags saying what you must do."
7. **Licence and third-party assets**: pointer to `LICENSE` and the Heroicons notice.

Pattern notes:
- Keep Quick start to copy-paste blocks. Put explanations after the block, not before.
- Put the Tailwind step in Quick start, not a later section; it is the step hosts forget because nothing errors, the styles are just missing.
- Do not document the live-editing loop in this README; spec 6 owns the developer doc. A single line "FLS developers: see the FLS worktree docs" is enough, or omit it.

## 2. CHANGELOG entry with install/upgrade flags

Sources: Keep a Changelog 1.1.0 (https://keepachangelog.com/en/1.1.0/): written for humans, an entry per version, newest first, ISO 8601 date, `Unreleased` at top, change types `Added / Changed / Deprecated / Removed / Fixed / Security`, yanked marker in the heading. The FLS flag schema is in `claude_plugins/fls-dev/commands/update_upgrade_notes.md` (`requires_migrations`, `requires_template_review` + `changed_template_paths`, `requires_settings_change` + `changed_settings`, `requires_tailwind_rebuild`, `requires_package_upgrade`).

Layout that combines both: a fixed "Upgrade" block at the top of each tag entry (what the developer must do), then the Keep a Changelog sections (what changed). The reader who only upgrades reads the first block and stops.

Rule block at the very top of the file, before any entry:

```
# Changelog

Format: Keep a Changelog. Versions: tags (`vMAJOR.MINOR.PATCH`).

Deprecation rule: a breaking change keeps the old surface working, with a
deprecation warning, for one tag. It is removed in the tag after that.

Every entry starts with an Upgrade block. A flag set to `yes` has a matching
action listed under it.
```

Example entry (flags use the same names as FLS `upgrade_notes.md`, so downstream tooling reads one vocabulary):

```
## [0.1.0] - 2026-MM-DD

### Upgrade
- requires_migrations: yes
  - Run `python manage.py migrate`. New table `panel_framework_bulkactionrun`.
- requires_template_review: yes
  - Review if you override: `panel_framework/panel.html`, `panel_framework/icons/...`
    (list every path; this is `changed_template_paths`)
- requires_settings_change: yes
  - Add `"panel_framework"` to `INSTALLED_APPS`. Add the URL include.
    (list setting names; this is `changed_settings`)
- requires_tailwind_rebuild: yes
  - Import the generated source file in `tailwind.input.css`, then run your Tailwind build.
- requires_package_upgrade: yes
  - `django-panel-framework @ git+https://github.com/preludetech/django-panel-framework.git@v0.1.0`

### Added
- First release as a standalone package. Moved from `freedom_ls.panel_framework`.

### Deprecated
- (none)
```

Where a flag is `no`, print `no` on one line rather than omitting it: a reader can tell "checked, nothing to do" from "forgot to say". For a long list of flags, put `no` flags on one line: "No action: migrations, settings."

Wording rules for action lines:
- Start with a verb and name the exact command or file: "Run `python manage.py migrate`", not "Apply migrations".
- Say what happens if skipped: "If skipped, the panel renders unstyled."
- For a first-time install (as in `v0.1.0`), give the FLS-only note separately: "Existing FLS databases: the old table `freedom_ls_panel_framework_bulkactionrun` is dropped by FLS migration `<name>`; no action."

## 3. Dev-loop script messages

No single standard exists; the pattern below follows common CLI guidance (state what was skipped, why, the consequence, and the exact next command) and the uv facts that matter: `uv sync --locked` errors instead of updating the lockfile (https://docs.astral.sh/uv/concepts/projects/sync/), and `--no-sync` skips the environment check. That uv page does not document `UV_NO_SYNC` by name, so spike 1 should confirm it against the installed uv version and the CLI reference (https://docs.astral.sh/uv/reference/environment/) before the message text relies on it.

Message shape: `[level] what happened. Consequence. Next: <command>`. One line when possible, `Next:` always last and copy-pasteable. Exit code: 0 for a skip, non-zero for a failed check.

### 3a. Skipped optional step (missing local checkout), in `rebuild_after_rebase.sh`

Skip is not an error; the developer who does not edit the package has no checkout. Exit stays 0.

```
rebuild_after_rebase: SKIPPED editable panel_framework
  PANEL_FRAMEWORK_DIR=/home/sheena/workspace/software_factory/django-panel-framework.git/main does not exist.
  Using the locked git copy (tag v0.1.0). Local edits to the package will not show up.
  To edit it live: git clone https://github.com/preludetech/django-panel-framework.git <dir>
                   export PANEL_FRAMEWORK_DIR=<dir>   # absolute path, then rerun this script
```

Success line, for symmetry, so the developer can see the link is active:

```
rebuild_after_rebase: panel_framework linked editable from <dir> (HEAD <short-sha>)
  Keep UV_NO_SYNC=1 set, or `uv run` will put the locked copy back.
```

Notes:
- Print the resolved absolute path, not the variable name alone; the default is invisible to the developer otherwise.
- Say "skipped" in capitals once; agents grep logs for it.
- If the directory exists but is the bare repo (no working files), say so: "`<dir>` is a bare repo; point PANEL_FRAMEWORK_DIR at the `main` worktree." The idea settles `main` checkout, so this is a likely mistake.

### 3b. Failed check: installed revision differs from lock (runs before landing)

Per `answers.md`, the check runs when a worktree lands, not on commit. It fails if the editable checkout HEAD is not the locked rev, or the checkout has uncommitted changes. Two distinct failures need two distinct messages, because the fixes differ.

Rev differs:

```
land check FAILED: installed panel_framework is not the locked rev
  installed: 3f9a1c2 (editable, /home/.../django-panel-framework.git/main)
  locked:    b71e04d (tag v0.1.0, from uv.lock)
  CI installs the locked rev, so tests that pass here can fail there.
  Next, pick one:
    - The package change is done:  cd <dir> && git tag vX.Y.Z && git push origin vX.Y.Z
                                   then bump the pin in pyproject.toml and run `uv lock`
    - Not your change:             cd <dir> && git checkout v0.1.0
  Then rerun the FLS suite and land again.
```

Uncommitted changes:

```
land check FAILED: panel_framework checkout has uncommitted changes
  <dir> (3 files). A tag cannot include them.
  Next: commit and push them in the package repo, tag, bump the pin, run `uv lock`.
```

No editable link (nothing to compare; the locked copy is in use): print `land check: ok (locked copy in use)` and exit 0.

Pattern notes:
- Show both values side by side with labels aligned; the developer sees the difference without reading prose.
- Give the reason in one sentence ("CI installs the locked rev"). A check with no stated reason gets bypassed.
- Offer the two real intents (I finished a package change / I did not touch it) as separate commands, since the same symptom has both causes.
- Never auto-fix: the check must not move a developer's package checkout. It reports and exits non-zero.
- Run failure output to stderr; keep the first line self-contained for CI logs and for agents that only see the last line of output.

### 3c. Related one-liners

- `UV_NO_SYNC` missing while an editable link is expected (if the script can detect the locked copy has replaced the link): `WARNING: panel_framework is the locked copy, not your checkout. Run: export UV_NO_SYNC=1 && bash claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh`
- Tailwind output stale after a pin bump: `Tailwind source for panel_framework changed. Run: npm run tailwind_build` (mirrors the changelog `requires_tailwind_rebuild` line).

## 4. Consequences for the spec

- README: Quick start follows Django's four-step shape plus settings and Tailwind steps; both are in the numbered list.
- CHANGELOG: an `Upgrade` block with the five flag names exactly as in `update_upgrade_notes.md`, then Keep a Changelog sections; deprecation rule at the top.
- Scripts: skip message names the path, the consequence and the fix; failed check prints installed vs locked side by side with two labelled next commands.
- Open items the spec should resolve: confirm `UV_NO_SYNC` behaviour (spike 1) before quoting it in messages; decide the script exit codes (0 skip, non-zero fail) and where the land check lives (already decided: before landing, in `fls-dev`).

## Sources

- https://docs.djangoproject.com/en/stable/intro/reusable-apps/
- https://keepachangelog.com/en/1.1.0/
- https://docs.astral.sh/uv/concepts/projects/sync/
- https://docs.astral.sh/uv/reference/environment/ (cited for the `UV_NO_SYNC` confirmation; not fetched, spike 1 must verify)
- Local: `claude_plugins/fls-dev/commands/update_upgrade_notes.md` (flag schema)

status: ok
