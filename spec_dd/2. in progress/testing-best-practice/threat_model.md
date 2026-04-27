# Threat model — Testing best practice (Phase 1: skill / documentation updates)

## Scoping note

This spec is **documentation-only**. The diff is confined to four files inside the FLS Claude plugin:

- `fls-claude-plugin/skills/testing/SKILL.md`
- `fls-claude-plugin/skills/playwright-tests/SKILL.md`
- `fls-claude-plugin/resources/testing.md`
- `fls-claude-plugin/resources/playwright-testing.md`

Per the spec's own "Explicitly out of scope" and success criterion 7: no production code, no test code, no `pyproject.toml`, no CI, no package installs, no migrations, no templates, no views. Phase 1 ships words, not behaviour.

That means **the live FLS application's attack surface does not change as a result of this PR**. The OWASP Top 10:2025 categories that normally drive a feature threat model (broken access control, injection, SSRF, cryptographic failures, etc.) have no new exposure here because no runtime code path is added or modified.

The realistic threat model for this spec is therefore narrow and is about the *content of the guidance itself*: bad guidance shipped to developers / Claude agents can produce insecure tests later, and skill files are read by an AI agent that will act on them. Below is what is genuinely in scope, scoped honestly rather than padded with generic boilerplate.

---

## Assets

The assets at risk in this PR specifically are:

1. **The skill / resource documents themselves** — `fls:testing` and `fls:playwright-tests` plus their resource files. These are read by both human developers and Claude Code agents and treated as authoritative. Their integrity (no malicious or wrong instructions) and accuracy (no insecure-by-default examples) are the asset.
2. **Downstream test code written against this guidance** — every Phase 2/3/4 spec in this initiative will be measured against these skills. If the skills sanction an insecure pattern, that pattern will propagate into the test suite and from there influence how production code is reviewed.
3. **Developer / agent attention as a control** — if the skills tell readers a tool is "currently available" when it isn't (or vice versa), readers will either import a missing package or skip a real protection. The tagging convention is itself an asset.
4. **Indirect: secrets that show up in test fixtures / examples** — if a documented example pattern hard-codes credentials, tokens, or PII as illustrative data, that pattern will be copy-pasted into real tests and potentially into git history.

Not assets in this PR (because nothing changes for them): user data, sessions, stored credentials, the database, the running web app, the multi-tenant Site isolation boundary.

---

## Threat actors

Realistic actors for a documentation-only change:

- **A future contributor (human)** reading the skill in good faith, who copy-pastes an example into a real test file. Most likely "actor"; they are not adversarial but they will faithfully reproduce whatever the skill shows.
- **A Claude Code agent** invoked with `fls:testing` or `fls:playwright-tests` loaded. Same shape as above but with less judgement about whether an example is illustrative vs. prescriptive — the agent will tend to take the skill literally.
- **A reviewer of a future PR** who uses the skill as the bar. If the skill is wrong, the bar is wrong, and review will not catch the issue.
- **A malicious contributor with commit rights to the plugin repo** — could in principle slip an insecure-by-default snippet into the resources, knowing it will be copied widely. Low-likelihood in this codebase (small contributor pool, mandatory review) but worth naming.
- **Out of scope:** unauthenticated web users, authenticated end-users (students, educators), external network attackers — none of them touch this PR's surface.

---

## Attack vectors mapped to OWASP Top 10:2025

Most categories do not apply because there is no runtime change. The ones that have a realistic, non-padded mapping are below; categories with no realistic mapping are listed at the end and explicitly marked N/A so the omission is auditable.

### A04:2025 — Insecure Design (applies, indirectly)

The skills are *design guidance* for the test suite. Insecure-by-default examples (e.g. a sample test that disables CSRF middleware globally, or a Playwright login fixture that hard-codes a real-looking admin password) are an insecure-design vector — not against the running app today, but against everything written against the guidance going forward.

Specific risks:

- An HTMX test example that shows mocking auth by patching `request.user` directly, encouraging future tests to bypass the real permission decorators rather than exercising them.
- A login-fixture example that stores `storage_state` containing real-looking credentials in the repo.
- A `time-machine` example that demonstrates freezing time around an auth-token-expiry check in a way that hides the underlying expiry logic, leading to tests that pass while the production check is broken.
- The "tautology" guidance, if poorly written, could be misread to mean "don't test derivations at all" — weakening rather than strengthening oracles.

### A05:2025 — Security Misconfiguration (applies, indirectly)

Tagging discipline is the relevant control here. If a tool tagged "currently available" is not actually installed, a developer following the skill will write tests that fail to run (DoS-on-self via test breakage). If a tool tagged "planned for upcoming phase" is actually already installed, the skill under-uses an existing protection. Both are misconfiguration of the documentation against the codebase.

The Playwright trace-on-failure config snippet is the most concrete instance: traces can contain screenshots / DOM dumps that capture auth tokens or PII from seeded fixtures. If the snippet is shipped without a "scrub before sharing" caveat, traces could be attached to bug reports / shared with third parties and leak fixture data that shadows real PII.

### A08:2025 — Software and Data Integrity Failures (applies, weakly)

The skills will recommend several pip packages (`pytest-randomly`, `pytest-socket`, `time-machine`, `pytest-xdist`, `django-htmx` if not present, plus the `mutmut` mention). Phase 2 actually installs them; Phase 1 only names them. The integrity concern is naming: if the skill names a package without pinning naming conventions (e.g. typo-squat names like `pytest-random` vs `pytest-randomly`, `time_machine` vs `time-machine`) a future installer could grab the wrong package. Low likelihood given pre-commit + review, but the mitigation is cheap.

### A09:2025 — Security Logging and Monitoring Failures (applies, very weakly)

Not in this PR. Mentioned for completeness because Playwright trace-on-failure is *adjacent* to logging — but Phase 1 only documents the config; Phase 2 actually turns it on. Real risk lives in Phase 2.

### Categories explicitly N/A for this PR

- **A01:2025 Broken Access Control** — no view/permission code changes.
- **A02:2025 Cryptographic Failures** — no crypto, key handling, or transport changes.
- **A03:2025 Injection** — no query, template, shell, or command construction added.
- **A06:2025 Vulnerable & Outdated Components** — no dependency changes in Phase 1.
- **A07:2025 Identification & Authentication Failures** — no auth code touched.
- **A10:2025 SSRF** — no outbound request paths added.

These are listed and dismissed deliberately so the next reviewer can see they were considered, not skipped.

---

## Required controls

Given the scope above, the controls that matter for *this* PR are:

1. **Tag every newly-documented tool / pattern as either "currently available" or "planned for upcoming phase X".** This is already a success criterion in the spec (criterion 3) and is the primary mitigation against the misconfiguration vector.
2. **Examples in the skills must not contain plausible secrets.** Use obvious placeholders (`"test-password-not-real"`, `"<fixture-token>"`) rather than realistic-looking strings. PII in examples must be obviously fake (e.g. `student@example.test`, never a real-looking email).
3. **Auth-related test examples (HTMX, login fixtures) must demonstrate exercising the real permission code, not bypassing it.** Patching `request.user` directly should be shown as an anti-pattern, not the recommended path. The recommended pattern is `client.force_login(user)` or a Playwright `storage_state` fixture produced by a real login flow.
4. **Playwright trace-on-failure documentation must include a caveat that traces capture DOM and may contain fixture PII / tokens; traces should not be attached to public issue reports without review.**
5. **Package names cited in the skills must be exact and correct.** Reviewer should sanity-check each name against PyPI to avoid documenting a typo-squat. Specifically: `pytest-randomly`, `pytest-socket`, `pytest-xdist`, `time-machine` (hyphenated), `django-htmx`, `django-perf-rec`, `mutmut`, `factory-boy` / `factory_boy` import name.
6. **Tautology guidance must be worded so the rule is "expected values are hard-coded oracles" — not "don't test derivations".** Wording matters; misreading produces weaker tests, not stronger ones.
7. **Cross-link discipline.** Both skills must point at each other for HTMX guidance (success criterion 4) so a reader entering from either side reaches the same canonical patterns.
8. **Skip list rationale stays recoverable.** Already in the spec; required so future contributors don't re-add `freezegun` / `pytest-rerunfailures` etc. without re-litigating the decision.

No runtime controls are required because there is no runtime change.

---

## Existing controls / coverage

Controls already in place that this PR inherits without modification:

- **Pre-commit hooks** run on every commit (`uv run git commit ...`) — catches obvious issues like lint, formatting, and any configured secret scanning.
- **Mandatory PR review** for the plugin repo — provides human eyes on documentation changes, which is the main mitigation for the malicious-contributor vector.
- **Existing skill / resource separation pattern** — `SKILL.md` is index, `resources/*.md` is long-form. Already established; this PR follows it.
- **Existing tagging convention precedent** — other FLS skills already tag patterns by availability; the convention being formalised here is consistent with prior practice.
- **`uv run pytest` still passes** as success criterion 8 — sanity check that no test code accidentally got modified. Acts as a guardrail against scope creep.
- **The spec's own "Explicitly out of scope" section** — bounds the diff so a reviewer can immediately flag any non-doc file as out-of-scope.
- **Site-aware multi-tenancy, CSRF middleware, app_authentication boundaries** — all unchanged. No coverage delta.

---

## Gaps

Honestly assessed gaps for *this* PR:

1. **No automated check that documented packages exist on PyPI under the cited names.** The mitigation is "reviewer eyeballs the names", which is fine for one PR but doesn't scale. Not worth automating in Phase 1; flag it as a Phase-2 concern (Phase 2 actually installs the packages, so if a name is wrong, `uv add` will catch it then). **Decision: accept the gap, rely on Phase 2 install to catch typos.**
2. **No automated check that "currently available" tags match `pyproject.toml`.** Same shape as above. Manual review only. Phase 2 should add `factory_boy` / `playwright` presence checks if the tagging is going to stay accurate over time. **Flag as a Phase-2 concern, not a Phase-1 blocker.**
3. **Trace-on-failure PII caveat could be missed.** The spec calls out the config snippet but does not currently call out the caveat. **Recommendation: amend the spec (todo item "user: Update the spec to close any security gaps surfaced") to add an explicit success-criterion bullet that the trace-on-failure section must include a "traces may contain fixture data, do not share publicly without review" warning.**
4. **The spec's "tautology" guidance is described in plain English and could be miswritten as "don't derive expected values" rather than "expected values must be independent oracles".** **Recommendation: spec update to add a one-line worked example contrast (good vs. bad) so the skill author has a target.**
5. **Auth-bypass-in-tests anti-pattern is not explicitly listed in the spec.** The HTMX patterns section talks about request-header simulation but does not say "and here is the wrong way: patching `request.user`". **Recommendation: spec update to explicitly require the skill to call out at least one auth-bypass anti-pattern, so readers see the boundary.**
6. **No explicit instruction to use `*.example.test` / placeholder secrets in examples.** Low risk because the project's existing skills already do this, but worth codifying once. **Recommendation: spec update — add a one-line success criterion that example credentials / PII must be obviously synthetic.**

Gaps **not** flagged (deliberately, because they would be padding): generic OWASP boilerplate around auth, sessions, encryption, SSRF, etc. None of those are touched by this PR and inventing risks for them would dilute the real ones above.

### Headline recommendations to feed back into the spec

The four spec amendments worth raising under todo step 3.2 ("user: Update the spec to close any security gaps surfaced") are:

- Add a success criterion that example credentials / PII must use obviously-synthetic placeholders.
- Add a success criterion that the trace-on-failure section must warn that traces can contain fixture data.
- Add a success criterion that the skill must show at least one auth-bypass anti-pattern, not only correct patterns.
- Add a worked-example contrast (good oracle vs. bad oracle) requirement for the tautology guidance, so the wording cannot be misread as "don't test derivations".

These are all wording-level changes to the spec; none expand scope beyond Phase 1.
