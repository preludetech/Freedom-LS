# Research: `setup_initial_prod_data` — what it replaces and what binds on it

Scope: the operator-run first-deploy bootstrap command named by `CI-18` in the infra repo's
`docs/app_repo_contract/deploy_ci.md`. FLS will ship a management command named exactly
`setup_initial_prod_data`; `create_site.py` and `create_site_superuser.py` are deleted. This file
does not re-argue those decisions — it reports what they require and what they break.

## 1. Every reference to `create_site` / `create_site_superuser`

Repo searched: whole tree, excluding `.git`, `node_modules`, `spec_dd/3. done/`.

**Code (non-spec):**
- `freedom_ls/site_aware_models/management/commands/create_site.py` — the command itself (deleted
  by this work).
- `freedom_ls/site_aware_models/management/commands/create_site_superuser.py` — zero bytes, no
  `Command` class, so Django registers nothing under this name today; `manage.py
  create_site_superuser` already reports "Unknown command" (deleted by this work).
- `freedom_ls/organisations/signals.py:50` — a docstring comment naming `create_site` as one of
  several call sites the signal-based design deliberately does not special-case (detail in §2
  below). No import, no call — this is prose inside a docstring, not a code dependency. Nothing
  here breaks when `create_site.py` is deleted.

**No other reference anywhere in `docs/`, `README.md`, `install_dev.sh`, `.claude/` (outside the
one memory file below), or `claude_plugins/`.** Grep for `create_site` in each of those roots
returned zero matches except:
- `.claude/agent-memory/fls-dev-qa-data-helper/reference_second_text` — false positive: this is
  `qa_create_site_scoping_form`, an unrelated QA fixture command (see §7), matched only because the
  substring `create_site` appears inside its longer name. No action needed.

**No test file anywhere in the repo calls `create_site` or `create_site_superuser` via
`call_command`.** A repo-wide grep restricted to `**/tests/**` for `create_site` returned no
matches. Neither command has ever been under test.

**`spec_dd/2. in progress/` (in scope, not excluded):**
- `spec_dd/2. in progress/prepare-to-deploy/create-site-superuser-command-file-is-empty/idea.md`
  — the idea document that originated this decision; full text read (see below).
- `spec_dd/2. in progress/more-testing-skills/research_testing_management_commands.md:166,228,297`
  — inventories both commands as djclick, `get_or_create`-based, and untested; flags them as "good
  idempotency-test candidates" and recommends them as a worked example for a *future* testing
  skill. That skill work has not landed; nothing currently depends on these commands existing for
  test-writing purposes. Note this file still uses the pre-rename vocabulary ("student" instead of
  "learner") in places — a documentation artifact, not a code dependency.

**`spec_dd/3. done/` (out of scope per the prompt, listed here only for completeness since the
grep surfaced it):** `2026-06-10_12:07_product-documentation/research_codebase_features.md:375`
and five files under `2026-08-21_09:09_organisations/` reference `create_site.py` extensively —
that spec is what added the `organisations/signals.py` receiver *instead of* editing
`create_site.py` (see §2). All of that work is already merged; none of it is reopened by this
deletion. `2026-08-23_17:20_learners-associated-with-organisations/research_codebase_impact.md`
also references it, describing the same completed decision.

**Sibling template repo** (`/home/sheena/workspace/lms/freedom-ls-concrete-template/`, readable):
- `apps/project_setup/management/commands/setup_initial_data.py` — a downstream-owned command,
  **not named `setup_initial_prod_data`** and **not calling FLS's `create_site`**. It duplicates
  the site+admin-creation logic locally (full read in §5/§7 below). It has no dependency on either
  deleted command, so nothing there breaks.
- `submodules/Freedom-LS/spec_dd/3. done/2026-06-10_12:07_product-documentation/
  research_codebase_features.md:375` — a vendored copy of the same completed spec doc found above,
  via the git submodule pointer. Same non-issue.

**Downstream fleet repo** (`/home/sheena/workspace/first_class/`, readable): a `create_site` /
`setup_initial_prod_data` grep across the whole tree returns ~44 hits, but they fall into three
buckets, none of which is a live dependency on the two files being deleted:
1. Multiple **stale worktree copies** of this same FLS repo's own `spec_dd/` and
   `.claude/agent-memory/` (`First-Class-LMS.git/prepare-to-deploy/submodules/Freedom-LS/...`,
   `First-Class-LMS.git/main/submodules/Freedom-LS/...`, `First-Class-LMS/submodules/Freedom-LS/...`)
   — these are git-submodule snapshots of FLS at older commits, already covered by the buckets
   above.
2. The downstream's own `apps/project_setup/management/commands/setup_initial_data.py` (three
   copies, one per worktree/branch: `prepare-to-deploy`, `main`, and the bare `First-Class-LMS/`
   checkout) — the same file described above; it does not import from FLS.
3. Infra-repo and app-repo-contract docs (`deploy_ci.md`, `README.md`,
   `running-how-to/run-a-management-command.md`, `setup-how-to/14-hand-off-to-the-app-repos.md`,
   the `.plans/` idea/plan files for `ci4-has-no-first-deploy-bootstrap-step`) — these describe the
   contract (`CI-18`) itself and the FLS-side idea doc
   (`First-Class-LMS.git/prepare-to-deploy/spec_dd/for_freedom_ls/prepare_to_deploy/
   create-site-superuser-command-file-is-empty/idea.md`, a synced copy of the idea doc already read
   in this repo). No executable dependency.

**Net effect:** deleting both files breaks nothing that currently runs — no test, no CI step, no
downstream import. The only things that reference them are prose (a docstring comment, spec
history, and idea docs) and one already-completed spec (`organisations`) whose implementation
deliberately routed around `create_site.py` rather than through it.

## 2. What `create_site` does that a replacement must carry over

Full text read at `freedom_ls/site_aware_models/management/commands/create_site.py`:

```python
site, _created = Site.objects.get_or_create(
    name=site_name,
    defaults={"domain": site_domain},
)
if site.domain != site_domain:
    site.domain = site_domain          # <-- reassigned, never saved

user_email = email if email else f"{site_name.lower()}@email.com"
user_password = password if password else user_email   # <-- password == email when omitted

user, user_created = User.objects.get_or_create(
    email=user_email,
    defaults={"is_staff": True, "is_superuser": True, "is_active": True, "site": site},
)
if user_created:
    user.set_password(user_password)
    user.save()

EmailAddress.objects.get_or_create(
    user=user, email=user.email, defaults={"verified": True, "primary": True}
)
```

Behaviours the replacement must carry over or deliberately supersede:

- **Confirmed real bug** (`create_site.py:21-22`): `get_or_create` keys on `name`, not `domain`.
  For a `Site` row that already exists under that name, the branch reassigns `site.domain` in
  memory and never calls `.save()`. Re-running the command to correct a domain typo prints nothing
  and changes nothing on disk. This is already documented as an "adjacent, do not fix here" defect
  in the completed `organisations` spec (`spec_dd/3. done/2026-08-21_09:09_organisations/
  1. spec.md:1093`) — it was explicitly left alone there because that spec's scope was the
  Organisation receiver, not `create_site.py` itself. It is now moot: the file is deleted, not
  patched, so whatever `setup_initial_prod_data` does for the `Site` row must key its own
  `get_or_create`/lookup correctly rather than inherit this bug.
- **The `EmailAddress` row.** `create_site.py` creates one allauth `EmailAddress` per user, with
  `verified=True, primary=True`. This is load-bearing (see §5): without it the account cannot pass
  allauth's login flow under `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (per `CI-18`'s own text —
  "no verification mail leaves the box" / "a stack nobody can sign up on").
- **`is_staff`/`is_superuser`/`is_active` all set True** on the created user, and `site` set to the
  just-created (or looked-up) `Site`.
- **What is *not* carried over, by design:** the "password defaults to the email address" fallback.
  `CI-18` requires the command to *generate* the password and print it once — `create_site.py`'s
  `user_password = password if password else user_email` behaviour is exactly the anti-pattern
  `CI-18` rules out (a guessable, non-random credential with no print-once semantics).

**`freedom_ls/organisations/signals.py:44-73`** — the receiver and post-migrate hook:

```python
@receiver(post_save, sender=Site)
def ensure_default_organisation(sender, instance, **kwargs):
    _ensure_default_organisation(instance)
```

- Fires on **every** `Site.save()`, regardless of caller — the docstring at
  `signals.py:44-53` states this explicitly: "A receiver rather than an edit to create_site so
  site_aware_models keeps its zero outgoing edges, and so the admin, the shell and SiteFactory are
  covered too." So **it fires unconditionally for whichever command creates the `Site` row**,
  `setup_initial_prod_data` included — no special-casing needed, and none should be added.
  `_ensure_default_organisation` (`signals.py:14-41`) is `get_or_create` keyed on
  `(site, is_default=True)`, seeded from `site.name`, using `Organisation._base_manager` (not the
  site-scoped manager) specifically so a re-save under a different ambient site does not miss the
  existing row and attempt a duplicate insert.
- **One case this receiver does not cover:** the migration-time default `Site(pk=1,
  domain="example.com")`. `ensure_default_organisations_after_migrate` (`signals.py:57-73`) exists
  *only* to backfill that one row, because `django.contrib.sites`'s own `post_migrate` hook fires
  its `post_save` signal with the historical (migration-state) model as sender, which does not
  match `sender=Site` in the `@receiver` decorator above. This is irrelevant to
  `setup_initial_prod_data` itself (it runs long after migrate, against the real model), but
  confirms: **any `Site` row `setup_initial_prod_data` creates or looks up via the real
  `django.contrib.sites.models.Site` class will trigger the receiver and get a default
  Organisation for free** — no explicit Organisation-creation step is needed in the new command.

## 3. Command-name shadowing — `get_commands()` resolution, confirmed from source

Read directly from the installed Django 6.0.4 (`.venv/lib/python3.13/site-packages/django/`,
confirmed version at `django/__init__.py:3`: `VERSION = (6, 0, 4, "final", 0)`).

`django/core/management/__init__.py:53-80`:

```python
def get_commands():
    commands = {name: "django.core" for name in find_commands(__path__[0])}
    if not settings.configured:
        return commands
    for app_config in reversed(apps.get_app_configs()):
        path = os.path.join(app_config.path, "management")
        commands.update({name: app_config.name for name in find_commands(path)})
    return commands
```

`apps.get_app_configs()` yields configs in `INSTALLED_APPS` order. The loop iterates
`reversed(...)`, so it visits the **last**-listed app first and the **first**-listed app last.
`dict.update()` overwrites on key collision, and the last write for a given command name wins — so
the app that appears **earliest in `INSTALLED_APPS`** is processed last in this loop and ends up
owning that command name in the returned `{command_name: app_name}` map. Confirmed against
Django's own how-to docs (`docs.djangoproject.com/en/6.0/howto/custom-management-commands/`):
"Django registers the built-in commands and then searches for commands in `INSTALLED_APPS` in
reverse. During the search, if a command name duplicates an already registered command, the newly
discovered command overrides the first." That page also gives the override recipe: to reclaim a
shadowed command, a downstream app must be listed *before* the app whose command it wants to
override, and can explicitly `import` the shadowed `Command` class under a new name.

**Consequence:** if FLS ships `setup_initial_prod_data` and a downstream project's own app also
defines a command of that exact name, `get_commands()` builds one flat name-to-app map with no
duplicate-name warning printed anywhere — whichever of the two apps sits earlier in
`INSTALLED_APPS` silently wins, and `manage.py setup_initial_prod_data` runs only that one
implementation.

Sources:
- [Django 6.0 docs — How to create custom django-admin commands, "Overriding commands"](https://docs.djangoproject.com/en/6.0/howto/custom-management-commands/)
- `.venv/lib/python3.13/site-packages/django/core/management/__init__.py:53-80` (installed Django
  6.0.4 source, this repo)

## 4. Password generation and print-once

- `BaseUserManager.make_random_password()` **does not exist in this repo's installed Django**. A
  grep for `make_random_password` across `.venv/lib/python3.13/site-packages/django/` returns zero
  matches. It was deprecated in Django 4.2 and removed in Django 5.1 (confirmed via the removal
  commit, `django/django@f2d9c76`, "Refs #33764 -- Removed BaseUserManager.make_random_password()
  per deprecation timeline"), so it is unavailable on Django 6.0.4, which this repo runs. Any
  reference to it as a solution is a dead end.
- Django's own 4.2 release notes, at the point of deprecating it, pointed developers at "Python's
  `secrets` module... for using `secrets` module to generate passwords," citing [Python's `secrets`
  module recipes and best practices](https://docs.python.org/3/library/secrets.html#recipes-and-best-practices).
- `django.utils.crypto.get_random_string` still exists and is the idiomatic in-framework choice
  (`.venv/lib/python3.13/site-packages/django/utils/crypto.py:51-62`):

  ```python
  RANDOM_STRING_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

  def get_random_string(length, allowed_chars=RANDOM_STRING_CHARS):
      return "".join(secrets.choice(allowed_chars) for i in range(length))
  ```

  It is itself implemented on top of `secrets.choice`, i.e. cryptographically strong. Its own
  docstring gives the bit-strength math: default 62-character alphabet, `length=12` ≈ 71 bits,
  `length=22` ≈ 131 bits — useful for picking a length that reads as "strong" for an administrator
  credential.
- **Print-once / no double-logging.** `CI-18`'s own text is explicit that the reason this step is
  operator-run rather than CI-run is exactly this: "A GitHub Actions log keeps whatever is printed
  into it, and keeps it long after the deploy is forgotten." The corollary for the command itself:
  whatever channel it prints the password on (stdout) must not also pass through anything that
  persists — no `logging` call with the password in it (project convention already forbids adding
  logging unless asked, per `CLAUDE.md`), and nothing written to a file or the database in
  plaintext. The password must exist in exactly one place after the command exits: the operator's
  terminal scrollback, which `CI-18` also says not to keep ("Do not keep it in a note or a password
  manager either").

Sources:
- [Django 4.2 release notes — `make_random_password()` deprecation](https://docs.djangoproject.com/en/4.2/releases/4.2/)
- [`django/django@f2d9c76` — removal commit](https://github.com/django/django/commit/f2d9c76aa7096ef3eed675b9eb824858f9dd81e5)
- [Python `secrets` module — recipes and best practices](https://docs.python.org/3/library/secrets.html#recipes-and-best-practices)
- `.venv/lib/python3.13/site-packages/django/utils/crypto.py:48-62` (installed Django 6.0.4
  source, this repo)

## 5. The FLS user model — what creating a superuser requires

Full text read at `freedom_ls/accounts/models.py`.

- **`site` is a required FK**, inherited via `SiteAwareModelBase` (`freedom_ls/site_aware_models/
  models.py:53-54`: `site = models.ForeignKey(Site, on_delete=models.PROTECT)`, non-nullable). A
  management command has no request, so nothing infers this automatically — it must be passed
  explicitly on `User(...)` construction, exactly as `create_site.py:33` and the sibling
  downstream's `setup_initial_data.py:53` both already do (`site=site`).
- **Login is email-based.** `USERNAME_FIELD = "email"` (`accounts/models.py:77`), `email =
  models.EmailField(unique=True)` (`:68`). There is no `username` field to populate (a
  `username` *property* exists purely for template compatibility, returning `self.email`,
  `:84-87`).
- **`is_staff` / `is_superuser`** are plain `BooleanField`s (`:74-75`), both default `False`. The
  manager's `create_superuser` (`accounts/models.py:57-64`) sets `is_staff=True` and (via its
  `is_admin` parameter) `is_superuser=True`.
- **The manager's `create_superuser` signature** (`accounts/models.py:57-64`):

  ```python
  def create_superuser(self, email, password=None):
      user = self.create_user(email, password=password, is_staff=True, is_admin=True)
      return user
  ```

  Note the parameter is named `is_admin` on `create_user` (`:34-41`) but maps to `is_superuser` on
  the instance (`:52`) — a naming quirk to be aware of if a new command calls `create_user`
  directly rather than `create_superuser`. `create_user` requires both `email` and a non-empty
  `password` (`:42-45`, raises `ValueError` on either being falsy) and does **not** take `site` as
  a parameter at all — the caller must set `user_obj.site = ...` and save, or construct the model
  instance directly (as `create_site.py` and the template's `setup_initial_data.py` both do,
  bypassing the manager's `create_user`/`create_superuser` entirely and calling `User(...)` +
  `.set_password()` + `.save()`).
- **An allauth `EmailAddress` row is required for the account to be usable**, per `CI-18`'s own
  text: `ACCOUNT_EMAIL_VERIFICATION` is `"mandatory"`, so without a `verified=True, primary=True`
  `EmailAddress` row, the created administrator cannot complete allauth's login flow through the
  FLS frontend at all (creating the `User` row alone is not sufficient — this is exactly what both
  `create_site.py:41-43` and the downstream's `setup_initial_data.py:67-71` already do, via
  `EmailAddress.objects.get_or_create`/`update_or_create`).
- **Default Organisation for a fresh tenant:** confirmed in §2 — nothing beyond the `Site` row is
  needed. `freedom_ls/organisations/signals.py`'s `post_save` receiver on `Site` (and the
  `post_migrate` hook for the migration-created row) guarantees every `Site` carries a default
  `Organisation`, unconditionally and automatically, regardless of which code path created or
  looked up the `Site`. No explicit Organisation step belongs in `setup_initial_prod_data`.

## 6. Idempotency — what "safe to run twice" means here concretely

Against these specific models:

- **`Site`**: a lookup-or-create keyed on the field the operator actually has to hand —
  `CI-18` says the command reads `HOST_DOMAIN` from the rendered `.env` (via a command-line
  argument, per the idea doc's stated preference — see §1's idea-doc read — not an env var read
  inside the command itself). The natural key is therefore `domain`, not `name`
  (unlike `create_site.py`'s buggy `name`-keyed lookup, §2). A `get_or_create(domain=...)` (or
  equivalent lookup + explicit `.save()` on any correction) avoids `create_site.py`'s "reassign but
  never save" bug outright, because there is nothing to reassign — the lookup key *is* the field
  that would otherwise need correcting.
- **`User`**: lookup by `email` (the unique, `USERNAME_FIELD` column). If found, **do not touch
  `set_password`** on the second run — this is `CI-18`'s explicit binding property: "It is safe to
  run again, and it never resets a password that already exists. Somebody will run it twice. A
  command that silently rotates a live administrator's credential is worse than the gap it closes."
  Concretely: only call `.set_password(...)` and print a credential inside the branch where the
  `User` row did not already exist; an already-existing `User` gets no new password generated and
  nothing printed for it.
- **`EmailAddress`**: `get_or_create`/`update_or_create` keyed on `(user, email)`, same idiom
  `create_site.py:41-43` already uses — safe to call unconditionally on every run, including the
  second one, because it converges on the same `verified=True, primary=True` state either way and
  never touches a password.
- **`Organisation`**: nothing to do — the `post_save` receiver already handles this idempotently
  (§2), independent of how many times `setup_initial_prod_data` runs or whether it runs at all
  after the first `Site` save.
- **Never-reset-password mechanically:** the only safe pattern is "generate and set the password
  exactly once, at the same moment the `User` row is first inserted" — i.e. inside the `created`
  branch of a `get_or_create`/`filter().first() is None` check, never in a branch that runs
  regardless of whether the row was just created. `create_site.py:37-39` already has this shape
  right (`if user_created: user.set_password(...); user.save()`); the defect there was `Site`'s
  lookup key, not `User`'s.

## 7. House conventions — how FLS writes and tests management commands

Confirmed by reading `freedom_ls/*/management/commands/*.py` directly (35 files, excluding
`__init__.py`; matches the existing inventory in
`spec_dd/2. in progress/more-testing-skills/research_testing_management_commands.md:151-236`,
already surveyed there in detail):

- **Two styles coexist.** The overwhelming majority (33 of 35, including the deleted
  `create_site.py`) use **`djclick`** (`import djclick as click`, `@click.command()`,
  `click.argument`/`click.option`, `click.echo`/`click.secho` for output, `raise
  click.ClickException(...)` for user-facing errors). Exactly two files use plain
  **`django.core.management.base.BaseCommand`**: `freedom_ls/accounts/management/commands/
  build_legal_docs_manifest.py` and `freedom_ls/base/management/commands/
  write_active_theme_css.py` (both confirmed by direct grep for `from django.core.management.base
  import BaseCommand` — only these two files matched).
- **The house "thin handle" idiom**, best demonstrated at
  `freedom_ls/role_based_permissions/management/commands/sync_role_permissions.py`: the
  `@click.command() def command(...)` body is a short sequence of calls into private
  `_helper()` functions that hold all the actual logic (`_ensure_permissions_exist`,
  `_sync_object_assignments`, `_sync_site_assignments`, `_report_orphans`, etc., all module-level
  and independently testable/importable). This is the pattern the testing-skill research file
  flags as "the skill's canonical 'how FLS already does this well' example"
  (`research_testing_management_commands.md:240-244`) and as the opposite of
  `recalculate_progress_percentages.py`'s "everything inline in `handle()`" anti-pattern.
- **Testing idiom, confirmed by reading `freedom_ls/role_based_permissions/tests/
  test_management_commands.py` directly:** djclick commands are invoked via
  `django.core.management.call_command(...)`, output is captured with
  `contextlib.redirect_stdout(io.StringIO())` (not `call_command(..., stdout=...)`, because djclick
  writes via `click.echo()` straight to real `sys.stdout`, bypassing any `stdout=` kwarg), and
  user-facing failures are asserted with `pytest.raises(click.ClickException, match=...)` — **not**
  Django's `CommandError`, since djclick raises its own exception type. A plain `BaseCommand`
  command, by contrast, would use `call_command(..., stdout=StringIO())` directly and assert
  `pytest.raises(django.core.management.base.CommandError, ...)`.
- **Neither deleted command was ever tested.** No `call_command` reference to `create_site` or
  `create_site_superuser` exists anywhere in the repo (§1). The testing-skill research file
  independently flags both as good idempotency-test candidates that were never written
  (`research_testing_management_commands.md:296-297`).
- **A concrete downstream precedent exists for this exact job.** The sibling template repo's
  `apps/project_setup/management/commands/setup_initial_data.py` (full text read, §2/§5) is a
  plain `BaseCommand` (not djclick) that does the same three things `setup_initial_prod_data` needs
  to do — `Site.objects.get_or_create(...)`, a `User` lookup-or-create with an explicit `site=`
  kwarg, and `EmailAddress.objects.update_or_create(...)` — but it is explicitly a **development**
  command: it hardcodes `SITE_DOMAIN = "127.0.0.1:8000"` and `ADMIN_PASSWORD = "admin@email.com"`  <!-- pragma: allowlist secret -->
  at module level rather than generating and printing a password, and its own comment says "change
  the admin password before exposing the project publicly." It is evidence of the downstream's
  independently-arrived-at shape for this job (useful precedent for the FK/`EmailAddress`
  mechanics), not a template to copy for the production-safe parts (`CI-18`'s
  generate-and-print-once and never-reset-a-password properties are exactly what this dev command
  does not do).

status: ok
