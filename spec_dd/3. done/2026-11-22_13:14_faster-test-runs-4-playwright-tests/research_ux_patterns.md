# Research: UX patterns for a fast, pleasant Playwright suite

Topic `ux_patterns`, spec "Fewer, faster Playwright tests". The "users" are developers and agents writing and debugging the suite.

Sources read: `idea.md`, `answers.md`, `freedom_ls/tests/playwright_fixtures.py`, plus the web pages cited inline. Items marked (verify) come from my background knowledge and were not confirmed in a page I fetched.

## Constraints from the repo

- `answers.md` already settles three things: stop at the first failure (plain sequential `expect`, no soft assertions), one test loads data once then resizes through each viewport, and the owner approves "goes" rows in the spec review before any test is touched.
- `playwright_fixtures.py` has only `logged_in_page` (learner, UI login) and `logged_in_user`. Its docstring says to add role variants "the moment a second test needs them". The audit will almost certainly show that moment has arrived.
- The docstring rejects a session-scoped `storage_state` because `transaction=True` flushes the DB (user and `django_session` rows) after each test.

## 1. Signed-in page fixtures

**What the official guidance gives.** The Playwright auth page recommends log in once, save `storage_state`, reuse it via `browser.new_context(storage_state=...)`. It names a `playwright/.auth` directory (gitignored) and does not cover per-role patterns or API login. It also says `storage_state` does not capture `sessionStorage`. <https://playwright.dev/python/docs/auth>

**Why that does not fit here directly.** A saved file holds a cookie pointing at a `django_session` row that the flush deletes. The pattern that does fit is the same idea moved inside the test: mint the session per test, after the user exists, and hand the cookie to the context.

**Candidate shapes (the spec must choose; I am not deciding):**

- Cookie injection per test. The fixture creates the user, builds a Django session for that user (for example through `SessionStore` or the test client's `force_login`, reading `sessionid`), and calls `context.add_cookies([...])` for the live server host. No form, no extra navigation, and it survives the flush because it runs after each test's setup. This keeps the fixture function-scoped and the call site unchanged. (verify the exact Django calls and cookie domain handling against the live server's host.)
- Keep the UI login fixture only under a name that says what it does, used by the sign-in tests.

**Naming and ergonomics that tend to work:**

- One fixture per role, named for the role and the result, in the style already used: `learner_page`, `educator_page`, `admin_page`, with matching user fixtures `learner_user`, `educator_user`, `admin_user`. The page fixture depends on the user fixture, as `logged_in_page` does today, so a test can attach course registrations or cohorts to the exact user who is signed in (the existing `logged_in_user` docstring is the reason).
- Keep `logged_in_page` as an alias of the learner fixture during migration, or rename in one sweep. A two-name period confuses agents, so prefer one sweep with the audit as the checklist.
- The sign-in tests use the bare `page` fixture and the form helper, which makes "sign-in is the subject" visible from the fixture used. A test that takes `*_page` never touches the form, and a test that takes `page` and goes to `account_login` is the sign-in test. That is a usable rule for the skill text.
- Make a fixture build everything needed to be signed in and nothing else (email-verified address, per-role permission membership). Role setup shared by several fixtures belongs in one helper, not copied into each fixture (project rule: no repeated code).
- Document the "why not storage_state" in one place only (module docstring) and update it to describe the new mechanism, since the docstring currently states the opposite conclusion.

## 2. Readable merged flow tests

Python Playwright has no `test.step` (that is the JS/TS runner). Equivalents:

- `context.tracing.group("name")` / `group_end()` (added around Playwright 1.49, verify in the installed version) puts a named group in the trace viewer's action list, so each merged check appears as a labelled section. A small context manager `with step("mobile layout"):` in the shared test helpers would wrap this and also act as the label in the Python traceback. See the trace docs: <https://playwright.dev/python/docs/trace-viewer-intro>.
- Assertion messages: Python `expect(locator, "message")` accepts a custom message (verify), so each assert in a merged test can say what it checks ("sidebar hidden at 375px"). Prefer this over a comment because it appears in the failure output.
- With stop-at-first-failure (the settled answer), order the steps from cheapest and most fundamental to most dependent, so the first failure is the most informative one. Name the test for the page and flow ("course_page_layout_across_viewports"), not "test_1".
- Keep a merged test to one page and one dataset, a short list of steps, each step a few lines. If a flow needs a long comment block to explain, split by data, not by check.
- For the viewport design in `answers.md`: a loop over `(name, width, height)` tuples reading as `for viewport in VIEWPORTS: page.set_viewport_size(...)` reports the loop variable only if the message includes it. Include the viewport name in each assertion message, otherwise a failure says "expected visible" with no hint of which size. A shared constant of named viewports (`MOBILE`, `TABLET`, `DESKTOP`) avoids magic numbers in each file.

## 3. Failure artifacts

- `pytest --tracing retain-on-failure` records a trace per test and keeps only failures, written as `trace.zip` under `test-results`. Open with `playwright show-trace trace.zip`. Default is `off`. <https://playwright.dev/python/docs/trace-viewer-intro>
- Screenshots on failure: `--screenshot only-on-failure` (verify flag name); video is `--video retain-on-failure` (verify). Video costs CPU, so prefer trace plus screenshot for a suite chasing speed.
- Where to set them: `addopts` in pytest config or a documented one-liner in the skill. The trade-off for this effort is overhead: `retain-on-failure` still records every test, so measure it in the before/after run rather than assume it is free. A common compromise is on in CI-style runs (`finish_worktree`) and off in the edit-run loop, with `--tracing on` suggested only when debugging.
- Merging tests makes traces more valuable: one trace covers the whole flow, and with groups the failing step is the last group in the action list.

## 4. How a developer finds which check failed

Ordered by effort:

1. Pytest traceback line number plus the assertion message (section 2). Cheapest, always present.
2. Trace viewer: the last action before the red one, and the group name.
3. Screenshot at failure for the final state.
4. `page.pause()` or `PWDEBUG=1` for interactive stepping (verify).

A convention worth putting in the skill: every merged test's failure message must name the check and, in viewport loops, the viewport. An agent reading only the pytest output should be able to say which check failed without opening a trace.

## 5. Presenting the audit for owner approval

`answers.md` settles where the approval happens (spec review, "goes" rows listed in the spec). Presentation patterns that help a reviewer:

- One table, one row per test (220 rows is long, so group by file and collapse unchanged groups). Columns: test id, what it checks (one line), setup shared with neighbours, verdict (`merges into X`, `stays`, `goes`), reason, and for merges the target flow name.
- Put the "goes" rows in their own short section at the top of the spec with the reason and what, if anything, still covers that behaviour (a non-browser test, another browser flow). Approving 5 rows is realistic; approving 220 is not, so the reviewer reads the exceptions and skims the rest.
- Show a coverage-preservation check: every checked behaviour in the old list maps to exactly one check in the new list. A two-way mapping (old to new, and new back to old) makes "nothing dropped" checkable by counting.
- Summaries up front: counts per verdict, and estimated seconds saved per merge group, so the owner can weigh a risky merge against its saving. The idea's 2 to 3 minute figure is flagged as a guess until the audit exists, so the audit is also the place to replace it with a number.
- Mark "moves out of the browser" rows separately from "goes". They keep the behaviour covered, and the owner should see them as lower risk.

## Suggestions for the spec to consider

- Decide the session mechanism first, since every other item depends on it, and update the module docstring in the same change.
- Role fixtures and the audit are tied: the audit's setup-sharing column tells you which roles are needed now.
- Include in the skill updates: fixture naming rule, the sign-in-only rule for the UI form, the step helper plus message convention, viewport constants, and the trace flags.
- Measure with and without `--tracing retain-on-failure` so the artifacts are not a hidden cost.

## Sources

- <https://playwright.dev/python/docs/auth>
- <https://playwright.dev/python/docs/trace-viewer-intro>

status: ok
