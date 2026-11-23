# django-stack (`ds`) plugin

Portable Django-stack conventions for Claude Code. Everything here helps *any* project on this stack —
Python 3.13+, Django 6.x, PostgreSQL, HTMX, Tailwind, and optionally Cotton / Alpine / Playwright. It
carries **zero product-specific domain knowledge** and depends on no other plugin. Product-specific
conventions (multi-tenant / site-aware models, registration, markdown content, brand, etc.) belong in a
separate downstream plugin that layers thin overlay skills on top of the `ds` skills here.

Manifest name: `ds`. Namespace: `/ds:*`, `Skill(ds:*)`. `enabledPlugins` key: `ds`.

> This is the only plugin here whose directory (`django-stack/`) differs from its manifest name
> (`ds`). Every identifier Claude Code derives — the skill/command namespace, the agent prefix, the
> `mcp__plugin_ds_playwright__*` tool names, and the `enabledPlugins` key — comes from the **manifest
> name**, never the directory. Use `django-stack` only in filesystem paths (`--plugin-dir`,
> `claude_plugins/django-stack/`).

## Per-project config

Where projects legitimately differ, `ds` reads `.claude/ds/config.md` (created by `/ds:init` with
portable defaults) instead of hard-coding a choice:

| Section → key | Values (default) | Read by |
|---|---|---|
| `## Project Settings` → `Dev base URL` | any URL (`http://127.0.0.1:8000`) | `ds:use-playwright` |
| `## Dev Credentials` → `Admin email` | any email (blank) | `ds:use-playwright` |
| `## Dev Credentials` → `Admin password` | any string (blank) | `ds:use-playwright` |
| `## Alpine.js` → `CSP build` | `enabled` (default) / `disabled` | `ds:alpine-js` |
| `## Admin` → `Admin theme` | `standard` (default) / `unfold` | `ds:admin-interface` |
| `## Admin` → `Object permissions (django-guardian)` | `disabled` (default) / `enabled` | `ds:admin-interface` |

Everything else `ds` needs — design tokens, cotton components, Alpine plugins, template layout — is read
from the project's own code at the point of use, never assumed.

## What's inside (counted from disk)

### Skills (10)
`admin-interface`, `alpine-js`, `app-settings`, `code-comments`, `frontend-styling`, `htmx`, `playwright-tests`,
`template`, `testing`, `use-playwright`.

### Commands (10 files)
Top level: `init`, `commit`, `app_map`, `catchup`, `make_github_issue`, `rebase_main`, `tdd_implement`,
`placeholder_page`.
`periodic/`: `README`, `dependabot_prs`.

`/ds:init` wires up `ds` and, when they are missing, creates the generic plugin-neutral artifacts any
Claude Code project needs: a root `claude.sh` launcher (starting with the `django-stack` `--plugin-dir`
flag + `$CLAUDE_PLUGINS_LOADED`), the `SessionStart` hook, and the `.gitignore` `settings.local.json`
line. `claude.sh` is a shared file — `ds:init` only ensures its own `--plugin-dir` line and leaves any
other plugin's line untouched, so if other plugins are installed their inits add their own lines the
same way. It also migrates artifacts an older init baked in: the `$FLS_PLUGIN` sentinel, the
`FLS_PATH` variable, and pre-split header comments in `.claude/ds/scripts/*.sh`.

### Agents (1)
`code-reviewer` — a generic Python/Django/HTMX reviewer. Its persistent memory lives at
`.claude/agent-memory/ds-code-reviewer/`, prefixed with the plugin name so it cannot collide with a
host project's own reviewer memory (the same convention `sdd` uses for `sdd-qa-data-helper`).

### Scripts
`find_available_port.sh`, `generate_app_map.py`, `db_clear.sh`,
`kill_runserver.sh`, `install_pre_commit_hook.sh` (makes the shared git pre-commit hook run from
whichever worktree commits), plus the hook scripts under `scripts/hooks/` (`ruff_fix.sh`,
`post-edit-bandit.sh`, `security-guard.sh`).

### Resources (15)
`admin_standard`, `admin_unfold`, `admin_guardian`, `alpine_csp_build`, `alpine_no_csp`, `factory_boy`,
`frontend_styling`, `templates_and_cotton`, `testing`, `test_tiers`, `playwright-testing`, `qa_diff_scoping`, `agent_memory_guidelines`
(a self-contained copy — duplicated here because `${CLAUDE_PLUGIN_ROOT}` is per-plugin and
`code-reviewer` reads it), plus `launcher_editing` and `wrapper_script_migration` — the two procedures
`/ds:init` follows, duplicated into each plugin that edits `claude.sh` or ships wrapper scripts, for
the same per-plugin-root reason. Apart from a parameter table at the top, the copies are identical;
diff them when you change one.

Config-driven resources come in mutually-exclusive sets, and the owning skill routes to exactly one:
`admin_standard` **or** `admin_unfold` (plus `admin_guardian` only when enabled), and
`alpine_csp_build` **or** `alpine_no_csp`. Each file is self-contained, so a project never loads
guidance for a setup it doesn't have.

### Hooks & configs
`hooks/hooks.json` (ruff-fix + bandit on edit; a security guard on Bash/Write/Edit — any
product-specific pytest pre-commit runner is intentionally **not** here), `.mcp.json` (Playwright MCP
server), `.lsp.json` (Pyright).

### Templates
`ds:init` ships `templates/settings.json` (the generic permission baseline + the `SessionStart` hook)
and `templates/wrapper_scripts/` (`claude.sh` launcher plus `find_available_port.sh`, `db_clear.sh`,
`kill_runserver.sh`).

## Why it works this way

Rationale cut from the prompt files an agent reads at run time.

- **Rebase command.**
  - The in-flight work is committed, never stashed, so the lost-change check covers it like every
    other commit on the branch.
  - A branch with a merge commit stops with `status: blocked`: a rebase replays only a merge
    commit's first parent and drops the rest without a conflict, so a human has to decide.
  - A branch another worktree is halfway through merging is not rewritten: its `MERGE_HEAD` would
    point at a commit no branch holds, leaving whoever started the merge with a conflicted tree and
    nothing to finish it against.
  - Both push flags stay after the refspec because a rule that blocks `git push --force:*` is a
    prefix match, and `--force-with-lease` shares that prefix. `<branch>` is written out so the
    command cannot push a different branch when pasted elsewhere.
  - A caller can pass `<auto-resolve>`: ordered `<path prefix> → theirs | ours | <instruction>`
    entries, the first match deciding. Those paths are exempt from the rule against a wholesale
    `--ours` or `--theirs` on a non-generated file, and the summary lists each path with the side
    taken, so the caller can check them.
  - `<tier>` may be `none`: the rebase runs no tests and the caller runs its own tier. A caller
    may pass `<tests>` `none`, `change` or `everything` in its place. A targeted
    run that selects nothing reports `none` too.
  - Pre-commit runs with `--from-ref origin/main --to-ref HEAD`, so it checks only the files the
    branch changed, not the whole tree.
  - The command carries no `model:` frontmatter, so a caller that follows it inline runs it on its
    own model.
- **Test tiers.** `--no-cov` makes the exit code mean pass or fail: in a project whose `addopts`
  turns coverage on, any run smaller than the whole suite fails the coverage threshold whatever
  the test did. `scripts/select_tests.py` takes `--working-tree`, `--range`, `--upstream-range`,
  `--tests-changed-in` and `--wide`; a project extends it through `none`, `escalation`,
  `dependency_files`, `tooling`, `markers` and `narrow` in `[tool.test_tiers]`. `narrow` is off by
  default because it leaves links the import graph cannot see to a later full run, and a project
  without one would lose that check. `--wide` turns it off for one run, which is how a checkpoint
  selects. `--upstream-range <old>..<new>` (given once) names
  the paths another line of history brought in, such as main after a rebase: such a path counts only
  where it meets the branch: the apps it changed, the apps those import, the apps that import them,
  and the tests its own paths select. `pyproject.toml`, `uv.lock`, `.python-version`,
  `package.json` and `package-lock.json` are a separate dependency-file list, which
  `dependency_files` extends; a change to one forces `full` whichever side made it.
  An optional `[tool.test_tiers.remote]` table with a `command` runs every full tier somewhere
  else, such as in CI, with the local full command as the fallback:

  ```toml
  [tool.test_tiers.remote]
  command = "uv run python path/to/your_remote_runner.py"
  ```

  The command prints the runner's `run:` lines, `run: tested <sha>` and
  `run: RESULT PASS|FAIL|UNAVAILABLE`, and exits 0 only on `PASS`. Its failed tests are its
  `run: failed` lines. Any other key in the table belongs to the command, not to `ds`.
  `- Remote full run: off` under `## Test Tiers` in `.claude/ds/config.md` (or
  `config.local.md`, for one machine) skips it and runs the local full command;
  `DS_TEST_REMOTE=on|off` overrides that for one run. `DS_TEST_RECORD_PATH` names a
  file for `run_tests.sh` to keep its run record at, on every result, instead of a temporary file
  that a passing run deletes. The full contract is in `resources/test_tiers.md`.
- **Test runner.** `resources/test_runner.md` is the one file a workflow plugin points its test
  hook at. It takes a request in the caller's words (`change`, `everything`, `before landing`,
  `one test`, `failed`), maps it onto a tier, and returns one `tests:` line, so the caller never
  learns a tier name, a selector flag or a pytest command.
  `before landing` is the checkpoint. `scripts/full_run_record.py resolve` picks its tier in this
  order: a branch diff `origin/main..HEAD` that selects `none` runs nothing; no record, or a
  recorded commit that no longer resolves, runs `full`; otherwise the selector decides for
  `<record>..HEAD`, where a path main brought in counts only where it meets the branch.
  The full-run record is one file per branch, `.ds-work/full_run_record_<branch>.txt`, holding a
  commit SHA. It is gitignored and lives in the worktree. `test_runner.md` writes it after every
  full run, whoever asked. Only a passing full run on a clean tree writes it, and it names the
  commit the run started on. A failed, incomplete or skipped run writes nothing, and neither does
  a run during which another process committed to the branch, because that commit was never
  tested. A remote full run is recorded only when its `run: tested <sha>` line matches the commit
  noted before the run.
- **QA diff scoping.** A misclassification must over-test, never under-test, which is why anything
  unmatched is `FULL`.
- **Code comments.** A comment is a promise to the future reader that the code can't keep on its
  own. Most break it: they restate the code, narrate how it got written, or cite a document the
  reader doesn't have. Those comments rot, and rotten comments are worse than none, because the
  reader trusts them. A comment about the change instead of the code is stale the moment the next
  change lands, and a change narration means nothing once the diff is merged.
