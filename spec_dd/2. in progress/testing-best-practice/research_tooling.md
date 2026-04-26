# Testing Tooling & Practices Research (2026)

Decision document for FLS — a Django 6 + pytest + HTMX + Playwright project.

**Baseline already in place:** `pytest`, `pytest-django`, `pytest-mock`, `pytest-cov`, `pytest-playwright`, `pytest-env`, `factory_boy`, plus documented anti-patterns (no tautologies, no conditionals/loops in test bodies, mock only at boundaries, AAA structure, no style assertions, etc.). This document only proposes *additions* on top of that baseline.

---

## TL;DR — Triage Table

| # | Tool / Practice | Priority | One-line rationale |
|---|---|---|---|
| 1 | `pytest-randomly` | **High** | Catches order-dependence and hidden shared state for the cost of one `uv add`. |
| 2 | `pytest-socket` (`--disable-socket`, allow `127.0.0.1`) | **High** | Forces real network calls to either be mocked or fail loudly — catches the “tests pass on my machine” class of bugs. |
| 3 | `time-machine` | **High** | Replaces ad-hoc clock mocking; ~100× faster than freezegun and friendlier with pytest assertion rewriting. |
| 4 | `django-htmx` + documented HTMX test patterns | **High** | Adds `request.htmx` and `HX-*` helpers; gives pytest a clean way to test 90 % of HTMX behaviour without a browser. |
| 5 | Branch coverage + `--cov-fail-under` policy | **High** | One-line config change; turns coverage into an actual gate, not a vanity number. |
| 6 | `pytest-xdist` (parallel) | **High** | pytest-django creates per-worker DBs out of the box; usually 3–5× faster locally and in CI. |
| 7 | Playwright `expect()` API + `get_by_role` / `get_by_text` rewrite | **High** | Auto-waiting kills `wait_for_selector` flakes; semantic locators stop coupling to CSS. |
| 8 | Playwright `trace: retain-on-failure` in CI | **High** | Frame-by-frame post-mortem of any CI failure; near-zero cost when tests pass. |
| 9 | factory_boy `Trait` + `RelatedFactory` discipline | **High** | Documenting the patterns prevents the “fixture explosion” that this codebase will hit as cohorts/registrations/progress graphs grow. |
| 10 | `hypothesis` + `hypothesis[django]` (targeted, not blanket) | **Medium** | Pays for itself on scoring strategies, deadline arithmetic, validators. Skip for CRUD. |
| 11 | `django-perf-rec` (or selective `assertNumQueries`) | **Medium** | Locks in N+1 fixes on hot views (cohort roster, progress dashboard). |
| 12 | `pytest-split` for CI sharding | **Medium** | Once the suite hits a few minutes, this is the simplest way to fan out across GitHub Actions runners. |
| 13 | `syrupy` for snapshot tests on rendered markdown / emails | **Medium** | High-signal where output is large and stable (markdown render, email HTML). Avoid for normal view tests — encourages lazy assertions. |
| 14 | `pytest-recording` (VCR) for outbound HTTP | **Medium** | Useful only if/when you start calling external APIs (xAPI LRS, payment, allauth social). Skip until then. |
| 15 | `django-test-migrations` | **Medium** | Catches migration-order bugs and missed `RunPython` reverse functions. Worth it the first time you bisect a broken `migrate`. |
| 16 | `pytest-icdiff` or `pytest-clarity` | **Low** | DX nicety; better assertion diffs. Pick one. |
| 17 | `mutmut` on a small high-value subset (quarterly) | **Low** | Surfaces tautological / weak tests. Don’t run on the whole codebase, don’t put in CI. |
| 18 | `dirty-equals` | **Low** | Useful in narrow spots (timestamps, partial dicts). Easy to overuse and hide intent. |
| 19 | `pytest-deadfixtures` | **Low** | Run occasionally to find unused fixtures. One-shot cleanup tool, not a CI gate. |
| 20 | `pytest-rerunfailures` | **Skip** | Masks flakes. Fix the test or delete it — your skill already says this. |
| 21 | `cosmic-ray` | **Skip** | Slower setup, slightly worse detection rate than `mutmut` for Python. Pick `mutmut` if you want mutation testing at all. |
| 22 | `freezegun` | **Skip** | `time-machine` is strictly better for new code. Keep only if you have legacy uses. |
| 23 | `assertpy` | **Skip** | Adds a fluent DSL on top of `assert`. Buys little; competes with native pytest assertion rewriting. |
| 24 | `snapshottest` (the older one) | **Skip** | Superseded by `syrupy`. |
| 25 | `pytest-django-queries` | **Skip** | Less actively maintained than `django-perf-rec`; worse ergonomics. |

---

## 1. Pytest Plugins Worth Adding

### 1.1 `pytest-randomly` — **High**

**What.** Randomises the order of modules → classes → tests, and reseeds `random`/`numpy`/`faker` per test. Prints the seed at the top of the run; you can reproduce with `-p no:randomly` or `--randomly-seed=N`.

**Why.** Test-order dependence is one of the highest-ROI bugs to find. It hides shared-state leaks (cached imports, module-level mutable defaults, factory sequence collisions, signal handlers re-attached without cleanup, leftover `Site.objects.get_current()` cache, etc.). With factory_boy + pytest-django + `mock_site_context`, the surface area for accidental cross-test state is real.

**Cost.** Negligible: one `uv add --dev pytest-randomly`. You will find a handful of failing tests on the first run. That is the point.

**Fit.** Excellent. Combines cleanly with `pytest-xdist`. Maintained by `pytest-dev`.

**Source:** [pytest-randomly on PyPI](https://pypi.org/project/pytest-randomly/) · [GitHub](https://github.com/pytest-dev/pytest-randomly)

---

### 1.2 `pytest-xdist` — **High**

**What.** Runs tests in parallel across N processes. `-n auto` uses all cores. `--dist loadfile` keeps tests from one file on the same worker (helpful for Playwright); `--dist loadgroup` for explicit groups.

**Why.** `pytest-django` already supports xdist — each worker gets its own DB (`test_db_gw0`, `test_db_gw1`, …). Easy 3–5× speedup. The faster the suite, the more often it runs, the less people skip it.

**Cost.** Minor. Tests must be order-independent (which they should be already; `pytest-randomly` enforces it). Test-creation logging gets interleaved; use `-v` carefully. Browser tests need `--dist loadfile` to avoid tab-thrashing the same `live_server`.

**Fit.** Excellent for unit/integration tests. For Playwright, see §5.6.

**Source:** [pytest-django parallel docs](https://pytest-django.readthedocs.io/en/latest/usage.html) · [pytest-xdist docs](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)

---

### 1.3 `pytest-socket` — **High**

**What.** A pytest plugin that monkey-patches `socket.socket` to raise `SocketBlockedError`. Add `--disable-socket` to addopts; allow `127.0.0.1` for the Postgres connection and Playwright `live_server`.

**Why.** Right now nothing prevents a test from accidentally hitting a real external service (HTTP fetch of a markdown asset, an LRS call, an OAuth provider via allauth, a CDN URL probe). On CI that becomes flaky; in dev that becomes “test ran 12 seconds, why?”. This plugin makes the boundary explicit and enforces your “mock at boundaries” rule mechanically.

**Cost.** Trivial. One config line. A few existing tests will need `@pytest.mark.enable_socket` or `@pytest.mark.allow_hosts(["127.0.0.1"])`.

**Fit.** Strong fit — directly enforces an existing principle in the testing skill.

**Source:** [pytest-socket on GitHub](https://github.com/miketheman/pytest-socket)

---

### 1.4 `time-machine` (replaces / supersedes `freezegun`) — **High**

**What.** Pin `datetime.now`, `time.time`, and friends to a fixed instant (or moving clock) via a context manager / decorator / pytest fixture. Adam Johnson’s benchmark shows ~100× faster than freezegun (16 µs vs 6.4 ms per call) because it patches CPython’s C functions in place rather than walking import graphs.

**Why.** You have time-shaped code: course deadlines, registration windows, cohort start/end, `student_progress` timestamps, `django-axes` lockouts, JWT/session expiry. Without a deterministic clock, those tests become flaky around midnight or when CI is slow.

**Cost.** ~Zero migration cost from nothing. If migrating from freezegun: API is similar (`with time_machine.travel("2026-01-01"):`).

**Fit.** Strong. CPython only — fine, you’re on 3.13.

**Caveat.** Don’t reach for this if a small refactor (inject a `now()` callable, or a “Clock” service) is cheaper. The “Clock pattern” usually beats time-mocking for code you own.

**Source:** [time-machine vs freezegun benchmark — Adam Johnson](https://adamj.eu/tech/2021/02/19/freezegun-versus-time-machine/) · [time-machine docs](https://time-machine.readthedocs.io/en/stable/comparison.html)

---

### 1.5 `syrupy` — **Medium** (narrow use)

**What.** Snapshot testing for pytest. `assert thing == snapshot` writes the value to a `.ambr` file on first run; subsequent runs compare. Update with `--snapshot-update`.

**Why (where it’s good).**
- Rendered markdown output (`content_engine`) — large, stable, human-readable.
- Email HTML (premailer output) — long, fiddly, regression-prone.
- API JSON shapes (django-ninja endpoints).

**Why (where it’s bad).** Tempting for view/template tests, but it encourages “re-blessing” the snapshot every time something changes — which is the opposite of the “independent oracle” principle in your testing skill. A snapshot test asserts *the output stays the same*, not *the output is correct*. Use sparingly and review snapshot diffs as carefully as code diffs.

**Cost.** Low.

**Fit.** Medium. Use only where the output is large, stable, and humans can eyeball-verify the diff.

**Caveat.** Doesn’t play nicely with `unittest.TestCase` subclasses (incl. Django’s); not an issue for your pytest-style codebase.

**Source:** [syrupy on GitHub](https://github.com/syrupy-project/syrupy) · [Simon Willison’s syrupy TIL](https://til.simonwillison.net/pytest/syrupy)

---

### 1.6 `django-perf-rec` — **Medium**

**What.** Adam Johnson’s tool. Records the SQL queries (and cache calls) for a block of code into a YAML file. Subsequent runs diff against the recorded queries and fail if anything changed (count, shape, or text). Better than raw `assertNumQueries(N)` because it tells you *which* query changed, not just that the count moved.

**Why.** Cohort rosters, student progress dashboards, course catalogue with permissions — these are exactly the views where N+1 regressions slip in after innocent template edits. Lock them down once and forget.

**Cost.** Low. Ships with a pytest plugin. Records live alongside tests.

**Fit.** Good. Pick 5–10 hot views, wrap their tests in `record_performance()`. Don’t blanket-apply.

**Alternative considered: `pytest-django-queries`** — less active, weaker diffing. **Skip** in favour of `django-perf-rec`.

**Source:** [django-perf-rec on PyPI](https://pypi.org/project/django-perf-rec/) · [GitHub](https://github.com/adamchainz/django-perf-rec)

---

### 1.7 `pytest-recording` (VCR.py wrapper) — **Medium** (deferred)

**What.** Records real HTTP traffic into YAML cassettes on first run; replays from cassette on subsequent runs. Decorate with `@pytest.mark.vcr`.

**Why.** Becomes the right answer the moment you start calling external services (xAPI LRS endpoints, allauth social login, S3 via django-storages, premailer fetching CSS, etc.).

**Cost.** Cassettes need maintenance when the upstream API changes. Filter sensitive headers (`Authorization`, cookies) explicitly via `vcr_config` or you’ll commit secrets.

**Fit.** Hold off until you have an actual outbound HTTP call worth recording. Until then, plain `mocker.patch` at the requests/httpx boundary is simpler.

**Source:** [pytest-recording](https://pypi.org/project/pytest-recording/)

---

### 1.8 `dirty-equals` — **Low**

**What.** Sentinel objects you can compare against: `IsNow(delta=2)`, `IsPositiveInt`, `IsPartialDict({"id": IsInt})`, `IsUUID`, etc.

**Why.** Tidy when asserting on responses with timestamps or auto-IDs.

**Cost.** Low, but every sentinel slightly weakens the assertion. Easy to slip from “the response contains a UUID” into “the response contains *anything*”.

**Fit.** Low priority. Reach for it at the spot where you’d otherwise pop the timestamp out of a dict before comparing.

---

### 1.9 `assertpy` — **Skip**

Fluent assertion library (`assert_that(x).is_equal_to(y).is_not_none()`). pytest already has assertion rewriting that gives you good diffs from plain `assert`. Adding a DSL makes assertions wordier without strengthening them. **Don’t add.**

---

### 1.10 `pytest-icdiff` / `pytest-clarity` — **Low**

DX plugins that prettify assertion diffs (icdiff renders side-by-side; clarity adds colour). Either is fine; pick one. They don’t change what tests do, just how failures read. **Pick at most one.**

---

### 1.11 `pytest-deadfixtures` — **Low**

Lists fixtures that are defined but never used. Run once a quarter, delete dead ones, move on. Don’t add to CI.

---

### 1.12 `pytest-sugar` — **Low**

Pretty progress bar + immediate failure printout. Conflicts with `pytest-xdist` in some terminals. Cosmetic; skip unless someone really wants it.

---

## 2. Property-Based / Generative Testing (Hypothesis)

### 2.1 When it pays off — **Medium, targeted**

Hypothesis generates examples for the *shape* of input you describe; if it finds a failing example it shrinks to the minimal one. Worth its weight in three FLS contexts:

1. **Scoring strategies** (`student_progress`). “For any combination of correct/incorrect form responses, the score is in `[0, 100]`.” “The score is monotonic in number of correct answers.” “Re-scoring an unchanged submission gives the same result.” These are *properties*, not examples — Hypothesis is the right tool.
2. **Deadline / window arithmetic.** “For any cohort with `start <= end`, the registration window contains `start` and excludes `end + 1ms`.” Edge cases around DST, leap years, empty windows are exactly what Hypothesis surfaces.
3. **Validators / sanitisers.** `nh3` HTML sanitisation, markdown rendering, email validation. Generate strings, assert invariants (output is always valid HTML, output never contains `<script>`, output is idempotent under re-sanitisation).

### 2.2 When it doesn’t — **Skip**

- CRUD round-tripping. Trust the ORM.
- View-level tests. Too much state to set up; Hypothesis shines on pure functions and small graphs.
- Anything that touches the database without `hypothesis[django]`’s `TestCase` integration — you’ll wear out fixtures.

### 2.3 Cost

- Slower: each test runs 100 examples by default. Mark expensive tests with `@settings(max_examples=20)`.
- Learning curve for `@composite` strategies and `assume`.
- `hypothesis[django]` provides `from_model(MyModel)` and a `TestCase` base — useful but doesn’t mix with `mock_site_context` cleanly. You’ll likely drive it through factories instead.

### 2.4 Recommendation

Add `hypothesis` (without the `[django]` extra to start). Pick ONE module — most likely `student_progress` scoring — and write 3–5 property tests. Evaluate after a month. Don’t mandate it project-wide.

**Source:** [Hypothesis for Django](https://hypothesis.readthedocs.io/en/latest/django.html) · [DRMacIver Django talk](https://drmaciver.github.io/hypothesis-talks/hypothesis-for-django.html)

---

## 3. Mutation Testing

### 3.1 `mutmut` vs `cosmic-ray`

Per the 2024-25 academic comparisons:

| | `mutmut` | `cosmic-ray` |
|---|---|---|
| Speed | ~1200 mutants/min (AST-based) | Slower |
| Detection rate | ~88.5 % | ~82.7 % |
| Setup | Simple (`mutmut run`) | Lengthy config file |
| Build-tool integration | Limited | Better |
| Maintenance | More active | Active |

For Python on a Django project, `mutmut` wins.

### 3.2 Worth running? — **Low**

Mutation testing is a *meta-test*: it doesn’t find bugs in your code, it finds weak tests. The signal it produces (“this mutation survives — your test would pass even if the code were wrong”) is exactly what catches the tautological tests your skill warns against.

### 3.3 What to run it on

**Don’t** run on the whole codebase — Django views and templates have many “mutations” that are false positives (changing a default that’s never observable). Restrict to:

- `freedom_ls/student_progress/scoring/*.py`
- `freedom_ls/content_engine/markdown_render.py`
- Any pure validator or business-rule module

**When.** Quarterly, manually. Not in CI. Treat each surviving mutation as a “write a better test” ticket.

**Source:** [Mutmut announcement](https://hackernoon.com/mutmut-a-python-mutation-testing-system-9b9639356c78) · [Mutation testing tools comparison (IEEE)](https://ieeexplore.ieee.org/document/10818231/)

---

## 4. HTMX-Specific Testing (in pytest, without a browser)

You should be able to cover ~90 % of HTMX behaviour in pytest. Playwright is for the remaining 10 %.

### 4.1 Use `django-htmx` — **High**

`django-htmx` (Adam Johnson) provides `request.htmx` middleware giving you `request.htmx` (truthy if `HX-Request: true`), `request.htmx.trigger`, `.trigger_name`, `.target`, `.boosted`, etc. It also ships `HttpResponseClientRedirect`, `HttpResponseLocation`, `trigger_client_event(response, "name", payload)`, and `reswap` / `retarget` helpers. Without it, you’re writing string headers by hand.

If FLS isn’t already using it: add it.

**Source:** [django-htmx middleware docs](https://django-htmx.readthedocs.io/en/latest/middleware.html) · [django-htmx HTTP tools](https://django-htmx.readthedocs.io/en/latest/http.html)

### 4.2 Test pattern: simulate the HTMX header

```python
def test_partial_returned_for_htmx_request(client, mock_site_context):
    student = StudentFactory()
    client.force_login(student.user)

    response = client.get(
        reverse("student_interface:topic_detail", args=[topic.id]),
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "<html" not in response.content.decode()  # no full page chrome
    assertContains(response, "topic-body")           # partial rendered
```

Two tests per dual-rendering view: full-page (no header) and partial (with header). One assertion per test.

### 4.3 Test pattern: response headers

```python
def test_form_submission_triggers_client_event(client, mock_site_context):
    response = client.post(url, data, headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert response["HX-Trigger"] == "topic-completed"
```

For JSON-payload triggers (`HX-Trigger: {"toast": {"msg": "..."}}`), parse and assert on the dict — never on the JSON string. The string ordering is not guaranteed.

### 4.4 Validation errors → HTTP 422

Your conventions document already says: HTMX validation errors return 422 with the re-rendered partial. Test pattern:

```python
def test_invalid_form_returns_422_with_error_partial(client, mock_site_context):
    response = client.post(url, {"email": "not-an-email"},
                            headers={"HX-Request": "true"})

    assert response.status_code == 422
    assertContains(response, "Enter a valid email", status_code=422)
```

422 (not 400) so HTMX swaps the error markup back into the form. `htmx.config.responseHandling` in newer HTMX versions makes this configurable — keep 422 as the convention.

### 4.5 OOB swaps

Out-of-band swaps are markup, not headers (`<div hx-swap-oob="true" id="cart-count">3</div>`). Test by parsing the response with BeautifulSoup or by `assertContains` on the OOB element’s sentinel text/ID. **Don’t** snapshot the full body for OOB tests — too brittle.

### 4.6 What still belongs in Playwright

- `hx-swap` actually swapping into the DOM (this is HTMX runtime, not yours — but smoke-test once).
- `hx-trigger="every 5s"` polling.
- Modal flows where `HX-Trigger` fires JS that the server can’t observe.
- Anything that interacts with Alpine.js state.
- Multi-step flows where the next request depends on JS-rendered state from the previous.

### 4.7 Anti-patterns

- Asserting on `response.content` as a string with regex. Use `assertContains` / parse HTML.
- Asserting CSS classes (already in your skill — restate for HTMX context: don’t test that the swapped fragment has `class="error"`, test that the error message appears).
- Using Playwright when a header simulation will do. Each Playwright test costs ~2–10 seconds; a pytest equivalent costs ~30 ms.

---

## 5. Playwright Patterns 2026

### 5.1 Use `expect()` and stop using `wait_for_selector` — **High**

The current Playwright API has two assertion families:

1. **Locator assertions** via `expect()`: `expect(page.get_by_text("Saved")).to_be_visible()`. These auto-retry with a configurable timeout (default 5s) and only fail when the assertion has truly not held during the window.
2. **Page state assertions**: `expect(page).to_have_url(...)`, `to_have_title(...)`.

Both are *auto-waiting*. They replace virtually every `wait_for_selector` / `time.sleep` / `page.wait_for_timeout` call.

```python
# OLD (current FLS playwright skill recommends)
page.click('text="Enroll"')
page.wait_for_selector('.success-message')
assert page.is_visible('text="Enrolled"')

# NEW (2026 idiom)
page.get_by_role("button", name="Enroll").click()
expect(page.get_by_text("Enrolled")).to_be_visible()
```

The current `playwright-tests` skill leans on `wait_for_selector` and `is_visible`. Update it.

**Source:** [Playwright auto-waiting](https://playwright.dev/python/docs/actionability) · [Playwright best practices](https://playwright.dev/docs/best-practices)

### 5.2 Locator priority (top → bottom) — **High**

1. `page.get_by_role("button", name="Submit")` — accessibility-first, the way real users (and screen readers) find elements.
2. `page.get_by_label("Email")` — for form fields.
3. `page.get_by_placeholder(...)`, `page.get_by_text(...)`, `page.get_by_alt_text(...)`.
4. `page.get_by_test_id(...)` — escape hatch; add `data-testid` to templates only when accessibility-based selection is genuinely impossible.
5. CSS / XPath — last resort. Brittle. Couples tests to markup.

The current skill recommends `text="Submit"` and `role=button[name="Submit"]`. The string-form selectors still work but the `get_by_*` builder API is the documented preference now and gives better error messages.

### 5.3 Network mocking — **Medium**

Use `page.route("**/api/external/**", lambda route: route.fulfill(...))` to stub third-party calls (analytics, CDN font fetches, anything you don’t want hitting prod from CI). Lets you simulate slow networks (`route.continue_(delay=2000)`) and error responses without modifying app code.

For FLS this is mostly relevant if/when you add an external xAPI sink, payments, or social-login providers.

### 5.4 Trace viewer — **High**

Configure once in `conftest.py`:

```python
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "record_video_dir": None}

# In playwright config / fixture
context.tracing.start(screenshots=True, snapshots=True, sources=True)
# at end of test
context.tracing.stop(path="trace.zip")
```

Or simpler: pass `--tracing=retain-on-failure` to pytest. View with `playwright show-trace trace.zip`. Trace contains DOM snapshots at every action, network log, console, and screenshots — turns “flaky on CI, can’t reproduce locally” from a 2-hour bisect into a 5-minute click-through.

In CI, upload the `trace.zip` as a build artefact on failure.

**Source:** [Playwright trace viewer](https://playwright.dev/python/docs/trace-viewer)

### 5.5 Anti-patterns to retire

- `time.sleep(N)` — always wrong, trace shows you why.
- `page.wait_for_timeout(N)` — slightly less wrong but still wrong.
- CSS selectors with `>` chains (`'.form > .btn-submit'`).
- Asserting on element existence without visibility (`locator.count() > 0`).
- Multiple actions per test without `expect()` between them — race conditions hide here.
- Sharing a logged-in browser context across unrelated tests without resetting state.

### 5.6 Parallelism for Playwright — **Medium**

`pytest-xdist -n auto --dist loadfile` keeps all tests in one file on one worker — important because Playwright fixtures (especially `live_server` and any per-file login state) don’t want to thrash. With Django’s test runner each xdist worker also gets its own DB, so per-file isolation is real.

Don’t go beyond `-n 4` for Playwright unless your CI box has the headroom — browsers are RAM-hungry.

**Source:** [Playwright parallel patterns](https://playwright.dev/docs/test-parallel) · [pytest-xdist distribution modes](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)

### 5.7 Login fixture: do it once

Logging in via the UI in every test is the #1 reason E2E suites take 20 minutes. Two options:

- **Storage state.** Log in once in a session-scoped fixture, save `context.storage_state(path=...)`, reuse via `browser.new_context(storage_state=...)`.
- **Programmatic login.** Skip the UI entirely: `client.force_login()` against `live_server`, then attach the resulting session cookie to the Playwright context.

Either is fine. Both are documented Playwright patterns and both are 5–20× faster than UI login.

---

## 6. Coverage Strategy

### 6.1 Turn on branch coverage — **High**

Statement coverage misses every `if/else` where one branch has no test. Branch coverage catches it. One config line:

```toml
[tool.coverage.run]
branch = true
source = ["freedom_ls"]
omit = ["*/migrations/*", "*/tests/*", "*/factories.py"]
```

### 6.2 Set a `--cov-fail-under` floor — **High**

Pick a number (start with where you are today, e.g. 70 %). Add to pytest addopts:

```toml
addopts = "--strict-markers --cov=freedom_ls --cov-branch --cov-fail-under=70"
```

Important caveat from the docs: `--cov-fail-under` is a *total* threshold. You can add untested code as long as the average stays above the floor. Mitigate by:

- **Ratcheting.** Bump the floor any time the actual % rises by ≥1 point.
- **Per-module thresholds.** Coverage.py 7 supports per-package thresholds via the `report.fail_under` family + selective reports, or use a script that parses `coverage.json` and enforces per-app minimums (e.g. `student_progress` ≥ 90 %, `educator_interface` ≥ 75 %).

### 6.3 Coverage is a smoke alarm, not a thermometer

Your skill already says “coverage is a signal, not a goal”. Reinforce: 95 % branch coverage with tautological assertions is worse than 60 % with strong ones. Mutation testing on a hot subset (§3) is the better quality signal.

### 6.4 Don’t chase 100 %

Excludes that are honest: `if TYPE_CHECKING`, `__repr__` for debugging, defensive `else: raise NotImplementedError`. Mark with `# pragma: no cover` and move on.

**Source:** [coverage.py config](https://coverage.readthedocs.io/en/latest/config.html) · [pytest-cov docs](https://pytest-cov.readthedocs.io/en/latest/config.html)

---

## 7. Test Data Strategy (factory_boy)

### 7.1 The problem to head off

LMS data graphs get deep fast: `Site → Cohort → Student → Registration → Course → Topic → ProgressRecord`. Naïve factories either:

- Build the whole graph every time → slow tests, flaky on factory-sequence collisions.
- Or each test builds a hand-rolled mini-graph → repetition, drift, fixture sprawl.

### 7.2 The factory_boy pattern matrix — **High** (document it)

| Relationship direction | Use | Example |
|---|---|---|
| FK on the model under construction | `SubFactory` | `cohort = SubFactory(CohortFactory)` |
| Reverse FK (child of the model under construction) | `RelatedFactory` | `RelatedFactory(RegistrationFactory, "cohort")` |
| Many-to-many | `post_generation` | `def students(self, create, extracted): ...` |
| Optional / variant state | `Trait` | `class Params: full = Trait(is_active=True, ...)` |
| Multiple children | `RelatedFactoryList` | `RelatedFactoryList(TopicFactory, "course", size=5)` |

**Rules of thumb:**
- If a field is `null=True`, default it to `None` and put non-null variants behind a Trait. This stops factories silently building expensive graphs.
- Use `build()` (no DB write) wherever possible in unit tests that don’t need persistence.
- `mute_signals(post_save)` when a `RelatedFactory` causes signal cascades (e.g. progress recalculation).

### 7.3 When to switch to seeded fixtures

If three+ tests need the same 12-object graph and the construction is genuinely expensive, build it once via a session-scoped fixture that uses factories internally. Don’t build “realistic seed data” by writing it longhand — that drifts from the schema.

If your `demo_content/` is already a useful realistic dataset, a `--reusedb` flow with a Django data migration that loads it once can be faster than per-test factory construction for integration tests. Trade-off: shared data leaks between tests. Only do this if the test class is read-only.

**Source:** [factory_boy recipes](https://factoryboy.readthedocs.io/en/stable/recipes.html) · [factory_boy reference](https://factoryboy.readthedocs.io/en/stable/reference.html)

### 7.4 `pytest-factoryboy` — **consider**

Auto-registers each `Factory` as a pytest fixture. `def test_x(student): ...` works without an explicit fixture. Cuts boilerplate but adds magic; some teams find the magic confusing. Optional.

---

## 8. CI Hygiene

### 8.1 Sharding with `pytest-split` — **Medium**

Once the suite hits ~5 minutes, split it across N GitHub Actions runners:

```yaml
strategy:
  matrix:
    group: [1, 2, 3, 4]
steps:
  - run: pytest --splits 4 --group ${{ matrix.group }}
```

`pytest-split` reads `.test_durations` (commit it) and assigns roughly equal-time chunks to each shard. Combine with `pytest-xdist` *inside* each shard for two-level parallelism on multi-core runners.

**Source:** [pytest-split](https://jerry-git.github.io/pytest-split/) · [Blazing fast CI with pytest-split](https://blog.jerrycodes.com/pytest-split-and-github-actions/)

### 8.2 `--lf` / `--ff` workflows — **High** (doc, no install)

`pytest --lf` reruns last-failed only; `pytest --ff` runs failed first. In local dev these turn a 90s suite into a 3s feedback loop while iterating on a fix. Document in CONTRIBUTING.

`pytest --sw` (stepwise) stops at the first failure and resumes from there next time — useful when refactoring.

### 8.3 Slowest-test reporting — **High** (doc, no install)

`pytest --durations=20` prints the 20 slowest tests. Run weekly or in a CI nightly. Anything over 1s in unit tests needs investigation. Most “slow tests” are accidental DB writes or network calls (which `pytest-socket` would prevent).

### 8.4 Flaky-test detection

**Don’t use `pytest-rerunfailures` to make CI green.** It hides flakes, the count grows silently, and one day half the CI is reruns.

What to do instead:
- **Fail loudly on flake.** If a test is flaky, mark it `@pytest.mark.flaky` (custom marker) AND open a ticket. Limit total flaky tests to e.g. 5 — refuse to merge new ones beyond that.
- **Periodic flake hunt.** `pytest-flakefinder` runs each test N times to surface order-independent flakes. Run quarterly.
- **`pytest-randomly` + `pytest-xdist` in CI** make flakes appear faster.

If you absolutely must rerun (e.g. a known-flaky third-party browser interaction), use a marker — `@pytest.mark.flaky(reruns=2)` — *not* a global `--reruns`. Each marker is a TODO to fix.

**Source:** [pytest flaky-tests guide](https://docs.pytest.org/en/stable/explanation/flaky.html)

### 8.5 Test artefacts

- Upload Playwright `trace.zip` on failure (§5.4).
- Upload coverage XML to Codecov / equivalent.
- Print the `pytest-randomly` seed in CI so a flaky test can be reproduced locally with `--randomly-seed=N`.

---

## 9. Other 2026 Wins for a Django+HTMX Project

### 9.1 `django-test-migrations` — **Medium**

Tests that schema migrations and data migrations actually work — including reverse migrations and ordering. Catches:

- Data migrations that crash on real-shape data.
- Migrations renamed but with un-renamed dependencies.
- `RunPython` without a `reverse_code` (auto-detected by their Django check).

Worth adopting the first time you hit a “migrate failed in staging, rolled back, can’t roll forward either” incident.

**Source:** [django-test-migrations](https://github.com/wemake-services/django-test-migrations)

### 9.2 Pre-commit hook running tests on changed files

You already have pre-commit. Adding `pytest --picked` (via `pytest-picked`) runs only tests for changed files on commit. Sub-second feedback at commit time. Don’t make it the *only* gate — CI still runs the full suite.

### 9.3 Django’s own `--parallel` — **Skip in your context**

You’re on pytest, not Django’s test runner. The pytest-xdist path is the right one.

### 9.4 Type-checking tests too

You run `pyright` / mypy on production code; consider running it on tests too. Catches “factory returns a Mock, not a Student” kind of bugs. The `disable_error_code` overrides for tests in your `pyproject.toml` already loosen things sensibly. Tighten over time.

### 9.5 `pytest-recording` for golden tests of email rendering

If you generate emails with premailer + Django templates, golden-file tests of the rendered HTML (via `syrupy` or hand-managed snapshots) catch CSS-inlining regressions that nothing else will. Strong ROI for the few hours of setup.

### 9.6 Visual regression testing — **Skip for now**

Tools like `pixelmatch`, Playwright’s `expect(page).to_have_screenshot()`, Percy, Chromatic. High value for design-systems projects. For an LMS with a focus on functionality and accessibility, the maintenance burden (every browser update changes pixels) typically outweighs the bug-find rate. Revisit if you ship a public-facing marketing site.

### 9.7 Accessibility testing — **Medium**

`axe-playwright-python` runs axe-core against any page. Two-line addition that finds real bugs. Worth adding to a handful of high-traffic Playwright tests:

```python
from axe_playwright_python.sync_playwright import Axe
results = Axe().run(page)
assert results.violations_count == 0, results.generate_report()
```

A11y regressions are exactly the kind of thing humans miss in code review. Brand guidelines + accessibility testing is a strong combo.

---

## Appendix A — Suggested First Wave

If this is too long to act on, do these six things first:

1. `uv add --dev pytest-randomly pytest-socket pytest-xdist time-machine`
2. Add `--disable-socket --cov-branch --cov-fail-under=<current>` to pytest addopts. Allow `127.0.0.1`.
3. Update the `playwright-tests` skill: `expect()` API + `get_by_role` priority + trace on failure.
4. Document the four HTMX test patterns from §4 in the testing skill.
5. Add `django-htmx` if not already present.
6. Pick one `student_progress` scoring module and write 3 Hypothesis property tests as a proof-of-value.

Total time: a half-day of work, immediate dividends in catching latent bugs.

## Appendix B — Suggested Second Wave (after 4–6 weeks)

7. `django-perf-rec` on top 5 hottest views.
8. `pytest-split` once CI > 5 min.
9. `syrupy` for email/markdown render tests.
10. `mutmut` quarterly on scoring + validators only.
11. `axe-playwright-python` on top 5 Playwright tests.

## Appendix C — Tools explicitly evaluated and rejected

- `freezegun` — superseded by `time-machine`.
- `assertpy` — adds verbosity without strengthening assertions.
- `snapshottest` — superseded by `syrupy`.
- `pytest-django-queries` — superseded by `django-perf-rec`.
- `cosmic-ray` — `mutmut` is the better Python choice.
- `pytest-rerunfailures` (as a default) — masks flakes; conflicts with the existing skill rule “delete flaky tests.”

---

## Sources

- [pytest-django parallel docs](https://pytest-django.readthedocs.io/en/latest/usage.html)
- [pytest-xdist distribution modes](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)
- [pytest-randomly on GitHub](https://github.com/pytest-dev/pytest-randomly)
- [pytest-socket on GitHub](https://github.com/miketheman/pytest-socket)
- [time-machine vs freezegun benchmark — Adam Johnson](https://adamj.eu/tech/2021/02/19/freezegun-versus-time-machine/)
- [time-machine comparison docs](https://time-machine.readthedocs.io/en/stable/comparison.html)
- [syrupy on GitHub](https://github.com/syrupy-project/syrupy)
- [Simon Willison’s syrupy TIL](https://til.simonwillison.net/pytest/syrupy)
- [django-perf-rec on GitHub](https://github.com/adamchainz/django-perf-rec)
- [pytest-recording](https://pypi.org/project/pytest-recording/) and [VCR.py docs](https://vcrpy.readthedocs.io/)
- [Hypothesis for Django](https://hypothesis.readthedocs.io/en/latest/django.html)
- [DRMacIver Hypothesis Django talk](https://drmaciver.github.io/hypothesis-talks/hypothesis-for-django.html)
- [Mutmut intro article — HackerNoon](https://hackernoon.com/mutmut-a-python-mutation-testing-system-9b9639356c78)
- [Mutation testing tools comparison — IEEE](https://ieeexplore.ieee.org/document/10818231/)
- [django-htmx middleware](https://django-htmx.readthedocs.io/en/latest/middleware.html)
- [django-htmx HTTP tools](https://django-htmx.readthedocs.io/en/latest/http.html)
- [HTMX HX-Trigger response headers](https://htmx.org/headers/hx-trigger/)
- [Playwright Python auto-waiting](https://playwright.dev/python/docs/actionability)
- [Playwright best practices](https://playwright.dev/docs/best-practices)
- [Playwright Python locators](https://playwright.dev/python/docs/locators)
- [Playwright trace viewer (Python)](https://playwright.dev/python/docs/trace-viewer)
- [Playwright Python pytest plugin](https://playwright.dev/python/docs/test-runners)
- [Playwright parallelism docs](https://playwright.dev/docs/test-parallel)
- [coverage.py configuration reference](https://coverage.readthedocs.io/en/latest/config.html)
- [pytest-cov configuration](https://pytest-cov.readthedocs.io/en/latest/config.html)
- [factory_boy recipes](https://factoryboy.readthedocs.io/en/stable/recipes.html)
- [factory_boy reference](https://factoryboy.readthedocs.io/en/stable/reference.html)
- [factory-boy best practices (camilamaia)](https://github.com/camilamaia/factory-boy-best-practices)
- [pytest-split](https://jerry-git.github.io/pytest-split/)
- [Blazing fast CI with pytest-split — Jerry Codes](https://blog.jerrycodes.com/pytest-split-and-github-actions/)
- [pytest flaky-tests guide](https://docs.pytest.org/en/stable/explanation/flaky.html)
- [pytest-rerunfailures](https://github.com/pytest-dev/pytest-rerunfailures)
- [django-test-migrations](https://github.com/wemake-services/django-test-migrations)
- [pytest-icdiff](https://github.com/hjwp/pytest-icdiff)
- [pytest-clarity](https://pypi.org/project/pytest-clarity/)
- [pytest-deadfixtures](https://github.com/jllorencetti/pytest-deadfixtures)
