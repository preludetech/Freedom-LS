# Permission matrix testing: keeping the spec table and the behaviour in sync

Answers the "Tests" line in `idea.md`: "A matrix test that iterates roles and
capabilities against the table above, so the table in the spec and the
behaviour cannot drift apart." Grounded in the repo's own `fls-dev:testing`
and `ds:testing` conventions and the existing permission/authorisation tests
in `role_based_permissions/tests/`, `educator_interface/tests/` and
`panel_framework/tests/`.

## 1. Patterns for keeping a matrix and its behaviour in sync

**Declare the matrix once, as data, and drive both the test and (optionally)
the doc from it.** The recurring shape in the wild is: a single source —
usually a plain data structure, sometimes a fixture file — that enumerates
`(role, capability) -> outcome`, consumed by a test that parametrizes over it
and fails loudly when a row is missing or wrong.

- **GitLab's policy specs** (`spec/policies/*_policy_spec.rb`,
  `ee/spec/policies/remote_development/workspace_policy_spec.rb`) use a
  literal matrix table inside the spec file — one row per
  `(admin, admin_mode, licensed, owner, role_on_project, ..., allowed)`
  combination — iterated with RSpec's `where`/`with_them` matrix DSL. GitLab's
  own guidance (Authorization development guidelines,
  https://docs.gitlab.com/development/permissions/) is to test every policy
  against "all roles, admin/non-admin, licensed/unlicensed" combinations
  rather than hand-picking a few, precisely so a new role or a widened grant
  cannot silently change `allowed?` without a spec catching it. GitLab's own
  team has since been refactoring older ad hoc policy specs *into* this
  matrix shape as a deliberate migration
  (https://gitlab.com/gitlab-org/gitlab/-/issues/513159), which is evidence
  the pattern is considered the target state, not a curiosity.
- **Discourse's `guardian_spec.rb`** does the equivalent per trust level and
  per moderator/admin flag rather than via a literal table DSL, but the
  underlying discipline is the same: the trust-level permissions are also
  published as a human-readable reference table on Discourse Meta
  (https://meta.discourse.org/t/trust-level-permissions-reference/224824) that
  the specs are expected to track. Discourse does not generate the doc table
  from the specs (or vice versa) — the two are kept aligned by convention
  and review, which is the "checked by review, not by code" tradeoff
  discussed in §4.
- **Django/pytest ecosystem** favours parametrizing directly over role
  fixtures with an explicit `id=` per case (Adam Johnson's parametrized
  ModelAdmin tests, https://adamj.eu/tech/2023/03/17/django-parameterized-tests-model-admin-classes/,
  is the same technique applied to a different cross-product) and keeping
  "the permission map next to the permission code as a contract the tests
  enforce" — i.e. the matrix lives beside the capability function it
  describes, not only in the spec doc or only in the test file.

**The pattern that generalises across all of these:**

1. One data structure is the matrix — a `dict[tuple[role, capability], Outcome]`
   or a list of `(role, capability, scope_relation, expected)` tuples — living
   in the app's production code or in a test-only module that imports the
   production capability names, never copy-typed as string literals in two
   places.
2. A single parametrized test walks that structure and asserts the capability
   function's answer against it. `ids=` names each case `role/capability` (or
   `role/capability/scope`) so a failure names the exact cell, the same way a
   spreadsheet cell reference does.
3. **Completeness checks are separate assertions, not implied by the
   parametrize.** Two failure modes a matrix-shaped test does not catch on
   its own: a row silently missing from the matrix (parametrize just doesn't
   generate that case — no failure, no signal), and a capability or view that
   exists in code but was never added to the matrix at all. Both need an
   explicit test: "every `(role, capability)` pair the matrix names has an
   entry" and "every capability the interface actually checks appears in the
   matrix's capability set." `panel_framework`'s existing
   `test_config_authorisation.py::TestProductionConfigsDeclareAuthorisation`
   is exactly this second shape already, generalised to "every section" —
   the same discipline should extend to "every capability."
4. **Negative cases are first-class matrix rows, not an afterthought bolted
   onto the positive ones.** "instructor may act on their own assigned
   cohort" and "instructor may not act on another cohort in the same
   organisation" and "instructor may not act on a cohort in another
   organisation" are three different rows, not one row plus a vague note.
   FLS already treats this as load-bearing: `test_organisation_isolation.py`
   pairs every "B's thing is absent" assertion with "A's thing is present"
   specifically because "isolation" is unfalsifiable without the positive
   half (see its own docstring on `isolation` fixture: "an empty page cannot
   pass for isolation").

## 2. Two layers: the capability function vs. the HTTP endpoint

FLS already has both layers, for a narrower question than the full matrix:

- **Capability/mechanism layer** — `panel_framework/tests/test_check_access.py`
  calls `ScopedConfig.check_access(request, instance)` directly on a
  hand-built `RequestFactory` request, with no client, no URL resolution, no
  templates. This is fast, precise about *why* something is denied (missing
  scope attr vs. no user vs. `authorise_instance` itself), and it is where
  `role_based_permissions/tests/test_utils.py` already lives for the
  role→guardian-permission sync (`assign_object_role`, `get_object_roles`,
  `sync_user_object_permissions`).
- **HTTP endpoint layer** — `educator_interface/tests/test_config_authorisation.py`
  and `test_organisation_isolation.py` go through `logged_in_client` and
  `reverse()`, asserting the actual status code (404, 200) and, for list
  views, that a row is or isn't in the rendered content. This is the layer
  that catches wiring bugs the unit layer cannot: a URL that bypasses
  `check_access` entirely, a template that renders a control anyway, a
  queryset that isn't actually filtered despite the capability function
  saying it should be.

**Which rows need endpoint-level tests, and how to keep the count
manageable:** not every `(role, capability, scope-relation)` cell needs its
own HTTP round trip. The two layers answer different questions and the
matrix test should mostly live at the capability layer, with endpoint tests
reserved for:

- **One or two representative capabilities per distinct enforcement
  mechanism**, not every capability. The matrix has ~10 capabilities but
  they likely reduce to two or three underlying mechanisms (guardian object
  permission check via `check_access`/`authorise_instance`; a capability
  function that isn't expressible as a guardian permission string at all,
  per the roadmap's "content-type filter" problem; and list-queryset
  filtering via `cohorts_visible_to`/`learners_visible_to`). One endpoint
  test per mechanism proves the wiring; the rest of the matrix's breadth is
  the capability layer's job.
- **Every "hide, don't disable" claim**, because that is a template/rendering
  assertion the capability layer cannot make on its own — `assert content
  not in body` for a control, mirroring the existing
  `test_users_list_cohort_cell_never_names_a_cohort_from_organisation_b`
  shape.
- **The negative/isolation cases already required by the framework's own
  test** (`test_config_authorisation.py`'s 404-sweep) — that test is generic
  over *every* enumerated path already, so it does not grow linearly with
  the matrix; a new capability that hangs a new action or panel off an
  existing `SectionConfig` is covered automatically, and only a genuinely new
  `SectionConfig` needs a new entry in `_seed_instance`.
- **403-for-changed-role** (the "acted, then role changed" case in the idea)
  needs exactly one or two endpoint tests total (one for the htmx-fragment
  path, one for the full-page path), not one per capability — it is testing
  the *response shape* of a denial, not the matrix itself.

Concretely: the matrix test proves *what* is allowed; a small, fixed number
of endpoint tests prove the matrix's answer *actually reaches* the response
(status code, rendered controls, filtered querysets, 403 vs 404 semantics).

## 3. Test cost

A literal 10 capability × 4 role cross-product is 40 cells. Adding
scope-relation (own / other-cohort / other-organisation / other-site, per
the idea's "cross-organisation is never possible" and "other cohort" cases)
multiplies by up to 4, giving **up to 160 parametrized cases** in the
worst case — but most cells collapse:

- A capability that is `no` for a role regardless of scope (e.g. `ta` on
  "Grant organisation_staff or site_admin") needs exactly one case, not four
  — scope is irrelevant once the answer is a flat deny. Only rows where the
  matrix cell is scope-*sensitive* (`own organisation`, `assigned cohorts
  only`) need the full scope-relation fan-out.
- Realistically: of the 10 capabilities, `ta`'s column is entirely
  scope-insensitive-no or scope-insensitive-yes except "Generate and
  download reports" and "See the organisation dashboard"; `instructor`'s
  column is mostly single-scope ("within assigned cohorts"). A reasonable
  estimate is roughly **60-80 meaningful cases** once flat-deny/flat-allow
  cells are collapsed to one case each and only genuinely scope-sensitive
  cells fan out — not 160.
- **Fixture reuse:** build the scope objects (site, two organisations, two
  cohorts per organisation, one user per role) *once* per test class/module
  via a fixture, per the "fixture placement" and "thin-wrapper" rules in
  `ds:testing` — the objects are read-only relative to the matrix
  assertions, so a module-scoped or class-scoped fixture is defensible here
  (rare exception to "default function scope", justified by the cost of
  standing up ~9 role assignments repeatedly). Role assignment itself
  (`assign_object_role`/`assign_site_role`) is a DB write per user-role pair,
  done once, not once per parametrized case.
- **Speed:** at the capability layer (`check_access`/`authorise_instance`
  called directly, no client, no template rendering — the
  `test_check_access.py` shape), 60-80 cases against shared fixtures is
  well under a second of test time; this is the layer that should carry the
  matrix's bulk. Pushing the same 60-80 cases through `logged_in_client` and
  full view rendering would be materially slower and is exactly what §2
  argues against — the endpoint layer stays a small, fixed set regardless of
  how wide the matrix grows.

## 4. Should the spec's markdown table be generated from code, checked against code, or neither?

Three options, with tradeoffs:

- **Generate the table from code.** Strongest sync guarantee, but wrong tool
  here: the table in `idea.md`/the eventual spec is written for the product
  owner to confirm ("The spec confirms each row with the product owner and
  may narrow it") — it is a decision record, not a rendering of the
  permission data structure. Generating it would either force the matrix's
  in-code representation to carry prose-quality column headers and cell text
  ("assigned cohorts only") that have no reason to exist in code, or produce
  a generated table too mechanical to read as a decision record. Neither
  Discourse nor GitLab do this for their permission docs; the doc and the
  spec stay hand-written, checked by review.
- **Check the doc against code with a test.** Also unattractive for the same
  reason as generation, from the other direction: a test that parses spec
  markdown and diffs it against `BASE_ROLES` couples a test suite to a
  markdown file's prose formatting, which is exactly the "config value the
  test shouldn't assert" anti-pattern the `ds:testing` resource warns about
  (testing derived-from-live-config values) — except here the "config" is
  free-text prose, which is worse: any copy-edit to the table's wording
  breaks the test for no behavioural reason.
- **Neither — instead, encode the matrix as data in the *test* suite (not
  parsed from the spec doc), and let the spec's prose table and the test's
  data matrix be two independent expressions of the same decision, each
  reviewed by a human against the product-owner-confirmed rows.** This is
  what the idea.md text actually asks for ("iterates roles and capabilities
  against the table above" — a test written *from* the table, not a test
  that *reads* the table). The safety net against drift is not code-checking
  markdown; it's that changing a permission's behaviour without touching the
  matching parametrize case is a failing test, and changing the parametrize
  case without a matching spec-table update is a normal code-review
  question ("why did this change and where's the spec update"), same as any
  other behaviour change.

**Recommendation: neither generate nor mechanically check the doc — encode
the matrix as data in the test module, hand-transcribed once from the
confirmed spec table, and lean on parametrize IDs plus code review to keep
them aligned.** This matches how GitLab and Discourse actually operate this
pattern in production-scale codebases.

## Implications for FLS

Recommended test shape, file locations following the repo's mirroring and
dependency-direction rules (`ds:testing` — "an app's tests import only apps
the app depends on at runtime"; matrix logic that spans
`role_based_permissions`, `learner_management` and `organisations` belongs in
the lowest app that depends on all three, which is `educator_interface`):

- **`freedom_ls/educator_interface/tests/test_permission_matrix.py`** — new
  file, holding:
  - A module-level data structure transcribing the spec's confirmed table,
    e.g. `MATRIX: list[MatrixCase]` where `MatrixCase` names
    `role: str`, `capability: str`, `scope_relation: Literal["own", "other_cohort", "other_organisation", "other_site"]`,
    `expected: bool`. One row per confirmed cell, flat-deny/flat-allow rows
    collapsed to a single `scope_relation="any"` case per §3.
  - One `@pytest.mark.django_db` test,
    `test_capability_matches_the_confirmed_matrix`, parametrized over
    `MATRIX` with `ids=lambda c: f"{c.role}/{c.capability}/{c.scope_relation}"`,
    calling whatever capability entrypoint spec 5 lands on (a
    `has_capability(user, capability_name, scope_object)`-shaped function,
    per the idea's "small capability layer" option) against fixtures built
    once per module/class (site, two organisations, cohorts, one user per
    role, per §3).
  - A second test, `test_every_role_has_an_entry_for_every_capability`,
    asserting the matrix's `{(role, capability)}` pairs cover the full
    cross-product of `ROLES × CAPABILITIES` constants also defined in this
    file — the completeness check from §1, independent of the parametrize.
  - A third test, `test_every_capability_the_interface_checks_is_in_the_matrix`,
    walking the same `SECTIONS`/action enumeration
    `test_config_authorisation.py` already builds and asserting each
    resolved capability name appears in the matrix's capability set — so a
    new action wired to a new capability string that never made it into the
    matrix fails loudly, the same spirit as
    `TestProductionConfigsDeclareAuthorisation`.
- **Keep `test_config_authorisation.py`'s existing 404-sweep and
  authorisation-declaration tests as-is** — they already generalise over
  every `SectionConfig`/action/panel and stay the endpoint-layer proof that
  the mechanism (not the matrix's specific answers) is non-bypassable. Do
  not duplicate their sweep inside the new matrix file.
- **A small, fixed set of endpoint tests, not one per matrix cell**, added to
  `test_organisation_isolation.py` (extending its existing "B's thing is
  absent, A's thing is present" pairing to instructor/ta-scoped rows) and a
  new `test_denied_experience.py` in `educator_interface/tests/` for the
  403-fragment-on-role-change case and the hide-not-disable rendering
  assertions — per §2, roughly one test per distinct enforcement mechanism
  plus one per denial-shape (404 vs 403 vs hidden control), not 60-80 HTTP
  round trips.
- **Unit-level role→permission-sync tests stay in
  `role_based_permissions/tests/test_utils.py`**, following its existing
  pattern (`assign_object_role`, `get_object_roles`,
  `sync_user_object_permissions`) — the matrix test in
  `educator_interface` should call the capability layer, not re-test
  guardian sync itself; that boundary already exists and should not blur.
- **Do not generate or markdown-parse-check the spec's table** (§4) — the
  spec table and `MATRIX` in the new test file are two hand-maintained,
  independently reviewed expressions of the product-owner-confirmed
  decisions; a PR that changes one and not the other is caught by review,
  and a PR that changes behaviour without updating `MATRIX` is caught by
  the test failing.

Sources:
- [GitLab Authorization development guidelines](https://docs.gitlab.com/development/permissions/)
- [GitLab: Refactor remote_development policy specs in accordance with matrix pattern (issue)](https://gitlab.com/gitlab-org/gitlab/-/issues/513159)
- [GitLab: Refactor agent_config_policy specs (merge request)](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/179304)
- [GitLab Testing best practices](https://docs.gitlab.com/development/testing_guide/best_practices/)
- [Discourse Trust Level Permissions Reference](https://meta.discourse.org/t/trust-level-permissions-reference/224824)
- [Understanding Discourse Trust Levels](https://blog.discourse.org/2018/06/understanding-discourse-trust-levels/)
- [Adam Johnson — Django parameterized tests for all ModelAdmin classes](https://adamj.eu/tech/2023/03/17/django-parameterized-tests-model-admin-classes/)
- [pytest parameter matrices — FlowFX](https://flowfx.de/blog/pytest-parameter-matrices/)

status: ok
