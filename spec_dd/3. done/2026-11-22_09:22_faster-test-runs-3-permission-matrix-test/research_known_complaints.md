# Known complaints: loop-in-a-test, shared fixtures, permission matrices

Part of this is sourced from the web. Items marked (experience) are well-known patterns I did not re-verify here.

## 1. Loop in one test vs parametrize

| Complaint | Mitigation |
|---|---|
| A plain loop stops at the first failing cell, so the rest stay hidden. Ganssle's unittest example shows this: without `subTest` the test dies at i=1. | Collect every mismatch in a list and assert once at the end, or use pytest 9 native `subtests`. |
| Test ids are lost. One test id covers 763 cells, and `-k` can't select a single cell. | Put permission, role, object and relation in every mismatch message. Keep one test per capability so the id is still meaningful. Keep a helper that re-checks one cell, to reproduce a failure. |
| Debugging is harder: no per-cell rerun, no per-cell `--pdb`, and the failure report is one long message. | Sort the mismatches and print them as a table. Cap the output only if it gets huge. |
| Per-cell timing and `--durations` are no longer visible. | Not a real loss here, since the cells are cheap once the data is shared. |
| Reporting: with pytest subtests, failures are listed first and the parent test's result comes last. Passed subtests are hidden unless you pass `-v`. | Accept this. Check that the failure message still names the cell. |
| Subtests share one test function, while parametrize makes each combination its own test. (Simon Willison TIL) | Use subtests only if you want per-cell failure lines. A manual mismatch list is simpler and doesn't depend on the pytest version. |
| Mixing subtests with `xdist` or other plugins has had rough edges. pytest 9 folded in `pytest-subtests`, and an old third-party issue describes exiting after the first subtest failure or skip. | Prefer the collect-and-assert-once pattern. It has no plugin dependency. |

## 2. Shared fixtures across cells

| Complaint | Mitigation |
|---|---|
| Test pollution and order dependence: one cell mutates data (grants, role changes) that a later cell reads. (experience) | Settle the open question first: does any cell change data another cell reads? Make the walk read-only. Where a cell must change data, do the mutation inside a `transaction.atomic()` savepoint and roll it back, or group those cells into their own test. |
| Stale permission caches. Django's `ModelBackend` caches on the user instance as `_perm_cache`, `_user_perm_cache` and `_group_perm_cache`. A grant made after the first `has_perm` call is invisible. The docs say to re-fetch the user. | Re-fetch the user (`User.objects.get(pk=...)`) after each grant change. Or build a fresh user object per cell from shared rows. Or delete those cache attributes. |
| django-guardian's `ObjectPermissionChecker` caches per-object permissions on the instance. A reused checker gives stale answers once permissions change. (experience, from guardian docs and issues) | Create a new checker per cell. Never reuse one across a grant or revoke. |
| Class-level or module-level data and `TestCase.setUpTestData`: Django deep-copies class attributes per test since 3.2 to stop leakage. A single-test walk doesn't get this protection. | Build the data inside the one test, or use a fixture scoped to the test. Don't mutate model instances shared across cells. |
| Hidden false passes: a cell passes because of data left over from an earlier cell. | Add a sanity cell that must be denied and one that must be allowed. Check the result of the walk against the old per-case results once, before deleting the old test. |

## 3. Permission-matrix tests generally

| Complaint | Mitigation |
|---|---|
| Brittleness: any rule change breaks hundreds of cells at once. | Keep the matrix as one declarative table, with one source of truth and no per-cell code. |
| Transcription drift: the expected table is copied by hand from the rules and drifts from them, so the test checks itself. | The spec leaves the matrix unchanged, so move the table verbatim. Compare the set of cells before and after (count and keys). |
| Large cell counts (763 here) feel exhaustive but hide gaps: a missing cell is silent. | Assert that the walk covered exactly the expected number of cells, so a skipped one is an error. |
| Slow because each cell builds its own world. | This is the problem this spec solves. Build once, walk many. |

## Recommendation

Use one test per capability. Build the world once, in a fixture scoped to the test. Walk the cells read-only. Use a fresh user object and a fresh guardian checker per cell. Collect mismatches as "permission / role / object / relation: expected X, got Y". Assert once at the end. Also assert the cell count equals the old count of 763.

## References

- https://docs.pytest.org/en/9.0.x/how-to/subtests.html
- https://til.simonwillison.net/pytest/subtests
- https://blog.ganssle.io/tag/pytest.html
- https://lwn.net/Articles/1045987/
- https://docs.djangoproject.com/en/stable/topics/auth/default/#permission-caching
- https://django-guardian.readthedocs.io/en/stable/userguide/check.html

status: ok
