# Test Suite Audit — Anti-Patterns & Coverage Gaps

Audit of 71 test files (~12k lines) across 15 apps in `freedom_ls/`. Sampled widely; representative examples cited per category.

## Summary

| Category | Count (est.) | Severity |
|---|---|---|
| CSS / styling assertions | ~12 | HIGH |
| Weak assertions (only `status_code == 200`) | ~8 | HIGH |
| Tautological tests (re-derive expected) | ~3 | HIGH |
| `.objects.create()` instead of factories | ~16 | MEDIUM |
| Copy-pasted tests (parametrize candidates) | ~8 groups | MEDIUM |
| Hardcoded config-value assertions | ~2 | MEDIUM |
| Trivial CRUD / model default tests | ~6 | MEDIUM |
| Multi-act tests | ~5 | LOW |
| Conditionals/loops in test bodies | a few | LOW |
| Poor test names | ~4 | LOW |
| E2E (Playwright) issues | ~2 | MEDIUM |
| Apps with **zero tests** | 3 | HIGH |

Mocking discipline is generally good — boundary mocks only, very few internal-helper mocks detected.

---

## 1. CSS / styling assertions (HIGH)

Couples tests to design; breaks on every Tailwind tweak. User has explicit feedback against this.

- `freedom_ls/content_engine/tests/test_markdown_utils.py:53` — `assert "border-primary" in result`, `assert "bg-warning/10" in result`
- `freedom_ls/base/tests/test_button_component.py:40-42` — `assert "animate-spin" in result`, `assert "htmx-hide-on-request" in result`, `assert "htmx-show-on-request" in result`
- `freedom_ls/panel_framework/tests/test_htmx_navigation.py:140` — asserts on full escaped div including class string

Fix: assert the *information* (callout text, icon presence by accessible label, button label) instead of class names.

## 2. Weak view assertions (HIGH)

Tests that stop at `status_code == 200` even when the view does real work.

- `freedom_ls/student_interface/tests/test_course_list_views.py:36-44` — has follow-on assertions but they only check attribute *presence* (`hasattr(...)`)
- `freedom_ls/webhooks/tests/test_send_test_views.py` — several views asserted only on status

Fix: assert on `response.context[...]` values or rendered content the user actually sees.

## 3. Tautological tests (HIGH)

Re-derives expected from input using the same formula as the SUT.

- `freedom_ls/student_management/tests/test_course_progress_calculation.py:14-41` — `assert percentage == 67  # round(66.666...)` — comment shows the test re-applied the same rounding logic
- `freedom_ls/webhooks/tests/test_delivery.py:116-139` — `test_later_retries_use_correct_base_delays` loops over `RETRY_DELAYS` and rederives jitter window

Fix: hard-code at least one known-good oracle per behaviour (`2 of 3 → 67`).

## 4. `.objects.create()` instead of factories (MEDIUM)

~16 instances. Often where a factory doesn't yet exist (Site, SiteSignupPolicy, ObjectRoleAssignment, SystemRoleAssignment, framework `StubModel`).

- `freedom_ls/accounts/tests/test_allauth_signup_policy.py` — `Site.objects.create(...)`, `SiteSignupPolicy.objects.create(...)`
- `freedom_ls/role_based_permissions/tests/test_utils.py:98-104` — `ObjectRoleAssignment.objects.create(...)`
- `freedom_ls/role_based_permissions/tests/test_models.py:71-74` — `SystemRoleAssignment.objects.create(...)`
- `freedom_ls/panel_framework/tests/test_tabs.py` — `StubModel.objects.create(...)`

Fix: add the missing factories, then sweep.

## 5. Copy-paste tests that should be parametrized (MEDIUM)

- `freedom_ls/student_progress/tests/test_form_progress_score_quiz.py:18-62` and `:65-106` — `single_correct_answer` / `single_incorrect_answer` differ only in selected option + expected score
- `freedom_ls/base/tests/test_context_processors.py:44-56` — three `get_text_color` tests with identical shape
- `freedom_ls/student_interface/tests/test_course_list_views.py:36-92` — `partial_list_courses` variations

## 6. Hardcoded config-value assertions (MEDIUM)

Tests that fail when a config table is correctly edited.

- `freedom_ls/role_based_permissions/tests/test_roles.py:32-50` — `assert len(BASE_ROLES["site_admin"].permissions) == 8` (and 3, 2 for instructor/ta)
- `freedom_ls/base/tests/test_context_processors.py:40-42` — `assert branch_name_to_color("main") == "#a937b4"` (testing a deterministic hash output)

Fix: assert on *structure* / *invariants* (e.g. site_admin has more permissions than instructor; permissions are a subset of the registered set).

## 7. Trivial CRUD / model-default tests (MEDIUM)

Re-tests Django ORM defaults.

- `freedom_ls/role_based_permissions/tests/test_models.py:47-90` — `test_create_assignment`, `test_is_active_default_true`
- `freedom_ls/webhooks/tests/test_models.py:82-92` — `test_new_fields_default_to_empty` asserts each field equals `""` after `refresh_from_db`

## 8. Conditionals / loops in test bodies (LOW)

- `freedom_ls/webhooks/tests/test_delivery.py:129-139` — `for i, base_delay in enumerate(RETRY_DELAYS):` inside a test (overlap with #3)

## 9. Manual `Site.objects.create()` instead of fixture (MEDIUM)

- `freedom_ls/accounts/tests/test_user_manager.py` — manually creates `forced_site` and `domain_site` rather than using `mock_site_context` + factory

## 10. Playwright (E2E) issues (MEDIUM)

`freedom_ls/student_interface/tests/e2e/test_course_toc.py` is generally clean (semantic locators, no `time.sleep`). Minor: hardcoded localStorage key string `coursePart_{course.slug}_2` (line 114-115); inline `evaluate("localStorage.clear()")` rather than a fixture (line 54).

## 11. Coverage gaps — apps with zero tests (HIGH)

| App | Test files |
|---|---|
| `app_authentication` | 0 |
| `xapi_learning_record_store` | 0 |
| `qa_helpers` | 0 (probably fine — it's helpers for QA itself) |

Of these, `app_authentication` and `xapi_learning_record_store` are the real concerns — both touch security/integration boundaries.

---

## Themes for batched / phased work

Each theme could be its own PR (or its own spec, per the user's `testing-best-practice-phase-N-*` suggestion).

### Phase 1 — Drop the brittle stuff (low risk, high confidence)
- Delete CSS class assertions (~12 sites)
- Remove hardcoded config-value assertions (~2)
- Delete trivial model-default tests (~6)

Mostly deletions and small rewrites. Net code goes down.

### Phase 2 — Strengthen weak assertions (catches real bugs)
- Sweep view tests that stop at `status_code == 200`; add context/content assertions
- Add negative-path coverage (rejection by validators, permission-denied) — currently sparse

### Phase 3 — Replace `.objects.create()` with factories
- Inventory missing factories (Site, SiteSignupPolicy, role-assignment models, StubModel)
- Add them
- Sweep ~16 call sites

### Phase 4 — Fix tautologies
- `test_course_progress_calculation` — replace formula-derived expected values with hard-coded oracles
- `test_delivery.test_later_retries_use_correct_base_delays` — split / hard-code

### Phase 5 — Parametrize copy-paste clusters
- Mechanical, low risk

### Phase 6 — Fill coverage gaps
- `app_authentication` tests
- `xapi_learning_record_store` tests

### Optional Phase 7 — E2E hardening
- Extract e2e helpers (localStorage reset fixture, etc.)
- Audit all e2e tests for semantic-locator usage

---

## Headline numbers

- ~17 high-severity issues
- ~40 medium-severity issues
- ~10 low-severity issues
- 2 high-value zero-test apps

Phase 1 alone removes the most brittle coupling for ~3 weeks of focused work; Phases 2–4 are where catch-real-bugs gains live.
