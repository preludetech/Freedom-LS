# Research: ux_patterns (developer experience of a walking matrix test)

There is no end-user UI. The only "user" is a developer reading pytest output. Little applies beyond the points below. They come from general pytest practice. I did not fetch the URLs for this run, so treat them as pointers.

## 1. Reporting failures from a test that walks many cells

Collect, don't stop at the first failure. Walk every cell, append a record for each disagreement, then make one assertion at the end with the whole report. A bare `assert` inside the loop hides every cell after the first bad one.

Recommended report shape:

- A count header: `3 of 120 cells disagree for capability "view_cohort_progress"`.
- One line per disagreeing cell, with every coordinate and both values: `permission=<p> role=<r> object=<o> relation=<rel> expected=ALLOW actual=DENY`.
- Sorted by a stable key (role, scope, object, relation), so reruns diff cleanly and CI logs compare.
- Fixed-width columns (a mini table) only if it stays greppable. One cell per line with `key=value` pairs is safer: a line can be pasted into `-k` or a grep.
- Also report cells that errored (exception type and message) as a disagreement line, not a crash. Otherwise one bad cell loses the rest of the report.
- Keep the cell total in the header. It shows coverage did not shrink: the checked count can be compared with the old 763.

Alternatives:

- `pytest-subtests` gives per-cell reporting, but each subtest failure is a separate report block and adds overhead. The answers file already chose the walk.
- `pytest-check` and `pytest-assume` are soft-assertion plugins. They add a dependency for what a plain list does.

Make the assertion message the report itself. Pytest's assertion rewriting prints the message, so use `pytest.fail(report, pytrace=False)` or `assert not failures, report`. `pytrace=False` removes the traceback noise, which is useful when the traceback points at the loop and not at a cell.

## 2. Re-running a single capability

Walk-per-capability gives one test per capability. Parametrize over the capability only, with readable ids (`ids=` or `pytest.param(..., id="view_cohort_progress")`). Then `pytest -k view_cohort_progress` or the full node id re-runs that capability. A developer can no longer select a single role × scope cell by test id. To make up for that, the failure line should hold enough to reproduce the cell by hand.

Optional: an environment variable or a pytest option that narrows the walk to one role or scope. That is extra functionality and not requested, so mention it only as a possible follow-up.

Keep ids stable and free of spaces and odd characters, so `-k` expressions and CI retry tooling (the sibling idea on rerunning failures) can use them.

## 3. `--durations` and CI output

- Fewer, longer tests: `--durations=N` will show about one line per capability, each slow. That is correct, and it makes the cost per capability visible. The old 763 lines of about 0.67s each disappear.
- If the world is built once per capability test, setup time shows under `setup` and the walk under `call` when the world comes from a fixture. Building it in the test body puts everything under `call`. A fixture gives the developer the split in `--durations`.
- The CI pass count falls from 763 to a handful. State this in the spec, so a falling test count is not read as lost coverage. The count header in the failure report, and perhaps a measured cell total, answer that.
- Under pytest-xdist, one big test per capability balances less evenly than 763 small ones. A few test-sized units are still fine, but watch the biggest one.
- Keep failure output deterministic (sorted). That keeps CI logs and retry-on-failure tooling stable.

## References

- pytest, parametrize ids: https://docs.pytest.org/en/stable/how-to/parametrize.html
- pytest, `-k` selection and node ids: https://docs.pytest.org/en/stable/how-to/usage.html
- pytest, `pytest.fail` and `pytrace`: https://docs.pytest.org/en/stable/reference/reference.html#pytest-fail
- pytest, `--durations`: https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration
- pytest-subtests: https://github.com/pytest-dev/pytest-subtests
- pytest-check: https://github.com/okken/pytest-check

status: ok · reason: short synthesis from general pytest practice, URLs not fetched
