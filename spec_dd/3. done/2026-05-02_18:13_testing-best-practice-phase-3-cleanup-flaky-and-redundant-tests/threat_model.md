# Threat model — Phase 3: cleanup flaky and redundant tests

## TL;DR

This spec is **test-only**: deleting/rewriting brittle assertions and fixing flaky tests surfaced by `pytest-randomly`. Spec explicitly forbids production code changes (Success criterion #7) and limits doc edits to one rule in `resources/testing.md`. The threat surface is therefore **not the running application** — it is the **integrity of the test suite as a security control**. The risk is that test cleanup silently weakens our ability to detect regressions in security-relevant behaviour (auth, permissions, multi-tenancy, CSRF).

No new attack surface is introduced. No new gaps that the spec must close before implementation. Two **review-time disciplines** are recommended below to keep the cleanup honest.

---

## 1. Assets at risk

The spec does not touch production code, so the user-facing assets (credentials, sessions, PII, course content) are not directly at risk. The assets at risk **from a flawed implementation of this spec** are:

| Asset | Why it matters |
|---|---|
| **Regression-detection coverage** for permissions / role boundaries | Audit §6 explicitly cites `BASE_ROLES["site_admin"].permissions == 8`. If we delete instead of re-express, we lose detection of "someone accidentally widened site_admin's permission set". |
| **Regression-detection coverage** for multi-tenant isolation | Site-aware filtering (`site_aware_models`) is the project's primary tenant-isolation control. Any test deleted in this sweep that incidentally exercised cross-site filtering would silently weaken that control. |
| **Regression-detection coverage** for authentication flows | CSS-class deletions in views that *also* check redirect/login behaviour must preserve the redirect/login assertion. |
| **CI gate fidelity** | The Phase 2 baseline (random ordering, `pytest-socket`) is now load-bearing. A flaky test "fixed" by hiding the failure (e.g. `pytest.mark.skip` without a ticket, or a fixture that masks shared state instead of cleaning it) degrades the gate without anyone noticing. |
| **`resources/testing.md` doc** | One in-scope edit. If the `transaction=True` rule is misstated, future authors will inherit the mistake. Low blast radius but worth a careful read at PR review. |

## 2. Threat actors

Standard application threat actors (anonymous users, authenticated users, admins, external attackers) are **out of scope** — the spec produces no runtime change. Relevant actors for *this* threat model are:

- **Future contributor** (including future-self / Claude) writing or refactoring code that depends on a security-relevant invariant. They are protected by tests; this spec changes which tests exist.
- **Reviewer** of this PR. The spec's safety depends on the reviewer being able to tell, per deletion, whether a behavioural assertion went with the brittle one. The diff being reviewable is itself a security control.
- **Reviewer of the *next* PR** (the strict-sequential `phase-3-strengthen-view-assertions`). Their starting point is whatever this PR leaves behind.

## 3. Attack vectors — OWASP Top 10:2025 mapping

Most categories don't apply because there is no runtime change. The two that *do* apply are about coverage erosion, not exploit surface.

| OWASP 2025 | Applies? | Why / mitigation |
|---|---|---|
| A01 Broken Access Control | **Indirect.** Test-suite erosion can hide future access-control regressions. | See §1 above. Mitigated by review discipline (below). |
| A02 Cryptographic Failures | No. No crypto code touched. |
| A03 Injection | No. ORM-only convention unchanged. |
| A04 Insecure Design | **Indirect.** Deleting tests of role/permission *invariants* is an insecure-design choice. | Spec already addresses this in step 3 of "Delete" — "don't just delete; re-express as invariant". This *is* the mitigation; the threat is failing to follow it. |
| A05 Security Misconfiguration | No. |
| A06 Vulnerable & Outdated Components | No. No dependency changes. |
| A07 Identification & Authentication Failures | **Indirect**, same shape as A01. |
| A08 Software & Data Integrity Failures | **Indirect.** A flaky-test "fix" that silently masks a real production bug (spec scope already calls this out) would be exactly this category. | Mitigated by spec's explicit rule: file-and-skip with ticket, never silently mask. |
| A09 Security Logging & Monitoring Failures | No. |
| A10 Server-Side Request Forgery | No. |

The non-OWASP threats specific to this spec:

- **T1 — Behavioural-assertion collateral damage.** A test contains both a CSS assertion and an authorisation assertion; a careless implementer deletes the whole test. *Mitigation: spec step 2 already says "delete only the brittle assertion" when accompanied by a useful one. Reviewer must verify case-by-case.*
- **T2 — Invariant loss on hardcoded-config rewrites.** The "site_admin permissions == 8" → "site_admin > instructor" rewrite is correct only if the rewritten assertion would actually fail when the security-relevant property is broken. A weak rewrite (e.g. asserting only "site_admin permissions is an int") provides false comfort. *Mitigation: reviewer should mentally apply the rewritten assertion to the failure modes the original was guarding against.*
- **T3 — Flake "fix" that papers over a production bug.** Spec already forbids this; relies on implementer judgement.
- **T4 — Test-only diff drifts into production code.** Reviewer should verify no `freedom_ls/**/*.py` changes outside `tests/` directories. Easy mechanical check.
- **T5 — `transaction=True` strip removes a marker that was actually needed.** Stripping the marker from a test that genuinely depends on `on_commit` semantics will turn a passing test into a silently-passing-for-the-wrong-reason test (the `on_commit` callback never fires). *Mitigation: when in doubt, keep the marker and add the rationale comment; only strip when the test clearly does no `on_commit` / `select_for_update` / cross-connection work.*

## 4. Required security controls

| Control | Status |
|---|---|
| C1: Diff is test-only (no `freedom_ls/**` non-test changes; one allowed addition to `resources/testing.md`). | Reviewer verifies via `git diff --stat` filter. |
| C2: Each deleted test reviewed for behavioural assertions before deletion. | Spec step 1–2. Implementer responsibility. |
| C3: Hardcoded-config rewrites preserve the invariant the original was guarding (especially for permission/role tests). | Spec step 3. Reviewer responsibility. |
| C4: Flaky-test fixes address the actual shared state, not the symptom. No `@pytest.mark.order` markers added. No `pytest.mark.skip` without a tracking ticket. | Spec already states this. |
| C5: `transaction=True` markers stripped only where unneeded; kept-with-rationale-comment everywhere else. | Spec already states this. |
| C6: Net LoC negative (success criterion #4) — sanity-checks that this is genuinely a *cleanup* PR, not a rewrite. | Mechanical check. |
| C7: Random-order suite green at Phase 2 baseline. | Success criterion #5. CI-enforced. |

## 5. Existing controls implementing these

- C1, C6: enforced by reviewer reading the diff. No automation, but mechanical to check.
- C7: already enforced by Phase 2 CI configuration (`pytest-randomly` + `pytest-socket` in the gate).
- C2, C3, C4, C5: enforced by spec language and reviewer judgement. No automation possible — these are intent-level checks.

## 6. Gaps the spec needs to close

**None that block implementation.** The spec already handles the failure modes identified above:

- The "delete vs. rewrite" distinction is explicit (§Scope step 3).
- The "don't fix production code; file-and-skip" rule is explicit (§Decisions made bullet 3, §Out of scope final bullet).
- The `transaction=True` rule is explicit and includes a doc-update so future tests inherit the discipline.

## 7. Recommendations (review-time, not spec-changes)

These are checks for the **PR review**, not amendments to the spec. The spec is sound as-written.

1. **Mechanical: verify diff is test-only.** `git diff --name-only main... | grep -v -E '(test_|/tests/|conftest\.py$|resources/testing\.md$)'` should be empty.
2. **Per-deletion: scan for entangled assertions.** For each removed test/assertion, eyeball it for `assertRedirects`, `assertContains` of a logged-in-only string, `client.force_login`, permission-check-related lookups. If any are present and were the *only* such assertion in their file, surface that in the PR description.
3. **Per-rewrite (hardcoded-config sites): apply the failure-mode test.** "If someone widened site_admin's permissions, would the rewritten assertion still fail?" If no, the rewrite is too weak.
4. **Per-flake-fix: read the fix, not just the green CI.** A passing test after a fixture tweak isn't proof the underlying shared-state leak is gone — it could just be hidden until a future seed re-surfaces it.
5. **`transaction=True` audit: keep-by-default.** When unsure whether a test depends on `on_commit` / `select_for_update`, keep the marker and add the rationale-TBD comment rather than strip.

## 8. Conclusion

**No security gaps in the spec.** This is a correctness / coverage-integrity threat model rather than an exploit-surface one. The spec already encodes the right disciplines; the remaining risk is review-time diligence, captured in §7.
