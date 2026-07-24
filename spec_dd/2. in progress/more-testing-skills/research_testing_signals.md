# Research: Testing Django Signals, Receivers, and `transaction.on_commit` Hooks

Stack: Python 3.13+, Django 6.x, PostgreSQL, pytest + pytest-django (project pins `pytest-django>=4.11.1`,
`factory-boy>=3.3.3`).

## PART A — External Best Practices

### A1. Test the receiver's *effect*, not "did a signal fire"

The dominant, most-cited guidance (Haki Benita, "How to Test Django Signals Like a Pro") is: prefer testing
what the receiver *does* (its observable side effect — a row created, an email sent, a field changed) over
asserting the signal object itself was dispatched. Signal-firing is Django plumbing; it's not your code, and
asserting "my `post_save` receiver ran" without checking its effect is a tautological test.

> "The best way to test a signal is to test its receiver directly, or test the effect of the receiver
> function." — https://hakibenita.com/how-to-test-django-signals-like-a-pro

Two concrete receiver-testing approaches, both valid depending on what you're proving:

1. **Call the receiver function directly** as a plain function (bypass the signal dispatch entirely) and
   assert its effect. Good for pure unit-testing of receiver logic.
2. **Exercise the code path that triggers the signal** (e.g. `Model.objects.create(...)`) and assert the
   receiver's effect happened. This also proves the receiver is actually *wired up* (registered), which
   approach 1 does not.

Only use approach 2 (trigger the real signal) when you specifically need to prove wiring — e.g. "saving a
`User` really does create a `Profile`" — not for every unit of receiver logic.

Source: https://hakibenita.com/how-to-test-django-signals-like-a-pro

### A2. Asserting a signal *was sent* — when you do need it

When you must assert dispatch itself (e.g. proving a *third-party* signal you don't control was sent, or
testing wiring without invoking the real receiver's side effects), use a temporary receiver/mock, connected
and disconnected around the test, rather than a global receiver:

```python
from contextlib import contextmanager
from unittest import mock

@contextmanager
def catch_signal(signal):
    handler = mock.Mock()
    signal.connect(handler)
    try:
        yield handler
    finally:
        signal.disconnect(handler)
```

```python
with catch_signal(charge_completed) as handler:
    charge(100)
handler.assert_called_once_with(sender=mock.ANY, total=100)
```

- `unittest.mock.Mock()` as the receiver gives you `assert_called_once_with()`, `assert_not_called()`,
  `call_args` etc. for free — no hand-rolled closures with `nonlocal`/`self` bookkeeping.
- Always disconnect in a `finally`/context-manager exit, not just at the end of the test body — an
  exception mid-test must not leave the handler connected for subsequent tests (see A4).
- `django.test.signals` / `django.test.utils` provide no built-in "signal was sent" assertion helper —
  this pattern (connect a temporary Mock receiver, disconnect after) *is* the idiomatic Django approach;
  there's no framework-provided `assertSignalSent`.

Sources:
- https://hakibenita.com/how-to-test-django-signals-like-a-pro
- https://www.freecodecamp.org/news/how-to-testing-django-signals-like-a-pro-c7ed74279311/
- https://yourlabs.org/posts/2012-10-06-testing-django-signals-properly/

### A3. Don't test that Django's own signals fire

Do not write tests that merely assert `post_save`/`pre_save`/etc. fire on `Model.save()` — that is testing
Django itself, not your code. Only test *your* receivers' registration and effects.

### A4. Pitfall: receivers with global side effects bleeding across tests

`Signal.connect()` is process-global state. A receiver connected in one test (and not disconnected) stays
connected for every test that runs afterward in the same process — a classic source of flaky, order-dependent
test suites. Rules of thumb:

- Connect/disconnect symmetrically inside a `try`/`finally` or context manager (A2), never bare
  `signal.connect(...)` followed by an unconditional `signal.disconnect(...)` at the end of the function body.
- Watch for **duplicate receiver registration**: connecting the same receiver function twice (e.g. because
  `AppConfig.ready()` runs its signal-wiring import more than once, or a test module re-imports and
  re-registers) makes the receiver fire twice per event — pass `dispatch_uid` on `@receiver`/`.connect()` to
  make registration idempotent.

Source: https://hakibenita.com/how-to-test-django-signals-like-a-pro

### A5. `transaction.on_commit()` callbacks: they don't run inside the default test wrapper

Django's default `TestCase` (and `@pytest.mark.django_db` without `transaction=True`) wraps every test in an
outer `atomic()` block that is always rolled back — so it **never actually commits**, and
`transaction.on_commit(callback)` callbacks registered during the test **never run**. This is Django ticket
history, not a bug: https://code.djangoproject.com/ticket/30457.

> "Because `TestCase` wraps each test in an atomic transaction that's rolled back at the end, the
> transaction is never actually committed and `on_commit()` handlers never run." —
> https://adamj.eu/tech/2020/05/20/the-fast-way-to-test-django-transaction-on-commit-callbacks/

**Option 1 — `TransactionTestCase` / `@pytest.mark.django_db(transaction=True)`**: runs against a real
commit, so `on_commit()` callbacks fire naturally. Correct, but slow — `TransactionTestCase` truncates and
reloads every table after each test (cost scales with the number of models in the project), so favor it only
when you need genuine cross-transaction/commit behavior (e.g. testing another thread/process sees committed
data).

**Option 2 (preferred, fast) — capture-and-execute the callbacks under the default fast `TestCase`/`django_db`**:

- `django.test.TestCase.captureOnCommitCallbacks(*, using=DEFAULT_DB_ALIAS, execute=False)` — a context
  manager (Django ≥3.2, stdlib). Returns a list of captured callback callables on exit; pass `execute=True`
  to have them invoked automatically as the `with` block exits (emulating a commit).

  ```python
  from django.test import TestCase

  class ContactTests(TestCase):
      def test_post(self):
          with self.captureOnCommitCallbacks(execute=True) as callbacks:
              response = self.client.post("/contact/", {"message": "hi"})
          assert response.status_code == 200
          assert len(callbacks) == 1
          assert len(mail.outbox) == 1
  ```

  Source: https://docs.djangoproject.com/en/6.0/topics/testing/tools/,
  https://adamj.eu/tech/2020/05/20/the-fast-way-to-test-django-transaction-on-commit-callbacks/

- Plain-pytest equivalent: the **`django_capture_on_commit_callbacks` fixture** shipped by pytest-django
  (≥4.4, so covered by this project's `pytest-django>=4.11.1` pin). Same signature/semantics as the
  `TestCase` method:

  ```python
  def test_on_commit(client, mailoutbox, django_capture_on_commit_callbacks):
      with django_capture_on_commit_callbacks(execute=True) as callbacks:
          response = client.post("/contact/", {"message": "hi"})
      assert response.status_code == 200
      assert len(callbacks) == 1
      assert len(mailoutbox) == 1
  ```

  Caveat straight from the docs: **avoid this fixture in tests marked `transaction=True`** — "you are not
  likely to get useful results" (real commits happen there, so there's nothing meaningful to capture).

  Source: https://pytest-django.readthedocs.io/en/stable/helpers.html

**Decision rule for the skill**: default to `captureOnCommitCallbacks`/`django_capture_on_commit_callbacks`
for asserting on `on_commit()` side effects — it's fast and precise. Reach for
`transaction=True`/`TransactionTestCase` only when the thing under test genuinely depends on a committed
row being visible to something outside the test's own connection (e.g. a real background worker, a second
DB connection, `select ... for update skip locked` polling).

### A6. Pitfall: `on_commit` hooks silently never running (false-green tests)

If a test exercises code that registers an `on_commit()` callback but neither uses `transaction=True` nor
`captureOnCommitCallbacks`, the callback is simply **discarded on rollback** — the test can still pass
(nothing asserts the callback's effect, or the assertion is on something unrelated) while giving zero
coverage of the callback's behavior. This is the single most dangerous failure mode: the test *looks* like
it covers commit-time behavior but doesn't. Always assert directly on the effect the callback should have
produced (a created row, a sent email, a mocked call) — a test that only asserts "no exception was raised"
around an `on_commit`-registered call proves nothing.

Source: https://adamj.eu/tech/2020/05/20/the-fast-way-to-test-django-transaction-on-commit-callbacks/

### A7. `factory_boy`: `@factory.django.mute_signals(...)` to suppress signals during factory creation

`factory.django.mute_signals(signal1, signal2, ...)` disconnects the given signals for the duration of
factory object creation, then reconnects them — useful when a `post_save`/`pre_save` receiver (e.g.
auto-creating a `Profile` on `User` save) would otherwise fire unwanted side effects every time a factory
builds a fixture object unrelated to what's under test.

As a class decorator (mutes signals for every `create()` call from that factory):

```python
import factory
from . import models, signals

@factory.django.mute_signals(signals.pre_save, signals.post_save)
class FooFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Foo
```

As a context manager (scoped to one call site):

```python
def make_chain():
    with factory.django.mute_signals(signals.pre_save, signals.post_save):
        return SomeFactory(), SomeOtherFactory()
```

Known limitation: decorating a *test class* (e.g. `TestCase` subclass) with `mute_signals` has no effect —
it only works applied to a `Factory` subclass or as a context manager, because it hooks into Factory's
object-generation lifecycle, not arbitrary test execution.

Source: https://factoryboy.readthedocs.io/en/stable/orms.html,
https://github.com/FactoryBoy/factory_boy/issues/348

## PART B — Current FLS State and Gaps

### B1. No Django signal receivers exist in production code today

A repo-wide grep for `on_commit|@receiver|Signal\(|post_save|pre_save|post_delete|signals` across
`freedom_ls/**/*.py` found:

- **Zero** `@receiver`, `Signal(`, `post_save.connect`, `pre_save.connect`, `post_delete.connect`, or
  `.connect(` usages anywhere in the codebase (production or test).
- The only textual hits for "signals" are unrelated English usage in docstrings/comments — e.g.
  `freedom_ls/course_applications/models.py` (a forward-looking `NOTE:` about an *upcoming*
  `application_state_changed signal` for application review — not yet implemented; do not delete that
  comment) and two unrelated UI-copy docstrings in `freedom_ls/course_applications/tests/test_backends.py`
  ("The 'Apply now' decision **signals**...").
- `freedom_ls/course_applications/apps.py::CourseApplicationsConfig.ready()` has a placeholder: `# No
  signals yet; application review will add them.` — confirms Django signals are a known *future* pattern
  for this codebase, not a current one.

**Implication for the skill**: FLS has no existing `@receiver`/signal-testing examples to point to yet.
The skill needs to lay down the pattern (A1–A4) proactively so the first signal-based feature (application
review's `application_state_changed`) has a house style to follow, rather than reinventing it ad hoc.

### B2. `transaction.on_commit()` itself is not called anywhere in application code

Grep for literal `on_commit` across `freedom_ls/**/*.py` finds **no production call site** —
`freedom_ls/webhooks/events.py::fire_webhook_event()` does *not* wrap its `WebhookEvent.objects.create()` +
`default_task_backend.enqueue()` in an explicit `transaction.on_commit(...)`. Every `on_commit` grep hit is
a comment in a **test** file (see B3).

Commit-safety for the webhook event flow instead comes from the **task backend's own semantics**, which
differ by environment (see `freedom_ls/deployment/settings_defaults.py:45-51`):

- **Dev/test** (`config.settings_base.TASKS`, inherited unmodified by `config.settings_dev` — confirmed via
  `pyproject.toml`'s `DJANGO_SETTINGS_MODULE = "config.settings_dev"`): `django.tasks.backends.immediate.ImmediateBackend`.
  Reading `.venv/.../django/tasks/backends/immediate.py::ImmediateBackend.enqueue()` shows it calls
  `self._execute_task(task_result)` **synchronously, inline, with no `transaction.on_commit` deferral at
  all** — the task runs the instant `enqueue()` is called, transaction state notwithstanding.
- **Production** (`config/settings_prod.py:82` → `fls_defaults.DATABASE_TASKS` →
  `django_tasks_db.DatabaseBackend`): per the comment at
  `freedom_ls/deployment/settings_defaults.py:47-48`, "Enqueue stays on-commit (Django default) so the
  worker sees the committed WebhookEvent row" — i.e. `django_tasks_db.DatabaseBackend` defers the actual
  enqueue/persist until the surrounding transaction commits.

**Consequence — a real gap worth flagging**: the dev/test backend (`ImmediateBackend`) never exercises the
commit-deferral behavior that production's `DatabaseBackend` relies on. A regression that broke the
production backend's on-commit deferral (e.g. an accidental `ENQUEUE_ON_COMMIT=False`-equivalent
misconfiguration, or a future refactor that calls `enqueue()` eagerly instead of relying on the backend)
would not be caught by the current test suite, because the test backend was never on-commit-gated to begin
with. If/when FLS starts calling `transaction.on_commit()` explicitly (e.g. inside `fire_webhook_event`
itself, rather than delegating the concern entirely to the configured task backend), it should be tested
with `captureOnCommitCallbacks`/`django_capture_on_commit_callbacks` (A5) so the assertion is really about
*deferral*, not just end-to-end behavior under `ImmediateBackend` where deferral is a no-op.

### B3. `@pytest.mark.django_db(transaction=True)` is used for webhook tests — but may be cargo-culted

Grep for `transaction=True` alongside `on_commit` finds 5 test files, all in the webhook-events family, each
carrying the identical comment `# transaction=True so that on_commit hooks for webhook event delivery fire
under test`:

- `freedom_ls/webhooks/tests/test_events.py` (class `TestFireWebhookEvent`)
- `freedom_ls/accounts/tests/test_account_webhook_events.py` (class `TestUserRegisteredWebhookEvent`)
- `freedom_ls/accounts/tests/test_user_registration_webhook_integration.py`
- `freedom_ls/student_interface/tests/test_course_completion_webhook_events.py`
- `freedom_ls/student_management/tests/test_registration_webhook_events.py`

Reading the actual test bodies (e.g. `test_account_webhook_events.py::TestUserRegisteredWebhookEvent`,
`test_registration_webhook_events.py::TestCourseRegisteredWebhookEvent`) shows every one of them
**mocks `freedom_ls.webhooks.events.fire_webhook_event` itself** via `mocker.patch(...)`/`patch(...)` and
asserts `mock_fire.assert_called_once_with(...)`. Since `fire_webhook_event` is fully mocked out, **no real
`on_commit` callback is ever registered in these particular tests** — the `transaction=True` marker (and
its associated `TransactionTestCase`-style per-test table flush cost, see A5) buys nothing for them. This
looks like the comment/marker were copy-pasted across the whole "webhook events" test family once (from
`freedom_ls/webhooks/tests/test_events.py::TestFireWebhookEvent`, where it *is* warranted — see below) rather
than re-justified per file.

Contrast with `test_events.py::TestFireWebhookEvent::test_creates_event_record_on_commit`, which calls the
real (unmocked) `fire_webhook_event()` and asserts on the real `WebhookEvent` row created plus (in a sibling
test) the real `default_task_backend.enqueue` call — here `transaction=True` is at least not obviously
wasted, though per B2 it still isn't exercising genuine on-commit *deferral* semantics under
`ImmediateBackend`.

**Gap for the skill to codify**: `transaction=True`/`TransactionTestCase` should be a deliberate, per-test
(or per-class) choice justified by "this test needs a *real* commit to be observable" — not a blanket
class-level marker inherited by every test in the file regardless of whether that particular test mocks away
the very call that would need it. The skill should give a concrete rule: if the code under test's
`on_commit`/task-enqueue call is mocked in the test, `transaction=True` is very likely unnecessary — use
plain `@pytest.mark.django_db` instead and let the mock's assertion carry the test.

### B4. `django_capture_on_commit_callbacks` / `captureOnCommitCallbacks` are not used anywhere

Grep for `django_capture_on_commit_callbacks|captureOnCommitCallbacks` across `freedom_ls/**/*.py`: **no
matches**. FLS's entire on-commit test story today is `transaction=True` (B3) plus mocking the call before
it would matter. This is the clearest concrete gap: the faster, more precise pytest-django fixture
(available given the `pytest-django>=4.11.1` pin, A5) is not part of the current toolkit/house style at all.
The skill should introduce it as the default recommendation for future `on_commit`-adjacent tests, reserving
`transaction=True` for cases that genuinely need a committed row visible outside the test's own transaction.

### B5. `factory.django.mute_signals` is not used anywhere

Grep for `mute_signals` across `freedom_ls/**/*.py`: **no matches**. Consistent with B1 (no signal receivers
exist yet to need muting). Worth including in the skill preemptively since `factory-boy>=3.3.3` is already a
project dependency and application review (per the B1 `NOTE:`) will introduce the first receiver
(`application_state_changed`) that factories creating `CourseApplication` fixtures may need to mute.

### B6. `mock_site_context` fixture as the de facto site-context pattern

Not signals-specific, but relevant context for any snippets the skill includes: nearly all webhook/on_commit
tests depend on the shared `mock_site_context` fixture (`freedom_ls/conftest.py:106`), which patches
`freedom_ls.site_aware_models.models._thread_locals.request` and `get_current_site` so
`fire_webhook_event`'s `get_cached_site(request)` call resolves to a real `Site`. Any example test the skill
writes for webhook/`on_commit` scenarios should use this fixture rather than hand-rolling request mocking.

## Recommendations for the Skill

1. **Lead with "test the receiver's effect, not that a signal fired"** (A1) as the default rule; only
   assert dispatch directly (A2, `catch_signal` context-manager pattern) when proving wiring or testing a
   signal you don't own the receiver for.
2. **Never leave a test-connected receiver dangling** — always connect/disconnect symmetrically in a
   `try`/`finally` or context manager (A4); call out `dispatch_uid` for idempotent registration.
3. **Default to `captureOnCommitCallbacks`/`django_capture_on_commit_callbacks(execute=True)`** for testing
   `on_commit()` callback effects under the fast `TestCase`/`@pytest.mark.django_db` path (A5); document the
   exact API names/signatures from A5 verbatim so the skill is copy-paste correct.
4. **Reserve `transaction=True`/`TransactionTestCase`** for tests that need a genuinely committed row
   visible outside the test's own DB connection; explicitly warn against blanket class-level `transaction=True`
   inherited by tests that mock away the very on-commit-registering call (concrete counter-example: B3's
   webhook test family).
5. **Call out the false-green trap (A6)** explicitly: a test can pass while never actually running its
   `on_commit` callback if neither `transaction=True` nor a capture fixture is used — always assert directly
   on the callback's effect.
6. **Document `factory.django.mute_signals`** (A7) as the house pattern for suppressing signal side effects
   during factory object creation, including the "doesn't work as a TestCase class decorator" caveat.
7. **Use FLS's own webhook/task-backend split (B2) as a worked example** of why "on-commit" behavior is
   environment-dependent (`ImmediateBackend` in dev/test vs `django_tasks_db.DatabaseBackend` in prod) — a
   good illustration for the skill of why testing on-commit deferral explicitly (rather than trusting the
   configured backend) matters once FLS calls `transaction.on_commit()` directly.
8. Point at `freedom_ls/conftest.py::mock_site_context` (B6) as the fixture to reuse for any example
   signal/on-commit test involving site-aware code.

status: ok
