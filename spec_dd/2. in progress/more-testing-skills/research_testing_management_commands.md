# Research: Testing Custom Django Management Commands

Scope: `manage.py <command>` custom commands in FLS. Stack: Python 3.13+, Django 6.x,
pytest + pytest-django. FLS uses **both** plain `django.core.management.base.BaseCommand`
and **djclick** (`import djclick as click`) commands — this matters a lot for the skill
(see Part B).

---

## PART A — External best practices

### 1. `call_command()` is the canonical invocation method in tests

Django's own docs for `django.core.management.call_command()` (Django 6.0 `django-admin`
reference) are the primary source:

- Signature: `call_command(name, *args, **options)`.
- `name` is preferred as a string (command name), not an imported `Command` object, unless
  you specifically need the object for a test.
- **Positional `*args` go through the argument parser**, so they behave like CLI strings —
  e.g. `call_command("flush", "--verbosity=0")` converts `"0"` to `int` automatically.
- **Keyword `**options` bypass the argument parser entirely** — you must pass the *actual*
  Python type the option expects, e.g. `call_command("flush", verbosity=0)` (int, not
  `"0"`), `call_command("dumpdata", exclude=["contenttypes", "auth"])` (list), or
  `call_command("flush", interactive=False)` (bool).
- To find the correct keyword name for `**options`, check the command's `add_arguments()` /
  `dest=` on `parser.add_argument()` — `--natural-foreign` → `natural_foreign=True`, or
  the argparse `dest` if the author set a custom one (e.g. `use_natural_foreign_keys=True`
  for `dumpdata --natural-foreign`).
- Return value of `call_command()` is whatever `handle()` returns.
- Output redirection: `call_command("dumpdata", stdout=f)` — pass file-like objects
  (`io.StringIO()`, or an opened file) for `stdout=`/`stderr=`.
  Source: https://docs.djangoproject.com/en/6.0/ref/django-admin/#django.core.management.call_command

### 2. Capturing and asserting on output

Two equally valid patterns, pick one per test suite for consistency:

```python
# Pattern 1: pass StringIO explicitly (works with plain BaseCommand and click-based cmds
# as long as they write through self.stdout / the injected stream)
from io import StringIO
from django.core.management import call_command

out = StringIO()
call_command("my_command", stdout=out, stderr=StringIO())
assert "done" in out.getvalue()
```

```python
# Pattern 2: redirect_stdout — needed when the command doesn't accept/honour
# stdout= (e.g. writes with click.echo()/print() rather than self.stdout.write()).
from contextlib import redirect_stdout
from io import StringIO
from django.core.management import call_command

out = StringIO()
with redirect_stdout(out):
    call_command("my_command", "--dry-run")
assert "drift" in out.getvalue().lower()
```
Sources:
https://adamj.eu/tech/2020/09/07/how-to-unit-test-a-django-management-command/ ,
https://wersdoerfer.de/blogs/ephes_blog/til-testing-django-management-commands-with-pytest/

pytest's built-in `capsys` fixture is also viable for commands that print via `print()`
directly, but is less reliable for Django commands that write via `self.stdout` (a
`django.core.management.base.OutputWrapper`), since that wrapper is bound to whatever
stream object was supplied to `call_command` (defaults to real `sys.stdout`, which `capsys`
does capture — but explicit `stdout=StringIO()` is more deterministic than relying on fd
capture, especially under `-n auto` / xdist).

### 3. Asserting on errors: `CommandError` vs `SystemExit`

- Plain `BaseCommand` subclasses should raise `django.core.management.base.CommandError`
  for expected/user-facing failures. In tests:
  ```python
  from django.core.management.base import CommandError
  import pytest

  with pytest.raises(CommandError, match="does not exist"):
      call_command("my_command")
  ```
- Do **not** expect a bare `SystemExit` from `call_command()` for `CommandError` — Django's
  test-facing `call_command()` lets `CommandError` propagate as a normal Python exception
  (the `SystemExit`/`sys.exit(1)` + stderr-print behaviour only happens in the real
  `execute_from_command_line()` CLI entry point). `pytest.raises(CommandError)` is the
  correct idiom, not `pytest.raises(SystemExit)`.
- Source (community write-up building on the official docs, using `pytest.raises` on the
  command's own error type): https://wersdoerfer.de/blogs/ephes_blog/til-testing-django-management-commands-with-pytest/

### 4. Testing `--dry-run` / idempotency / `--check`-style drift detection

- For `--dry-run` flags: assert that (a) the reported outcome (e.g. "N drifted") is
  correct, **and** (b) no DB/filesystem side effect actually happened — i.e. write two
  assertions: one on output, one on state unchanged.
- For idempotency: call the command twice in the same test and assert the second run is a
  no-op (zero changes reported, no new DB rows).
- For `--check`/CI-style commands that should fail loudly on drift: assert the command
  raises (`CommandError`/`ClickException`) or returns non-zero, and that the message names
  the specific drifted item (helps future debugging when CI fails).
  General pattern recommended by: https://adamj.eu/tech/2020/09/07/how-to-unit-test-a-django-management-command/

### 5. Structuring commands for testability — keep `handle()` thin

Universally recommended pattern (Adam Johnson's post, wersdoerfer TIL, GeeksforGeeks
writeup, and Django's own dumpdata/loaddata source are all cited as examples of this):

- `handle()` / the click `command()` function should only: parse/validate options, call one
  or two plain functions, and format output.
- All real logic — querying, transforming, writing — belongs in plain, independently
  importable functions/services in the same module (or a sibling module).
- Two test tiers:
  1. **Unit tests** that import the plain function directly and call it with plain
     Python/ORM objects — fast, no `call_command` overhead, can even use
     `SimpleTestCase` if no DB is touched.
  2. **Integration tests** that go through `call_command()` to exercise option
     parsing, output formatting, and wiring — fewer of these, one per option/flag
     combination that matters.
- Rationale explicitly called out: `call_command()` has overhead (loads full command
  machinery) — extracting logic for direct unit testing is faster and clearer.
  Source: https://adamj.eu/tech/2020/09/07/how-to-unit-test-a-django-management-command/

### 6. Pitfalls

- **Don't shell out to `manage.py` via `subprocess`** to test a command. It is slow (new
  process + Django setup per test), can't easily share the test DB transaction/rollback
  machinery pytest-django relies on, and produces opaque failures. Use `call_command()`
  in-process instead.
- **Interactive prompts / stdin.** Commands that call `input()` or Click's
  `click.confirm()`/`click.prompt()` will hang or raise `Abort` under `call_command()`
  because there's no TTY. Either:
  - give the command a non-interactive flag (`--yes`/`--no-input`) and always pass it in
    tests, or
  - mock the prompt function (`unittest.mock.patch("...command.click.confirm",
    return_value=True)` or monkeypatch `builtins.input`), or
  - for pure-Click commands, use Click's own `CliRunner.invoke(..., input="y\n")` instead of
    `call_command` if finer control over stdin is needed (outside Django's test guidance,
    but standard Click testing practice).
- **Commands with heavy I/O** (network calls, subprocess calls to `git`, filesystem writes
  outside a temp dir, sending email). Isolate the I/O behind a small seam (a function
  parameter, an injectable client, `settings`-driven path) so tests can monkeypatch/mock it
  rather than hitting the real filesystem/network. Use `tmp_path`/`tempfile.TemporaryDirectory`
  for filesystem-writing commands so tests don't pollute the repo.
- **Type mismatches with `**options`.** Passing `verbosity="0"` instead of `verbosity=0` to
  `call_command(**options)` is a common silent-bug source since it bypasses argparse's
  string→type conversion (see §1).

---

## PART B — Current FLS state and gaps

### Inventory: all management commands (35 files, excluding `__init__.py`)

Found via `find freedom_ls -path "*/management/commands/*.py" -not -name "__init__.py"`.
Two implementation styles coexist:

**Plain `django.core.management.base.BaseCommand`** (raises `CommandError`):
- `freedom_ls/accounts/management/commands/build_legal_docs_manifest.py`
- `freedom_ls/base/management/commands/write_active_theme_css.py`

**`djclick` (`import djclick as click`, `@click.command()`)** (raises
`click.ClickException`, uses `click.echo`/`click.secho` for output, `click.confirm` for
prompts) — the majority, 33 files:
- `content_engine`: `content_validate.py`, `content_save.py`, `danger_content_delete.py`
- `site_aware_models`: `create_site.py`, `create_site_superuser.py`
- `student_progress`: `recalculate_progress_percentages.py`,
  `danger_clear_all_course_progress.py`
- `role_based_permissions`: `sync_role_permissions.py`, `validate_role_permissions.py`
- `student_management`: `create_demo_data.py`
- `qa_helpers` (15 commands, all `qa_*` prefixed dev/QA fixture generators):
  `qa_create_empty_student_cohort.py`, `qa_create_soft_deadline.py`,
  `qa_complete_form.py`, `qa_create_deadline_overrides.py`,
  `qa_create_large_cohort.py`, `qa_add_course_items_for_pagination.py`,
  `qa_create_cohort_progress.py`, `qa_create_header_bar_users.py`,
  `qa_create_course_player_student.py`, `qa_create_educator_modal_target.py`,
  `qa_create_form_question_types.py`, `qa_create_rich_dashboard_student.py`,
  `qa_create_password_reset_student.py`, `qa_create_application_docs_scenario.py`,
  `qa_create_course_access_types.py`, `qa_create_course_visibility.py`,
  `qa_create_course_detail_variants.py`, `qa_create_incomplete_registration_learner.py`

### Gap analysis: tested vs untested

`grep -rn "call_command" freedom_ls --include="*.py"` returns matches in exactly **one**
file: `freedom_ls/role_based_permissions/tests/test_management_commands.py`, which tests
`sync_role_permissions` and `validate_role_permissions` (both djclick commands).

- **Tested via `call_command`:** `sync_role_permissions`, `validate_role_permissions`
  (role_based_permissions) — 2 of 35.
- **Tested indirectly, bypassing `call_command` entirely** — logic already extracted into
  plain functions and unit-tested directly:
  - `content_save.py`'s `save_content_to_db()` is imported and called directly in
    `freedom_ls/content_engine/tests/test_content_save_course.py`,
    `test_content_save_save_with_uuid.py`, `test_form_save.py`.
  - `content_validate.py`'s underlying `freedom_ls.content_engine.validate.validate()` is
    imported and tested directly in `test_course_visibility.py`,
    `test_course_difficulty_duration_outcomes.py`, `test_icon_validation.py`,
    `test_toc_in_development.py`, and `freedom_ls/course_access/tests/test_load_time_validation.py`.
  - These are genuinely **not gaps** — this is the "thin handle, logic elsewhere" pattern
    working as intended (see Part A §5) — but nothing exercises the `command()` /
    `handle()` wiring itself (option parsing, `click.argument`s, output formatting), so a
    thin `call_command()` smoke test per command would still add value.
- **Untested, no coverage of any kind found:**
  - `build_legal_docs_manifest.py` — plain `BaseCommand`, shells out to `git` via
    `subprocess.run`, raises `CommandError` on missing dir / missing HEAD, has an
    `--output` option. Good candidate to demonstrate `CommandError` assertions,
    `tmp_path`-based `--output` testing, and mocking `subprocess.run`/`get_head_commit`.
  - `write_active_theme_css.py` — plain `BaseCommand`, raises `CommandError` when the
    theme CSS file is missing, otherwise writes a file to `BASE_DIR`. Simple, good
    "first example" for the skill (no DB needed — could use `SimpleTestCase` + `tmp_path`
    via `override_settings(BASE_DIR=..., RESOLVED_THEME_DIR=...)`).
  - `danger_content_delete.py` — djclick, **interactive** (`click.confirm(...)` unless
    `--yes`/`-y` passed), destructive (deletes all content-engine rows in a
    `transaction.atomic()` block). No test exists. Real risk: without `--yes`,
    `call_command("danger_content_delete")` will attempt to read stdin under pytest and
    likely raise/hang — the skill should show the `--yes` pattern and/or mocking
    `click.confirm`.
  - `danger_clear_all_course_progress.py` — djclick, destructive, **zero output, zero
    confirmation, zero error handling** — untested. Minimal risk-mitigation command that
    would benefit most from a test asserting all four progress tables are empty after the
    call, given a factory-seeded DB.
  - `recalculate_progress_percentages.py` — djclick, non-trivial aggregation logic
    (batches `TopicProgress`/`FormProgress` by user, recomputes `progress_percentage`).
    All logic lives inline in `handle()`/`command()` rather than being extracted —
    a concrete FLS example of the *anti-pattern* Part A §5 warns against. Untested.
    Good "before/after" example for the skill: show extracting the loop body into a
    testable `recalculate_all_course_progress() -> tuple[int, int]` function.
  - `create_site.py`, `create_site_superuser.py`, `create_demo_data.py` — djclick,
    idempotent `get_or_create` based setup commands, untested. Good idempotency-test
    candidates (call twice, assert second call creates nothing new).
  - All 18 `qa_helpers/qa_*` commands — djclick, dev/QA-fixture generators (create demo
    users, cohorts, deadlines, etc. for manual/E2E QA). None are tested via
    `call_command`. These are lower priority for unit tests (they exist to support manual
    QA and Playwright/E2E fixtures, not production behaviour) but at minimum a smoke test
    (`call_command` doesn't raise, given a `site` fixture) would catch import/wiring
    breakage cheaply.

### Representative commands read in full (complexity characterisation)

1. **`sync_role_permissions.py`** (djclick) — best current example of "thin `command()`,
   logic in private `_sync_object_assignments()` / `_ensure_permissions_exist()` /
   `_report_orphans()` helper functions", already well tested. `--dry-run` and
   `--report-orphans` flags, drift detection, DB side effects. **Use as the skill's
   canonical "how FLS already does this well" example.**
2. **`validate_role_permissions.py`** (djclick) — CI-oriented `--check`-style command:
   collects errors into a list, then `raise click.ClickException(error_msg)` if any exist.
   Tested via `pytest.raises(ClickException, match=...)` — **note this is `click.ClickException`,
   not Django's `CommandError`**, because it's a djclick command (see below).
3. **`content_validate.py` / `content_save.py`** — extreme "thin handle" example:
   `content_validate.py`'s entire `command()` body is `validate(path)` (one line); real
   logic lives in `freedom_ls/content_engine/validate.py`. `content_save.py` similarly
   delegates to `save_content_to_db()`. Neither is tested via `call_command` — the
   extracted functions are tested directly, and the thin `command()` wrapper is untested.
4. **`build_legal_docs_manifest.py`** — plain `BaseCommand`, the only command combining
   `subprocess` calls + `CommandError` + `--output` option handling — good "classic Django"
   contrast case against the djclick examples above.

### FLS-specific nuance for the skill: djclick changes the exception type

Because most FLS commands use **djclick**, not plain `BaseCommand`, the standard Django
docs advice ("assert `pytest.raises(CommandError)`") **does not directly apply** to most
FLS commands. Confirmed by reading FLS's own test suite
(`freedom_ls/role_based_permissions/tests/test_management_commands.py`): it imports
`from click import ClickException` and asserts
`pytest.raises(ClickException, match="...")` for `validate_role_permissions` failures
(raised in-command via `raise click.ClickException(error_msg)`). The skill **must**
explicitly document this fork:
- plain `BaseCommand` → `raise CommandError(...)` → assert with
  `pytest.raises(django.core.management.base.CommandError, match=...)`.
- djclick `@click.command()` → `raise click.ClickException(...)` (or let click's own
  argument validation raise `click.UsageError`, a `ClickException` subclass) → assert with
  `pytest.raises(click.ClickException, match=...)`.

### Output capture idiom already established in FLS

The existing test file uses `contextlib.redirect_stdout` + `io.StringIO()` wrapped in small
`_call_sync()` / `_call_validate()` helper functions (not `call_command(..., stdout=...)`)
— likely because djclick commands write via `click.echo()`, which writes to real
`sys.stdout` rather than honouring a `stdout=` kwarg passed to `call_command()`. **The skill
should verify/state**: for djclick commands, use `redirect_stdout`; for plain `BaseCommand`
commands (which write via `self.stdout.write()`), `call_command(..., stdout=StringIO())` is
sufficient and preferred (simpler, no global redirect).

### Recommendations for the skill

1. Lead with the fork: "Is this a plain `BaseCommand` or a djclick command?" — because it
   changes both the exception type to assert on and the output-capture idiom.
2. Provide two ready-to-copy helper snippets: one for plain `BaseCommand`
   (`call_command(..., stdout=StringIO())` + `pytest.raises(CommandError)`), one for
   djclick (`redirect_stdout(StringIO())` + `pytest.raises(click.ClickException)`).
3. Codify the "thin handle" pattern using `sync_role_permissions.py` as the positive FLS
   example and `recalculate_progress_percentages.py` as the "extract this" example to
   refactor-and-test in a worked example.
4. Include an explicit interactive-prompt pattern (mock `click.confirm` or always pass
   `--yes`/`-y`) referencing `danger_content_delete.py` as the motivating case.
5. Include an idempotency-test pattern (call twice, assert second call is a no-op)
   referencing `create_site.py`/`create_site_superuser.py`/`create_demo_data.py`.
6. Include a `--dry-run` pattern referencing `sync_role_permissions --dry-run` (assert
   output message **and** DB state unchanged).
7. Flag `qa_helpers/qa_*` commands as lower-priority/optional-smoke-test territory rather
   than requiring full coverage — they're QA fixture generators, not production logic.
8. Explicitly warn against `subprocess`-based `manage.py` invocation in tests, and against
   asserting `SystemExit` for `CommandError`/`ClickException` (assert the exception type
   directly instead).

---

status: ok
