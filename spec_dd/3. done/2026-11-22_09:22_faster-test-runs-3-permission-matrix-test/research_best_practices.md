# Research: best practices (permission-matrix test restructure)

Note: written from established knowledge of the tools; URLs are the canonical docs, not fetched this session.

## 1. Table-driven authorization tests
- Keep the expected matrix as plain data (role x scope -> allowed/denied) separate from the walker. The data is the spec; the walker is dumb.
- Walk the table in one test per capability, and make each cell's result a tuple `(permission, role, object, relation, expected, actual)` so a failure names the cell.
- Prefer enumerating roles/scopes from the source of truth (enum / model choices) so a new role with no table row fails loudly rather than being silently skipped.

## 2. Collecting many failures in one test
- **Assert on a list of mismatches (recommended here).** Build `mismatches: list[str]`, then `assert not mismatches, "\n".join(mismatches)`. No dependency, one precise message, works with xdist and pytest-django rollback. Sort the list so output is deterministic. Cap or summarise only if huge.
- **pytest-check** (https://github.com/okken/pytest-check): soft asserts, all failures reported, but adds a dependency and verbose per-check output. Overkill when you already build your own report.
- **Subtests** (`pytest-subtests` https://github.com/pytest-dev/pytest-subtests; built into pytest 9 https://docs.pytest.org/en/stable/how-to/subtests.html): per-cell reporting, but each subtest still counts and costs reporting overhead, and DB state is NOT reset between subtests (they share the one test's transaction). Use only if per-cell IDs in the report matter more than speed.
- Trade-off of list approach: loses per-cell pass/fail counts and `-k` selection of one cell; compensate with the cell in the message and a coverage assertion (section 5).

## 3. Sharing expensive DB fixtures in pytest-django
Docs: https://pytest-django.readthedocs.io/en/latest/database.html and https://pytest-django.readthedocs.io/en/latest/faq.html
- **Per test (default):** each test in a transaction rolled back at the end. Safe, slow if setup is heavy. This is today's 763x rebuild.
- **Build once inside one test (chosen):** setup cost paid once per capability; stays inside the per-test rollback, so no state leaks and no cleanup code. Fully xdist-safe (each worker has its own DB; no cross-test state).
- **Module/session scope with `django_db_blocker.unblock()`:** data persists outside any test transaction, so you must delete it yourself; leaks on crash, can break other tests' counts, and each xdist worker rebuilds it per worker. Also fixtures using `django_db_setup` ordering get fiddly.
- **`django.test.TestCase.setUpTestData`** (https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TestCase.setUpTestData): class-level atomic block, rolled back after the class; Django 3.2+ deep-copies class attributes per test so mutations don't leak. Good fit if the file used classes; not natural with pytest parametrize. Needs the same grouping (one class per capability) to save time.
- Takeaway: the "walk per capability" choice avoids the whole cross-test state problem; its cost is only granularity.

## 4. Isolating mutations inside a walk
- If a cell mutates (e.g. deactivating a StaffMember, revoking a grant), wrap that cell in `transaction.atomic()` and force rollback (raise a private exception, or `transaction.set_rollback(True)` inside the atomic block). Nested atomic uses a SAVEPOINT, so cost is small. Docs: https://docs.djangoproject.com/en/stable/topics/db/transactions/#savepoints
- Cheaper alternative: order read-only cells first and group mutating checks into separate tests that build their own world.
- Beware cached state: clear per-request/per-user permission caches (e.g. `_perm_cache`, `refresh_from_db`, fresh `User` fetch) between cells, otherwise a rolled-back mutation still shows in cached objects.
- Don't catch broad exceptions inside the walker to keep going; an unexpected exception should fail the test (or be recorded as a mismatch naming the cell), never be swallowed.

## 5. Proving coverage equal after restructuring
- Before: record the exact set of 763 parametrized IDs (`pytest --collect-only -q`) and their (permission, role, scope, object) tuples.
- In the walker: record each visited cell in a set and, at the end, `assert visited == expected_cells` (expected generated independently from the role/scope/permission definitions, not from the walker's loop), reporting `expected - visited` and `visited - expected`.
- Assert the total cell count equals 763 once as a one-off migration check (and ideally keep the set-equality check permanently).
- Mutation check: temporarily flip one table entry (or one permission rule) and confirm the new test fails with that cell named; do this for a few capabilities to show the walk is not vacuous.
- Also ensure empty-iteration cannot pass: assert the visited set is non-empty per capability.
- Apply the same shape to the other world-building tests in the file (deactivation, visibility, import-gate), per answers.md: the whole file gets the treatment.

## References
- https://pytest-django.readthedocs.io/en/latest/database.html
- https://pytest-django.readthedocs.io/en/latest/faq.html
- https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TestCase.setUpTestData
- https://docs.djangoproject.com/en/stable/topics/db/transactions/#savepoints
- https://github.com/okken/pytest-check
- https://github.com/pytest-dev/pytest-subtests
- https://docs.pytest.org/en/stable/how-to/subtests.html

status: ok
