# Foundational apps swap borrowed downstream models for stub models in tests

Spec 5 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring `site_aware_models`, `role_based_permissions`, `organisations` and `base`'s tests to both
rules from `ds:testing`: file-hierarchy mirroring and same-or-lower cross-app imports. Also bring
them to the conftest/fixture layering rules. All four sit at or near the bottom of the runtime
dependency graph. `base` depends on nothing, `site_aware_models` depends on `base`, `organisations`
depends on `base` and `site_aware_models`, and `role_based_permissions` depends on `accounts`,
`base` and `site_aware_models`. So their own tests must not reach for a concrete downstream model
just because one happens to be handy. A test may need "some object": a site-aware row, a
role-assignable target, or an object with a unique-per-site constraint. For that, it defines a
small local stub, following `freedom_ls/panel_framework/tests/conftest.py`
(`StubModel`/`StubChild`/`StubProtectedChild` registered via `schema_editor()`).

Verified cross-app imports to remove, grouped by file (all re-checked against the current tree):

- `site_aware_models/tests/test_manager.py`: `accounts.factories.SiteSignupPolicyFactory`,
  `UserFactory`; `accounts.models.SiteSignupPolicy`, `User`. Exercises `SiteAwareManager`'s
  per-site filtering, which needs any concrete `SiteAwareModel` subclass, not specifically `User`.
- `site_aware_models/tests/test_admin.py`: `accounts.factories.UserFactory`;
  `learner_management.models.Cohort`. Exercises `GuardedSiteAwareModelAdmin` against a model whose
  FK points at another registered `ModelAdmin`, and asserts a URL name that names `Cohort` literally.
- `site_aware_models/tests/test_factories.py`: `accounts.models.User`, to prove `SiteAwareFactory`
  auto-fills `site` from the thread-local context for any subclass.
- `site_aware_models/tests/test_admin_filters.py`: `learner_progress.factories.TopicProgressFactory`,
  to exercise `CompletionListFilter` (shared by every progress admin) through a real changelist.
- `site_aware_models/tests/test_forms.py`: `learner_management.models.Cohort`;
  `organisations.factories.OrganisationFactory`, to exercise `ConstraintValidationFormMixin` against
  a model with a `UniqueConstraint` that excludes `site`.
- `site_aware_models/tests/test_slugs.py`: `content_engine.factories.TopicFactory`,
  `content_engine.models.Topic`, to exercise `get_unique_slug` against a real slugged, site-aware
  model.
- `role_based_permissions/tests/test_management_commands.py`,
  `test_utils.py`, `test_models.py`: `learner_management.factories.CohortFactory` (and, inline,
  `learner_management.models.Cohort` in `test_utils.py`), used throughout as "any object with an
  assignable role." One case in `test_utils.py` also asserts against the concrete guardian
  permission codename `freedom_ls_learner_management.view_cohort`.
- `organisations/tests/test_admin.py`: `accounts.factories.UserFactory`, to log in as staff against
  the admin change view.
- `organisations/tests/test_models.py`: `accounts.factories.UserFactory`;
  `role_based_permissions.utils.assign_object_role`, used against an `Organisation` as the role
  target.
- `base/tests/test_header_bar_user_menu.py`: `accounts.factories.UserFactory`, `accounts.models.User`;
  `learner_management.factories.CohortFactory`; `organisations.factories.OrganisationFactory`;
  `role_based_permissions.utils.assign_object_role`, all to compute a real
  `can_access_educator_interface` value before rendering the header partial.
- `base/tests/test_error_pages.py`: `accounts.factories.UserFactory`, to drive the CSRF-failure page
  through a logged-in client.

Two imports the audit flagged for these apps resolve without any change here, because `SiteFactory`
moves to `site_aware_models` in spec 4. These are `site_aware_models/tests/test_slugs.py`'s and
`test_get_cached_site.py`'s `from freedom_ls.accounts.factories import SiteFactory` (in
`test_get_cached_site.py`, the only cross-app import in the file), and the `SiteFactory` half of
`organisations/tests/test_signals.py` and `test_models.py`'s imports. All of them become imports of
`site_aware_models`'s own factory once spec 4 lands, which is not a cross-app edge for any of these
four apps.

Once each app's tests are clean, this spec deletes that app's lines from spec 3's rule-2 and rule-1
baselines. Spec 3 owns the baseline files themselves.

## Why

These four apps are the group the rest of the effort's cleanups point back to.
`research_test_layout_audit.md` picked them out specifically. Their tests borrow concrete
downstream models (`Cohort`, `Topic`, `TopicProgress`) to stand in for "any object," which is
exactly backwards for apps this low in the dependency graph. `panel_framework` already shows the
fix works. Landing the stub-model technique here, on the smallest and most generic apps, gives
every later cleanup spec a working reference instead of a description.

## What is settled

- Runtime dependencies: `base` depends on nothing; `site_aware_models` depends on `base`;
  `organisations` depends on `base` and `site_aware_models`; `role_based_permissions` depends on
  `accounts`, `base` and `site_aware_models`.
- The stub-model technique is the prescribed fix, per spec 1's standard:
  `freedom_ls/panel_framework/tests/conftest.py`'s `StubModel`/`StubChild`/`StubProtectedChild`,
  registered via `schema_editor()`, is the reference pattern this spec follows for a stub
  `SiteAwareModel` subclass and a stub role-assignable object.
- `UserFactory` and `User` imports are allowed in any app's tests (spec 1 treats the user as
  framework-level). The `accounts` imports listed above that only build a user need no change; the
  other `accounts` imports (`SiteSignupPolicy` and the like) are still violations.
- `assign_object_role` calls follow spec 1's rule for granting a role in an app that does not depend
  on `role_based_permissions`.
- `SiteFactory` lives in `site_aware_models` after spec 4. The `SiteFactory` imports named above as
  "resolve without change" need no work in this spec; do not re-list them as violations.
- Spec 3 owns the baseline files (`ignore_imports` for rule 2, the exemption list for rule 1); this
  spec's only edit to them is deleting its four apps' now-clean lines.

## Open until the spec

- Whether `base/tests/test_header_bar_user_menu.py` needs `learner_management`, `organisations` and
  `role_based_permissions` at all is open. `base`'s own code never imports any of the three, and
  `can_access_educator_interface` reaches the template only as a context-processor value contributed
  by `learner_management` (`config/settings_base.py`,
  `freedom_ls/learner_management/context_processors.py`). Whether the test can pass that value
  directly into the render context instead of computing it through real role assignments is a
  decision for the spec, not settled here.
- Whether `site_aware_models/tests/test_admin.py`'s second assertion (a URL name that names
  `freedom_ls_learner_management_cohort_permissions` literally) can move to a stub model with its own
  registered `ModelAdmin`, or whether that one assertion stays pinned to a concrete app as a
  documented exception.
- Whether `role_based_permissions/tests/test_utils.py`'s guardian-integration case (asserting against
  the concrete permission codename `freedom_ls_learner_management.view_cohort`) can run against a
  stub model's own permission, or needs to stay concrete because it is proving guardian wiring against
  a real app label.

## Out of scope

- Any other app's tests, including the ones that import from these four (every other app already
  depends on at least one of them at runtime, so those are not rule-2 violations).
- Moving `SiteFactory` itself (spec 4's job) or generating and regenerating the baseline files
  (spec 3's job). This spec only deletes its own now-clean lines from them.
- `educator_interface`'s `role_based_permissions` runtime-edge question (spec 15's job) and the
  `learner_management`/`learner_progress` circular edge (spec 8's job).

## Resources

- `research_test_layout_audit.md` (parent `spec_dd/1. next/test-organisation-and-hygene/`), §1 and
  the §5 table rows for `site_aware_models`, `role_based_permissions`, `organisations`, `base`: the
  per-app violation list and the stub-model recommendation this spec verified and carried forward.
- `freedom_ls/panel_framework/tests/conftest.py`: the stub-model + `schema_editor()` pattern to
  follow.
- `claude_plugins/django-stack/skills/testing/SKILL.md` (+ `resources/testing.md`, `factory_boy.md`)
  and `claude_plugins/fls-dev/skills/testing/SKILL.md`: spec 1's rules and stub-model technique.
