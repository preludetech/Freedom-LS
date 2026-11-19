# Best practices: cross-tenant authorisation on shared content

Scope: practices only; the grant model and prior research are in the two other research files and `answers.md`.

## 1. 404 vs 403 for cross-tenant objects
- OWASP IDOR Prevention Cheat Sheet: check object-level authorisation on every access. Use a scoped lookup, not fetch-then-check. If existence is sensitive, return the same response for "missing" and "forbidden", which means 404. https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- Applied here: a course with no grant to the caller's org must give 404 on detail and preview. That matches the `answers.md` decision. A course the org can `see` but not `preview` is different: the org may know it exists, so preview can return 404 (consistent) or 403. Pick one and test it. We recommend 404 so one rule covers all denials.
- The 404 must be indistinguishable: same template, status and timing-insensitive content as a truly missing slug. Don't leak existence through redirects or different messages.
- Use `get_object_or_404(visible_courses(org), slug=...)`, with the scoped queryset as the first argument. Never `get_object_or_404(Course, ...)` followed by `if not can_x: raise Http404`. The second form works but is easy to forget.

## 2. Queryset-level scoping vs per-view checks
- Make the queryset the primary control: one function, e.g. `courses_visible_to(org, flag="see")`, returns a `QuerySet`. Lists, pickers, detail lookups and POST handlers all start from it. Forgetting to filter then fails loudly in review, because there is one obvious entry point.
- Keep a single predicate form for non-queryset cases, e.g. `can(org, course, flag)`, implemented over the same grant data so the two cannot drift. A test should assert that they agree for every row of the matrix.
- Prefer a custom manager/QuerySet method (`Course.objects.visible_to(org)`) to scattered `Q` expressions. This is the pattern the Django docs endorse for reusable query logic: https://docs.djangoproject.com/en/stable/topics/db/managers/
- Per-view decorators or mixins are fine for the "which org am I" step, but should not hold the grant logic.
- Existing-registration visibility is a union: `Q(owned) | Q(grant_see) | Q(registration_for_org)`. Use `Exists(...)` subqueries, not joins, so rows don't duplicate. Apply `.distinct()` only if unavoidable.
- Do not rely on UI hiding. Pickers narrowing options is a convenience only.

## 3. Re-check on POST actions, not just pickers
- OWASP: verify on every access attempt, and never trust identifiers in URLs or POST bodies. A picker that hides a course doesn't stop a crafted POST with `course_id`.
- Resolve the submitted course through the same scoped queryset with the required flag (`register` for registration actions; `see` for read). An out-of-scope ID then fails exactly like a bad ID: 404 for the page, or a 422 form error ("invalid choice") for an HTMX form. In a Django `ModelChoiceField`, set `queryset=` to the scoped queryset so validation does this for free.
- Re-check at the moment of the write, not only at form render. A grant may be removed between render and submit.
- Cover bulk/cohort paths and any "re-register", "copy" or "import" endpoints. These are the usual missed surfaces.
- The `register` bypass of price/application gates must be decided inside the one service that creates the registration, so a view cannot skip the grant check while still skipping the gate. Gate-skipping without a verified `register` flag should be impossible by construction.

## 4. Validate grant declarations at load time
Fail fast when content is loaded or validated, not when a request arrives. Pydantic-style validation fits the existing content schema:
- Unknown org slug: error naming the file and slug. Don't silently ignore it, because that turns a typo into a hidden course (or, worse, a stale grant that applies if the slug is later created).
- Duplicate org entries: error, not last-wins. Duplicates hide contradictory flags.
- Normalise implied flags: `register` and `preview` imply `see`. Expand at load so stored data and the runtime check both see an explicit `see=True`. The check code should then never special-case implication. Warn or accept a redundant `see: true` alongside `register`; don't reject it.
- Reject a grant naming an owner org (it is redundant and probably a mistake), a wildcard `*` (per `answers.md`), and unknown flag keys (`extra="forbid"`).
- Reject non-boolean flags (no `"yes"` strings coerced). Use strict booleans.
- Make loading idempotent: the DB grant rows should be replaced to match the file, so removing a grant from front matter revokes it on the next load. Test revocation explicitly.
- Collect all errors across files and report them together, so authors aren't fixing one at a time.

## 5. Avoiding N+1 on per-row grant checks
- Don't call `can(org, course, flag)` per row in templates. For lists, filter in SQL via the scoped queryset, so denied rows never load.
- For rows that need a per-row flag shown (e.g. a "Preview" button only when `preview` is granted), annotate in the same query: `.annotate(can_preview=Exists(Grant.objects.filter(course=OuterRef("pk"), org=org, preview=True)) | Q(owned))`. Then the template reads an attribute.
- If a predicate must run on a Python list, fetch the org's grants once into a dict `{course_id: flags}` (one query) and look up in memory. Cache per request, not across requests, to avoid stale grants.
- Add `assertNumQueries` / `django_assert_num_queries` tests on list and picker views with N courses and with 2N courses, and assert the count is equal. This catches regressions. https://docs.djangoproject.com/en/stable/topics/db/queries/ and pytest-django `django_assert_num_queries`: https://pytest-django.readthedocs.io/en/latest/helpers.html
- Use `select_related`/`prefetch_related` as the repo convention requires. Grants held as a front-matter list may be stored as a DB table with an index on `(org, course)`.

## 6. Testing authorisation matrices
- Parametrise over the cross product: viewer org {owner, granted-see, granted-register, granted-preview, granted-all, ungranted, ungranted-with-own-registration, ungranted-with-other-org's-registration} × surface {course list, learner picker, cohort picker, detail, preview, register POST, bulk POST} × expected outcome {visible/200, 404, 422}. Use `pytest.mark.parametrize` with ids, and keep the expected-outcome table as one readable data structure in the test file, so reviewers can read the policy.
- Assert both directions: allowed paths work (guards against over-blocking) and denied paths return the same response as a nonexistent slug. Compare the denied response to a real 404, not just the status code.
- Include negative edge cases: no organisations on the course (today's behaviour retained), implied flags, grant removed mid-flow (render, then revoke, then POST), registration held by a different org (must not show), and cross-site boundaries for the site-aware models.
- Add a "completeness" test: enumerate every URL pattern in the educator app that takes a course identifier (via the URL resolver) and fail if one isn't in the matrix's surface list. That catches a new endpoint nobody guarded.
- Cross-check the queryset function and the predicate `can()` against each other for every matrix row (see section 2).
- Test the loader separately: one test per validation rule in section 4, plus a round-trip that revoking a grant in the file removes access.
- OWASP's testing advice matches this: test with multiple accounts across read/create/update/delete operations.

## Recommendations (short)
1. One `visible_to(org, flag)` queryset method, used by every surface; a `can()` predicate derived from the same data.
2. 404 for every denial; scoped lookups, never fetch-then-check.
3. POST handlers and form fields use the same scoped queryset; the registration service owns the gate bypass.
4. Strict, load-time validation with implied flags expanded; DB grants re-synced from the files.
5. SQL-side filtering and annotation; one query-count test per list.
6. A parametrised org × grant × surface matrix plus a URL-completeness test.

status: ok · reason: web sources limited to the OWASP IDOR cheat sheet (fetched); Django and pytest-django links are cited from general knowledge, not fetched
