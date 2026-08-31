# Implementation plan — deploy_prep_2

Implements `idea.md` and the gap list in `notes_from_infrastructrure_repo.md`, with the
adjustments the idea makes to FLS-03, FLS-04, FLS-09, FLS-10 and FLS-14. Read those two files
first; this plan does not restate their reasoning, only the order of work, the files touched and
the shape of each change.

Everything here is TDD where there is code to test: write the named tests first, watch them fail,
then write the code. One task at a time — do not write the whole test suite up front.

**Vocabulary note.** The `domain-glossary` skill has no word for a dev-only tooling app.
`dev_tools` is coined here (Task 7) and defined once: the app holding human-run demo and
destructive management commands, distinct from `qa_helpers`, which holds machine-run QA fixture
builders. Everything else in this plan uses existing FLS nouns.

---

## 0. Existing code and machinery this work must reuse

Nothing in this list gets reimplemented.

| Thing | Where | Used by |
| --- | --- | --- |
| `AppSettings` / `Setting` per-app settings base | `freedom_ls/base/app_settings.py` | Task 7 — the `dev_tools` gate |
| `DeploymentSettings` + `config` singleton, and the flat-constants module beside it | `freedom_ls/deployment/config.py`, `freedom_ls/deployment/settings_defaults.py` | Tasks 5, 6 |
| `AccountsConfig` + `config`, already declaring `TRUSTED_PROXY_IP_HEADER` | `freedom_ls/accounts/config.py:7,15` | Task 5 — the declaration stays, only the reader's behaviour changes |
| `build_logging_config(*, log_dir=None)` and its stdout-only default branch | `freedom_ls/deployment/settings_defaults.py:139` | Task 6 — the default branch already does the right thing |
| `configure_theme` prepending the theme's `templates/` to `TEMPLATES[0]["DIRS"]` via `setdefault("DIRS", [])` | `freedom_ls/base/theming.py:69-73` | Task 2 — proves an empty `DIRS` is safe |
| The `--yes` flag + `click.confirm` + pre-flight census idiom | `freedom_ls/content_engine/management/commands/danger_content_delete.py:22-68` | Task 7 — copy this shape onto the two commands that lack it |
| The module-level `pytest.skip` when an optional app is absent from `INSTALLED_APPS` | `freedom_ls/qa_helpers/tests/test_qa_create_report_cohort.py:16-17` | Task 7 — the pattern for `dev_tools` tests |
| `importlib.reload(importlib.import_module("config.settings_prod"))` with `HOST_DOMAIN`/`SECRET_KEY`/`WEBHOOK_ENCRYPTION_SALT` monkeypatched | `freedom_ls/deployment/tests/test_settings_defaults.py:213` | Tasks 5, 6 — the only way to assert on prod settings |
| `freedom_ls_deployment.E006`, which already forces axes and allauth onto the same header | `freedom_ls/deployment/checks.py:378-414` | Task 5 — context, no change |

### Facts verified in the tree, not assumed

- `pytest-playwright` supplies the `--tracing=retain-on-failure --screenshot=only-on-failure`
  flags in `addopts` (`pyproject.toml:79`). It is not optional at collection time: without the
  plugin **every** pytest run aborts on unrecognised arguments, not just the playwright tests.
  No CI workflow uses `--no-dev` or `--extra`, so moving it to the dev group breaks nothing.
- `pyproject.toml` carries **two** byte-identical dev lists — `[project.optional-dependencies]
  dev` (`:43-72`) and `[dependency-groups] dev` (`:121-146`). Both need the additions.
- Nothing in the repo parses `pyproject.toml`; there is no test asserting the dependency list.
- `/tmp/lms_templates` does not exist and nothing reads it. `configure_theme` `insert(0, ...)`s
  ahead of it and never inspects the existing contents.
- In production a client-IP header is **always** named: `settings_prod.py:126` defaults
  `TRUSTED_PROXY_IP_HEADER` to `fls_defaults.TRUSTED_CLIENT_IP_HEADER` = `"CF-Connecting-IP"`.
  So Task 5's fallback path is live on every production login today.
- `get_client_ip` has exactly two callers: `freedom_ls/accounts/forms.py:148` (LegalConsent on
  signup) and `AXES_CLIENT_IP_CALLABLE` (`config/settings_base.py:340`). It is not called on
  every request.
- `build_logging_config`'s `log_dir` branch sets `db_handlers = ["file"]` — dropping `log_dir`
  moves `django.db.backends` to console. That logger is pinned at `WARNING` and
  `propagate=False` (`settings_defaults.py:229-234`), so no SQL starts streaming to stdout.
- `freedom_ls.qa_helpers` is absent from `settings_base.py` and added only in
  `settings_dev.py:46-51`. It has `migrations/__init__.py` and no `models.py`.
- `danger_clear_all_course_progress` (`freedom_ls/learner_progress/`) and `create_demo_data`
  (`freedom_ls/learner_management/`) both ship in the production image today, both with no
  guard. `create_demo_data`'s own docstring calls itself "unsafe anywhere reachable over the
  network".
- Deleting the template manifest removes 100% of the FLS-03 surface: `project_setup` and
  `setup_initial_data` appear nowhere else in live code.
- `notify-downstream.yml` has no live dependants; `repository_dispatch` returns zero hits.
- The `.env.example` permission the idea asks for is **already in place** — see Task 4.
- `fls-content-plugin/` is untracked and absent from this worktree — see Task 12.

### Constraints that shape the code

- `T20` (flake8-print) is on: no `print()`. Use `click.echo` / `click.secho`.
- `S` (flake8-bandit) is on outside tests. Type hints on every function, no `Any`, no
  `# type: ignore` (`CLAUDE.md`).
- `pytest` runs with `--disable-socket` and `--cov-fail-under=73`.
- `mypy` runs with `warn_unreachable` and `check_untyped_defs`.

### Skills to consult while implementing

`ds:testing` + `fls-dev:testing` (every test task, and the `fls_internal` marker question in
Task 7) · `ds:app-settings` + `fls-dev:app-settings` (Task 7's setting) · `domain-glossary`
(Task 7's naming) · `code-comments` (every comment rewritten in Tasks 2, 5, 6) ·
`unslop` + `brand-guidelines` (Tasks 9, 10, 11) · `sdd:claude-code-authoring` (Task 3, editing
plugin commands and the SDD todo template) · `ds:app_map` (Task 7's final step).

No frontend is touched anywhere in this plan, so there is no QA plan.

---

## Task 1 — FLS-01: test dependencies out of the runtime dependency list

**Files:** `pyproject.toml`, `uv.lock`.

1. Delete `"pytest-env>=1.2.0"` and `"pytest-playwright>=0.7.2"` from `[project] dependencies`
   (`:18-19`).
2. Add both to `[project.optional-dependencies] dev` **and** to `[dependency-groups] dev`.
   Place them beside the other pytest entries in each list.
3. Run `uv lock` and commit the regenerated `uv.lock`. Confirm both packages now carry the
   dev marker rather than sitting in `freedom-ls`'s unconditional dependencies
   (`uv.lock:1034-1035`, `:1139,1141`).

No test to write — nothing in the repo reads `pyproject.toml`, and adding a dependency-list
assertion is new functionality nobody asked for. Verification is in §Verification below.

---

## Task 2 — FLS-02: drop `/tmp/lms_templates` from the template search path

**Files:** `config/settings_base.py`.

Replace the `DIRS` entry (`:172-176`) with `"DIRS": []`, dropping the commented-out
`# "DIRS": []` and `# BASE_DIR / "templates"` lines and the now-pointless `# noqa: S108`
/ `# nosec B108` suppressions with it.

Nothing else changes: `configure_theme` calls `setdefault("DIRS", [])` before inserting, and
`panel_framework/tests/conftest.py:153` splats the existing list.

**Test first:** in an existing `config`/theming test module, assert
`"/tmp" not in str(settings.TEMPLATES[0]["DIRS"])` — a plain regression guard against the entry
coming back. Keep it to one assertion.

---

## Task 3 — FLS-03: delete the template manifest and the command that reads it

The idea says the manifest goes and so do all references to it; the decision taken is that
`/fls-dev:update_template_repo` goes with it, since its Step 5 is entirely manifest-derived.

**Delete:**

- `claude_plugins/fls-dev/resources/template_repo_manifest.md`
- `claude_plugins/fls-dev/commands/update_template_repo.md`

**Edit:**

| File | What |
| --- | --- |
| `claude_plugins/fls-dev/README.md:62-63` | Drop `template_repo_manifest` from the FLS-specific resource list; change the "### Resources (11)" count to 10. Also fix the command roster near `:27,:30` — "Commands (10 files)" becomes 9, and the `update_template_repo` row goes |
| `claude_plugins/fls-dev/templates/config.local.md:6-13` | Remove the `## Template Repo` section. The file is then header-only — check whether `/fls-dev:init` still has anything to copy, and if not, delete the template and its copy step |
| `claude_plugins/fls-dev/commands/init.md:31, :267-269, :337` | Remove the template-repo path plumbing from Step 4 and the Step 9 summary. `:31`'s aside about where `.claude/settings.json` comes from names the template repo too — cut the attribution and keep the instruction |
| `claude_plugins/fls-dev/commands/update_product_docs.md:25` | The routing sentence loses one of three destinations |
| `claude_plugins/sdd/commands/README.md:16, :116-124` | Delete workflow item 10 and the whole `## Step 8.6` block; renumber the items and steps that follow |
| `claude_plugins/sdd/commands/protected/setup_todo_list.md:121-124` | Delete section `## 12. Template repo` and renumber 13→12, 14→13, 15→14 |
| `spec_dd/2. in progress/deploy_prep_2/todo.md:65-68` | This run's own todo carries the same step. Strike it with a one-line note saying the step was removed by this work, rather than ticking it |

**Before renumbering `setup_todo_list.md`,** grep `claude_plugins/sdd/` for hardcoded section
numbers — `setup_todo_list.md:47` says "Preserve the structure exactly — later commands and the
user both rely on it". Check `sdd/commands/next.md` and
`sdd/commands/protected/update_todo.md` for anything that matches on a number rather than a
title.

**`docs/product/deployment.md` names the template repo in seven places** (`:8`, `:9`, `:15`,
`:33`, `:66`, `:92`, `:114`). Those go too. `:15` and `:33` disappear with the sections Task 9
deletes; the survivors are handled in Task 9, which is the task that rewrites the file.

`spec_dd/1. next/mega-qa/research_downstream_qa_inheritance.md` and
`research_staging_reset_endpoint.md` lean on the manifest heavily. They are historical research,
not executable — leave them, but add one line to `spec_dd/1. next/mega-qa/`'s idea file noting
that the manifest they cite no longer exists.

---

## Task 4 — FLS-04: `.env.example`

**Files:** `.env.example`.

The idea's second bullet — "make sure claude can edit `.env.example` but no other `.env` file" —
is **already implemented** and needs verification, not change. `.claude/settings.json` denies the
exact basenames `Read(.env)` / `Edit(.env)`, and the two `PreToolUse` hooks (`:86-106`) deny
every other `.env.*` basename while `case`-exempting `.env.example`. The `_comment_env_files`
entry at `:5` explains why a glob deny cannot be used. Confirm by editing the file in step 1 and
leave the settings untouched.

Content fixes:

1. **Delete the `SENTRY_RELEASE=` line** and the two comment lines above it. An empty value in
   an `env_file` beats the image's build-time `ENV`, so that line blanks the release baked in at
   build and Sentry events stop mapping to a deploy.
2. **Unquote `HOST_DOMAIN`**: `HOST_DOMAIN=staging.freedomlearningsystem.org`. Values are written
   verbatim and compose strips no quotes, so the quotes become part of the value. Scan the whole
   file for any other quoted value and unquote those too.
3. **Add a header** at the top of the file saying, in two lines: values are literal — no quotes,
   no trailing whitespace — and the `# secret` / `# config` markers are documentation about the
   line below, never part of a value and never to be transcribed into a deployment's own
   variable store.
4. **Keep `AWS_STORAGE_BUCKET_NAME` and `AWS_S3_CUSTOM_DOMAIN`**, since this file also serves
   deployments outside the First Class fleet, but give each a one-line note saying it is
   deliberately left blank there and why (the existing comment block above
   `AWS_STORAGE_BUCKET_NAME` already half-says this; make it explicit for both).

`.env.example:38` links `docs/deployment-security-checklist.md` — re-check that link after
Task 10.

---

## Task 5 — FLS-05: a named client-IP header that is absent or malformed must fail loudly

**Files:** `freedom_ls/accounts/utils.py`, `freedom_ls/accounts/tests/test_utils.py`.

Today `get_client_ip` returns `REMOTE_ADDR` whenever the named header is absent or is not one
valid address. Behind the edge that is the proxy container's own address on the `edge` network:
the same value for every visitor, and a different one after the container is recreated. axes then
keys its lockout counter on it. allauth, handed the same header name, already raises rather than
falling back.

**Change:** when `config.TRUSTED_PROXY_IP_HEADER` names a header, that header is the only source.
Raise `django.core.exceptions.PermissionDenied` when it is absent or is not a single valid
address. Fall back to `REMOTE_ADDR` **only** when no header is configured, which is what keeps
this correct on a deployment with no proxy in front.

```
def get_client_ip(request):
    header_name = config.TRUSTED_PROXY_IP_HEADER
    if header_name:
        value = str(request.headers.get(header_name, ""))
        if not _is_ip_address(value):
            raise PermissionDenied(...)   # message names the header, not the value
        return value
    return str(request.META.get("REMOTE_ADDR", "") or "")
```

Do not put the header's value in the exception message — it is attacker-controlled and ends up in
logs. Name the header instead.

Rewrite the docstring: the paragraph starting "Falls back to REMOTE_ADDR then, and when no header
is configured or the named header is absent…" currently documents the bug as intended behaviour.

**Tests.** Three existing tests assert the behaviour being removed and must be inverted:

- `:56-67 test_get_client_ip_falls_back_when_header_carries_several_addresses`
- `:70-78 test_get_client_ip_falls_back_when_header_is_not_an_address`
- `:90-94 test_get_client_ip_falls_back_to_remote_addr_when_proxy_header_missing`

Rename each to say what it now asserts (`..._raises_when_...`) and assert
`pytest.raises(PermissionDenied)`. Add one asserting the exception message does not contain the
rejected header value. These stay valid unchanged: `:27`, `:34`, `:45`, `:81`, `:111`.

Also check `freedom_ls/accounts/tests/test_signup_form.py:151`, which sets
`TRUSTED_PROXY_IP_HEADER = None` — that path is unaffected, but confirm no other signup or axes
test sets a header without supplying it.

`settings_base.py:350` leaves `TRUSTED_PROXY_IP_HEADER = None`, so dev and the test suite are
unaffected by default.

> **Note for the implementer:** this makes a misconfigured edge return 403 on login and signup
> rather than locking every visitor out of one shared address. That is the intended trade. It
> also means a request that reaches the app container directly, bypassing the edge, is refused —
> which is the second reason for the change.

---

## Task 6 — FLS-06: production logs to stdout only

**Files:** `config/settings_prod.py`, `freedom_ls/deployment/settings_defaults.py`,
`freedom_ls/deployment/tests/test_settings_defaults.py`.

1. `config/settings_prod.py:92-95` → `LOGGING = fls_defaults.build_logging_config()`. Rewrite the
   comment above it: stdout only, capped by the container log driver. Drop the "temporary" and
   "once container-level caps exist" framing — the condition is met.
2. `settings_defaults.py:140-150` — rewrite `build_logging_config`'s docstring the same way. The
   `log_dir` parameter **stays**: it is a supported option for a deployment that wants files.
   What goes is the claim that omitting it "would relocate the disk-fill risk rather than
   removing it".
3. Keep the four tests that exercise the `log_dir` branch (`:127`, `:136`, `:144`, `:154`) — that
   branch is still supported.

**Test first:** add one test that reloads `config.settings_prod` (the
`importlib.reload` idiom at `test_settings_defaults.py:213`) and asserts no handler in
`LOGGING["handlers"]` has a `class` of `logging.handlers.RotatingFileHandler`.

Afterwards check `git ls-files logs` — if the `logs/` directory at the repo root is tracked or
gitignored solely for this, say so in the commit message; do not delete it as part of this task
unless it is empty and untracked.

---

## Task 7 — FLS-10: a `dev_tools` app for human-run demo and destructive commands

Three commands ship in the production image today with no guard at all. `qa_helpers` is the wrong
home for them: it holds machine-run QA fixture builders and is excluded from coverage on the
grounds that none of it runs in production. These are human-run, and one of them may be wanted on
staging.

**New app: `freedom_ls/dev_tools/`.** A coined name — see the vocabulary note at the top.
Structure follows `qa_helpers`: `__init__.py`, `apps.py` (with
`label = "freedom_ls_dev_tools"`, per the label convention the conformance suite's
`test_app_labels` enforces), `migrations/__init__.py`, `management/commands/`, `tests/`. No
models, so no migration is generated — confirm with `makemigrations --check --dry-run`.

**Move, unchanged except for the guard:**

| From | To |
| --- | --- |
| `freedom_ls/content_engine/management/commands/danger_content_delete.py` | `freedom_ls/dev_tools/management/commands/` |
| `freedom_ls/learner_progress/management/commands/danger_clear_all_course_progress.py` | `freedom_ls/dev_tools/management/commands/` |
| `freedom_ls/learner_management/management/commands/create_demo_data.py` | `freedom_ls/dev_tools/management/commands/` |
| `freedom_ls/learner_progress/tests/test_danger_content_delete.py` | `freedom_ls/dev_tools/tests/` (it was already in the wrong app) |

Command names do not change, so `.claude/settings.json:64-65`, `.claude/fls-dev/config.md:19`,
`.claude/fls-dev/scripts/install_dev.sh:19` and `claude_plugins/fls-dev/scripts/db_recreate.sh:7`
keep working with no edit. Verify each after the move.

Keep `danger_content_delete`'s `apps.get_model` indirection exactly as it is. `dev_tools` is a
leaf app nothing depends on, so it could import directly, but rewriting working code is not in
scope and the comment explaining the deletion order is load-bearing.

**The gate.** A per-app setting via the existing `AppSettings` / `Setting` pattern — read
`ds:app-settings` and `fls-dev:app-settings` before writing it.

- `freedom_ls/dev_tools/config.py` declares `DEV_TOOLS_ENABLED`, default `False`.
- `freedom_ls/dev_tools/guard.py` (or a `_guard` helper beside the commands) exposes one
  function that raises `CommandError` unless `settings.DEBUG` is true **or**
  `config.DEV_TOOLS_ENABLED` is true. The message says how to turn it on.
- Every command in the app calls it as its first statement.

Two deliberate acts are needed to run these outside development: install `freedom_ls.dev_tools`
in `INSTALLED_APPS`, and set `DEV_TOOLS_ENABLED`. That is the "clear way to turn them on" the
idea asks for, and it works for staging without loosening anything for production.

**Installation.** Add `"freedom_ls.dev_tools"` to `config/settings_dev.py`'s `INSTALLED_APPS`
block (`:46-51`), beside `qa_helpers`. Do **not** add it to `settings_base.py`.

**The missing prompts.** `danger_clear_all_course_progress` and `create_demo_data` get the
`--yes/-y` flag, the pre-flight census and the `click.confirm` prompt, copied from
`danger_content_delete.py:22-68`. `danger_clear_all_course_progress` should also wrap its five
deletes in `transaction.atomic()`, matching its sibling — as it stands a failure part-way leaves
progress half-deleted. Keep the existing deletion order; `danger_content_delete`'s comment cites
it by name.

**Tests** (`freedom_ls/dev_tools/tests/`), written first:

- The guard raises `CommandError` with `DEBUG=False` and `DEV_TOOLS_ENABLED` unset, for each of
  the three commands.
- The guard passes with `DEBUG=True`, and passes with `DEBUG=False` and `DEV_TOOLS_ENABLED=True`.
- `danger_clear_all_course_progress --yes` empties all five progress tables given a
  factory-seeded database, and leaves content intact.
- Without `--yes`, `click.confirm` is consulted and answering no deletes nothing. Mock
  `click.confirm`; do not let a test read stdin.
- The moved `test_danger_content_delete.py` still passes, with `--yes` and the guard satisfied.

Follow `qa_helpers/tests/test_qa_create_report_cohort.py:16-17` and skip at module level when
`"freedom_ls.dev_tools"` is not in `INSTALLED_APPS`, so a downstream running FLS's suite under
its own settings is unaffected. Read `fls-dev:testing` on whether these also want the
`fls_internal` marker — they exercise portable behaviour, so probably not, but the skill decides.

**Do not** add `*/dev_tools/*` to the coverage `omit` list (`pyproject.toml:95-102`). Unlike
`qa_helpers`, these are destructive commands a person runs by hand and they earn their coverage.
Confirm `--cov-fail-under=73` still passes after the move.

**Last step:** run `/ds:app_map` to regenerate `docs/app_structure.md` with the new app.

---

## Task 8 — FLS-09: delete `notify-downstream.yml`

**Files:** `.github/workflows/notify-downstream.yml` (delete).

A clean single-file removal — nothing references it, no other workflow depends on it, and
`repository_dispatch` appears nowhere in the repo.

Tell the user in the completion report that `FLS_NOTIFY_DOWNSTREAM_CROSS_REPO_TOKEN` is now an
orphaned cross-repo **write** token in the repository's Actions secrets, and should be revoked at
GitHub and deleted from the secret store. That is outside this worktree.

---

## Task 9 — FLS-07: cut `docs/product/deployment.md` back to what FLS requires of any host

**Files:** `docs/product/deployment.md`, plus the collateral listed below.

FLS is a library with more than one downstream. A target architecture, a VPS price list, a POPIA
residency argument and scale estimates belong to a deployment, and each of those now has a repo
that owns it. Every line that says "not yet built" is a status report on somebody else's work.

**Keep** (rewriting only where noted):

- The H1, the `_Last updated:_` line, and a rewritten `## Summary` — FLS is never deployed
  standalone; this page states what the application requires of a host, not how any particular
  host is built. `:8`'s clause naming the template repo as the owner of the Compose and
  reverse-proxy scaffolding goes with the rewrite.
- `## Background Tasks` (`:41-49`) — `fls_run_worker` and `fls_run_housekeeping` are application
  requirements. Unchanged.
- `## Application-Level Capabilities` (`:51-66`) — the substance of the page. Two edits: the
  final **Logging** paragraph must be rewritten after Task 6 (it currently says this repo's prod
  settings opt out of stdout-only and write rotating files, which stops being true), and it
  should stop asserting what "the template repo's reference configuration" pairs (`:66`) — say
  what the application does and that capping container logs is the deployment's job.
- `## Deploying a Concrete Project` (`:110-118`), trimmed: keep "never deployed standalone" and
  the conformance-suite advice. Delete `:114` entirely — the sentence exists only to name
  `git@github.com:preludetech/freedom-ls-concrete-template.git` and credit it with the Caddy and
  Compose scaffolding. Say instead what a concrete project *is* — a downstream repository that
  installs `freedom_ls` as a submodule and supplies its own settings, content and deployment
  scaffolding — without naming a repository to clone. FLS has more than one downstream, and
  which scaffold a given one starts from is not this page's fact to assert.
- The **First-run bootstrap** paragraph, with its last clause reversed. It currently advises
  putting `setup_initial_prod_data` in the deploy sequence. It prints a generated administrator
  password once, and an Actions log keeps whatever is printed into it — so the operator runs it
  by hand, once per stack. This is the first thing to fix in the file: it is advice rather than
  description, and following it puts a password in CI.

**Delete:** `## Target Architecture` (`:13-29`), `## Provisioning and CI/CD` (`:31-39`),
`## Backups` (`:68-72`), `## Scale Estimates` (`:74-84`), `## POPIA Data Residency`
(`:104-108`).

**Reduce** `## Operator Responsibilities` (`:86-102`) to the items true of any deployment —
patching, TLS somewhere in front, backups existing and tested, monitoring — with no Vultr, Caddy,
Let's Encrypt or Ansible specifics, no "planned" / "not yet built" status lines, and no mention
of "the template-repo stack" (`:92`). Point at `../deployment-security-checklist.md` for the
rest.

**When the section edits are done,** `grep -in "template" docs/product/deployment.md` must come
back empty. That is the check on this file; the collateral below is separate.

**Collateral, same task:**

| File | Line | What |
| --- | --- | --- |
| `docs/product/README.md` | `:40` | The Deployment row still describes "Vultr Johannesburg VPS, Docker Compose with Caddy, Gunicorn, and PostgreSQL". Rewrite to match the trimmed page |
| `docs/product/*.md` | — | `grep -rin "template repo\|freedom-ls-concrete-template" docs/` and clear whatever else it finds. `configuration-and-extension.md` is the likely other holder |
| `docs/product/security-and-data-handling.md` | `:116` | "TLS terminates at the reverse proxy (or the CDN edge) using **Let's Encrypt** certificates" — this fleet uses a Cloudflare Origin CA certificate from the vault and every record is proxied and Full (strict), so an HTTP-01 challenge cannot complete. Say the deployment supplies the certificate; do not name an issuer |
| `docs/product/roadmap.md` | — | Check for duplicated "Ansible not yet built" / "Cloudflare planned" status claims and remove them |

Then walk every inbound link and confirm it still resolves to a section that exists:
`docs/product/README.md:13,:40` · `webhooks.md:66` · `reports.md:58,:82` ·
`configuration-and-extension.md:108,:138,:139,:147` · `security-and-data-handling.md:58,:84,
:130,:140,:178,:189` · `deployment-security-checklist.md:7,:220`.

Match the house style of `docs/product/`: H1, `_Last updated: YYYY-MM-DD_` on line 3, prose over
bullet fragments, British spelling, relative sibling links. Apply `unslop` and
`brand-guidelines` before finishing.

---

## Task 10 — FLS-08: mark the checklist's three topology-dependent items

**Files:** `docs/deployment-security-checklist.md`.

A checklist a correct deployment fails teaches operators to skip lines. Three items read as
failures on this topology and only one is a real gap.

| Line | Item | What to say |
| --- | --- | --- |
| `:24` | "Application uses a dedicated database user (not the superuser)" | Depends on topology. For the same-host containerised Postgres this project ships, the official image runs `initdb --username="$POSTGRES_USER"`, so the application's role **is** the cluster superuser by construction, and the backup path authenticates as that role over the container's local socket — which is what keeps the password off a command line `ps` would show. A separate application role breaks the backup. The item stands for an external or managed database |
| `:86` | "SSH port (22) is restricted to known admin IPs or VPN" | Depends on topology. A fleet whose operators have no fixed address leaves SSH reachable behind key-only authentication and `fail2ban` instead. Say what the substitute controls are, so the line is answerable either way |
| `:101` | "Centralized logging is configured (e.g., ELK, CloudWatch, Datadog)" | Depends on topology. Errors go to Sentry and container logs are capped at the log driver; a two-box fleet with no aggregator satisfies this differently. Note that Task 6 makes stdout the only sink |

Keep the file security-only. Commit `b58594d8` deliberately moved operational material out to
`docs/product/deployment.md` two commits ago, and `:5-9` asserts that boundary — these
annotations are security rationale, not operations, so they belong here. Do not reintroduce a
deploy sequence or a monitoring section.

Section numbers have already shifted once, and
`freedom_ls/accounts/management/commands/build_legal_docs_manifest.py:15` cites "section 10" by
number. Do not renumber; if you do, fix that citation and the `§` references in
`docs/product/security-and-data-handling.md:28,:68,:70,:116,:124`.

---

## Task 11 — FLS-12: the dead install doc

**Files:** `docs/install.md` (delete).

`docs/install.md` is zero bytes and nothing links to it — not `README.md`, not `CLAUDE.md`, not
anything under `docs/` or `claude_plugins/`. Delete it.

The other half of FLS-12 — the link to `docs/how tos/incorporate into another project.md`, which
does not exist — is at `template_repo_manifest.md:13` and disappears with Task 3. Confirm after
Task 3 that no live reference to that path remains.

While here: `CLAUDE.md:73` references `docs/templates_and_cotton.md`, which does not exist
either. The live document is `claude_plugins/fls-dev/resources/templates_and_cotton.md`. Fix the
reference.

---

## Task 12 — FLS-11: `fls-content-plugin/` (no commit)

`fls-content-plugin/` is **untracked** and absent from this worktree. It survives in the `main`
worktree at `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-content-plugin/`, holding
four directories and two stale `.pyc` files left by the `split-claude-plugin` rename.

There is nothing to commit. Report it as a manual `rm -rf` for the user to run in the `main`
worktree, and suggest checking the other worktrees for the same leftover. `claude_plugins/
fls-content/validate/` is confirmed live and referenced by `pyproject.toml:78,200,202,277` and
`.pre-commit-config.yaml:55-57`; nothing points at the old path.

---

## Task 13 — FLS-14: record the decision, change nothing

**Files:** `config/settings_base.py` (comment only).

The idea settles the open question: `AXES_LOCKOUT_PARAMETERS` keeps both the bare `"username"`
rule and `[["ip_address", "username"]]`. Extend the existing comment above `:331` by one sentence
recording that the flat rule is deliberate and why — allauth's `login_failed` rate limit wraps
allauth's own login view and not `/admin/login/`, so without it a spray that rotates source
addresses against one administrator account is capped by nothing. No code changes.

---

## Verification

Run from the worktree root. Nothing here is manual browser QA — this change set has no frontend.

**Full suite, twice.** `uv run pytest` after each task, and once at the end. `pytest-randomly`
is installed, so a second full run at a different seed is worth it after Task 7's file moves.

**Task 1 — the dependency split is real, not just textual:**

```
uv sync --no-dev --reinstall
uv pip list | grep -Ei 'pytest|playwright'      # expect: nothing
uv sync                                          # restore the dev environment
uv run pytest -m "not playwright" -x -q          # the suite still collects
uv run pytest -m playwright --no-cov             # after: uv run playwright install --with-deps chromium
```

The `--no-dev` run is the closest stand-in available for the contract's
`docker run --rm <image> pip list`, since this repo ships no Dockerfile by design.

**Task 2:** `uv run python manage.py shell -c "from django.conf import settings;
print(settings.TEMPLATES[0]['DIRS'])"` under dev settings — expect the theme directory only, no
`/tmp` entry. Then load any page in the dev server to confirm templates still resolve.

**Task 3:** `grep -rn "template_repo_manifest\|update_template_repo" . --exclude-dir=.git
--exclude-dir=".venv"` returns hits only under `spec_dd/`. Start a fresh Claude session and
confirm `/fls-dev:` no longer offers the removed command.

**Tasks 5 and 6 — against real production settings:**

```
DJANGO_SETTINGS_MODULE=config.settings_prod \
HOST_DOMAIN=example.test SECRET_KEY=x WEBHOOK_ENCRYPTION_SALT=y \
  uv run python manage.py check --deploy
```

Expect `freedom_ls_deployment.E006` to stay silent (axes and allauth still agree on the header)
and no new error. The reload-based unit tests are the primary assertion for both.

**Task 7:**

```
uv run python manage.py makemigrations --check --dry-run     # expect: no changes
uv run python manage.py danger_clear_all_course_progress --yes   # dev: runs
uv run python manage.py create_demo_data                          # dev: prompts
DJANGO_SETTINGS_MODULE=config.settings_prod ... uv run python manage.py help
  # the three commands are absent — dev_tools is not installed
```

Then run `.claude/fls-dev/scripts/install_dev.sh` end to end on a fresh branch database and
confirm `create_demo_data` still seeds it, and `/fls-dev:do_qa`'s content-reset rung
(`danger_content_delete --yes`, `.claude/fls-dev/config.md:19`) still works.

**Tasks 9, 10, 11 — links:** run a markdown link check over `docs/` (or grep each relative link
and stat the target) and confirm every inbound link listed in Task 9 still resolves.

**Whole change set:** `uv run pre-commit run --all-files` — it carries ruff, djlint, mypy,
bandit and detect-secrets, and Task 4 edits a file detect-secrets watches closely.

---

## Out of scope, deliberately

- Any new dependency-manifest assertion test (Task 1) — nothing in the repo parses
  `pyproject.toml` today and none was asked for.
- A `check --deploy` error for `dev_tools` being installed in production (Task 7). The
  `CommandError` guard is sufficient; a system check is a second mechanism for the same rule.
- Removing `build_logging_config`'s `log_dir` parameter (Task 6). It is a supported option for a
  deployment that wants files; only FLS's own prod settings stop using it.
- Anything in `/home/sheena/workspace/first_class/infrastructure` or the template repo at
  `/home/sheena/workspace/lms/freedom-ls-concrete-template`. Both are separate repositories.
