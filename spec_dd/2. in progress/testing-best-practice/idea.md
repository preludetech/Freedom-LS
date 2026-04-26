# Testing best practice — incremental hardening

Increment our testing practices. Two threads of work, run in this order:

1. **Update the FLS plugin's testing skills** so future code follows the new bar from day one.
2. **Sweep the existing test suite** to align it with the updated skills, and fill priority gaps.

Each phase below is a candidate spec / PR. The user picks which phases to do **now**, **later**, or **never** — see the *Decisions needed* section.

Research that informs this idea:
- `research_audit.md` — concrete anti-patterns and gaps in the current suite.
- `research_tooling.md` — prioritized tooling and practice additions for 2026.

---

## Skill updates (always first; foundation for everything else)

These changes make the skills the single source of truth before we sweep code.

- **`fls:testing` skill** — already strong. Add: HTMX test patterns (header simulation, `HX-Trigger` assertions, 422 validation, OOB swaps); a section on `time-machine` for time-shaped code; a short factory_boy patterns matrix (`SubFactory` / `RelatedFactory` / `Trait` / `post_generation`); a note on `pytest-randomly` order-independence rule.
- **`fls:playwright-tests` skill** — needs more work. Switch from `wait_for_selector` / `is_visible` to the `expect()` API; update locator priority to `get_by_role` / `get_by_label` / `get_by_text`; add trace-on-failure config; add a session-scoped login pattern (storage_state or programmatic).
- Cross-link the two skills so HTMX guidance is reachable from both.

---

## Suite sweep — phased

Themes from the audit, ordered by safety + value. Each is roughly one PR.

### Phase 1 — Drop brittle / low-value tests
- Delete CSS-class assertions (~12 sites).
- Delete hardcoded config-value assertions (~2 sites).
- Delete trivial model-default tests (~6 sites).
- Net code goes down; no risk.

### Phase 2 — Strengthen weak view assertions
- Sweep view tests that stop at `status_code == 200`; assert on `response.context` or rendered content.
- Add negative-path coverage for validators / permission checks (currently sparse).

### Phase 3 — Replace `.objects.create()` with factories
- Inventory missing factories (Site, SiteSignupPolicy, role-assignment models, framework `StubModel`, …).
- Add the factories.
- Sweep ~16 call sites.

### Phase 4 — Fix tautologies
- `test_course_progress_calculation` — replace formula-derived expected values with hard-coded oracles.
- `test_delivery.test_later_retries_use_correct_base_delays` — split / hard-code.

### Phase 5 — Parametrize copy-paste clusters
- `score_quiz` correct/incorrect tests, `get_text_color` tests, `partial_list_courses` variations.
- Mechanical, low risk.

### Phase 6 — Fill coverage gaps
- `app_authentication` and `xapi_learning_record_store` currently have **zero tests**. Both touch security/integration boundaries. Worth their own spec each (test design depends on what we want to lock in).

### Phase 7 (optional) — E2E hardening
- Audit Playwright tests against the rewritten skill.
- Extract shared fixtures (localStorage reset, etc.).

---

## Tooling additions — pick & choose

From `research_tooling.md`. Each is independent and small (`uv add` + a few config lines), unless noted.

### Strong recommendation (high ROI, ~half-day total)
- `pytest-randomly` — catches order-dependence. Will surface a few latent bugs on first run.
- `pytest-socket` — enforces "mock at boundaries" by failing the build when a test opens an unexpected socket.
- `pytest-xdist` — 3–5× faster locally and in CI.
- `time-machine` — deterministic clock for deadline / window code.
- `django-htmx` (if not already in) — clean middleware for `request.htmx` and HX response helpers.
- Branch coverage + `--cov-fail-under` ratchet.

### Worth doing in a follow-up phase
- `hypothesis` — targeted at scoring strategies, deadline arithmetic, sanitisers (not blanket).
- `django-perf-rec` — lock in N+1 fixes on top 5 hot views.
- `pytest-split` — only once CI > ~5 minutes.
- `syrupy` — snapshot tests for rendered markdown / email HTML only.
- `mutmut` — quarterly, manual, on scoring + validators only. Not in CI.
- `axe-playwright-python` — accessibility on top Playwright tests.

### Explicitly skip
- `freezegun` (use `time-machine`), `assertpy`, `cosmic-ray`, `pytest-rerunfailures` (masks flakes), `pytest-django-queries` (use `django-perf-rec`), visual regression tools.

---

## Suggested split into specs

Rather than one mega-spec, split into separate `testing-best-practice-phase-N-*` specs so each lands as its own reviewable PR:

1. `testing-best-practice-phase-1-skills` — update `fls:testing` and `fls:playwright-tests` skills (foundation).
2. `testing-best-practice-phase-2-tooling-quick-wins` — add `pytest-randomly`, `pytest-socket`, `pytest-xdist`, `time-machine`, branch coverage gate, `django-htmx`. Sweep any tests that break under random ordering or socket blocking.
3. `testing-best-practice-phase-3-cleanup` — delete brittle tests (CSS, hardcoded config, trivial CRUD).
4. `testing-best-practice-phase-4-strengthen` — strengthen weak view assertions; add negative-path coverage.
5. `testing-best-practice-phase-5-factories` — replace `.objects.create()` sweep.
6. `testing-best-practice-phase-6-tautologies-and-parametrize` — fix tautologies, parametrize copy-paste.
7. `testing-best-practice-phase-7-coverage-gaps-app-authentication` — own spec.
8. `testing-best-practice-phase-7-coverage-gaps-xapi` — own spec.
9. (Optional later) hypothesis / perf-rec / e2e hardening as their own small specs.

---

## Decisions needed

1. **Split into multiple specs, or one spec with multiple PRs?** The plugin's SDD workflow is one spec → one PR; splitting fits that grain. Confirm.
2. **Which tooling to adopt now?** Default proposal is the "strong recommendation" block (6 items). Flag any to defer or skip.
3. **Coverage gap apps (`app_authentication`, `xapi_learning_record_store`)** — in scope for this work, or separate effort?
4. **Branch coverage threshold** — start at the current % as the floor, then ratchet? Or pick a target (e.g. 75 %) and write tests to hit it?
5. **Phase 2 (tooling quick wins) before or after Phase 3 (cleanup)?** Doing tooling first means the cleanup runs against `pytest-randomly` etc. and surfaces more bugs — but cleanup PR is bigger. Doing cleanup first keeps PRs small but loses some signal. Default proposal: tooling first.
6. **Anything in the "skip" list you actually want?**
