# Small apps: closing the last rule-2 and layering gaps

Spec 6 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring `health`, `content_base`, `icons`, `qa_helpers`, `webhooks`, `mail`, `google_tag`, `dev_tools`,
`course_interest`, `course_recommendations`, `deployment`, `referral_tracking` and
`contrib/conformance` to both test rules (mirroring, cross-app import boundary) and the
conftest/fixture/factory layering rule, and delete these apps' lines from spec 3's baseline files.
Every app here has at most one distinct rule-2 violation, or none, and no app needs the stub-model
technique spec 5 is introducing.

## Why

Batching keeps the per-app overhead down: each app is tiny to small, and most fixes are a single
factory call moved to a local stub or a documented exception, not a rewrite. Doing them together
also gives spec 3's baseline a clean sweep across a third of the app count in one pass.

## What is settled

- **Clean, no change expected**: `health`, `icons`, `qa_helpers`, `referral_tracking`. Each has no
  test-only cross-app import beyond its own runtime dependencies, no conftest layering violation
  (`qa_helpers` has no `tests/conftest.py`; `referral_tracking`'s only carries a `_clear_cache`
  autouse fixture), and a test hierarchy that already mirrors its source. `panel_framework` is
  excluded from this spec even though it is equally clean: the educator interface rebuild is
  reworking it, so its tests are that effort's concern, not this one's.
- **`content_base`** has one rule-2 violation. `content_base/tests/test_admin_filters.py` imports
  `freedom_ls.content_engine.factories.TopicFactory` to exercise `ContentTagListFilter` through
  `content_engine`'s `Topic` admin changelist, because `content_base` itself has no concrete model to
  filter. `content_base`'s runtime deps are `markdown_rendering` and `site_aware_models` only;
  `content_engine` depends on `content_base`, not the other way round, so this is backwards. The
  audit's own per-app table mislabelled this app "Clean" while listing the same edge in its rule-2
  column. The edge is real, confirmed by reading the file.
- **`webhooks`** has nothing left after specs 1 and 4. Its only test-only dependency is `accounts`:
  `UserFactory` in `test_send_test_views.py` (allowed in any app's tests) and `SiteFactory` in
  `test_integration.py` and `test_events.py` (moved to `site_aware_models` by spec 4). Confirm and
  delete its baseline lines.
- **`mail`** has one rule-2 violation and one layering item already settled as an exception.
  `mail/tests/test_settings_defaults.py` imports `freedom_ls.deployment.config.config` to assert the
  mail timeout stays well inside the worker's task ceiling; `mail`'s only runtime dep is `base`. On
  layering, `mail/tests/conftest.py`'s public helpers (`make_message`, `body_parts`,
  `raw_attachment_part`) are the one instance in the repo of the standard's documented-exception
  route for a conftest helper meant for manual import. The module docstring already states the
  reason: serialisation, the worker send and the backend all assert against the same message shape.
  This matches the rule as written, so nothing changes here.
- **`google_tag`** has one rule-2 violation, concentrated in one file.
  `google_tag/tests/test_context_processors.py` imports `accounts.factories.UserFactory` and
  `accounts.models.User` (both allowed), and `content_engine.factories.{CourseFactory,TopicFactory}` and
  `learner_management.factories.LearnerCourseRegistrationFactory`. `google_tag`'s only runtime dep is
  `base`.
- **`dev_tools`** has one rule-2 violation.
  `dev_tools/tests/test_danger_commands_with_applications.py` imports
  `course_applications.factories.CourseApplicationFactory` and `course_applications.models.CourseApplication`.
  `dev_tools`' runtime deps (`accounts`, `base`, `content_engine`, `form_engine`,
  `learner_management`, `learner_progress`, `organisations`) do not include `course_applications`.
- **`course_interest`** has one rule-2 violation.
  `course_interest/tests/test_views.py` imports
  `learner_management.factories.LearnerCourseRegistrationFactory`; `course_interest`'s runtime deps
  (`accounts`, `content_engine`, `course_access`, `site_aware_models`) do not include
  `learner_management`. The missing `tests/conftest.py` collection guard for this app belongs to spec
  4, not this spec.
- **`course_recommendations`** has no violation once spec 3 lands.
  `course_recommendations/tests/{test_models,test_queries}.py` import `content_engine.factories.CourseFactory`,
  and `RecommendedCourse.course` is a `ForeignKey` to `"freedom_ls_content_engine.Course"`. Spec 1
  counts a string-label relation as a runtime dependency, and spec 3 teaches the graph to see it.
  Confirm `docs/app_structure.md` shows the edge, then delete the baseline lines. The missing
  `tests/conftest.py` collection guard belongs to spec 4.
- **`deployment`** has no rule-2 violation. Every cross-app import in its tests,
  `content_engine.factories.FileFactory`, `organisations.factories.OrganisationFactory`,
  `reports.factories.GeneratedReportFactory` and `reports.models.GeneratedReport`, lands inside its own
  runtime deps: `base`, `content_engine`, `organisations`, `reports`. One layering violation:
  `deployment/tests/conftest.py` defines a plain function, `set_env`, imported manually by
  `test_checks.py` and `test_storage.py`, instead of living in a sibling helpers module.
- **`contrib/conformance`** has two things, kept separate. Rule 2: `test_settings.py` imports
  `course_access.backends.CourseAccessBackend` and `course_access.loader.get_course_access_backend`;
  `tests/test_conformance_meta.py` also imports `course_access.loader.get_course_access_backend`;
  `tests/test_timestamped_models.py` imports `site_aware_models.models.TimestampedModel`.
  `contrib/conformance` has no runtime deps at all. Rule 1: `test_theme.py`, `test_migrations.py`,
  `test_settings.py`, `test_admin_site.py`, `test_urls.py` and `_registry.py` live at the
  `contrib/conformance` package root and are imported as probe modules by
  `tests/test_conformance_meta.py`, rather than living under `tests/`. This dual-use design is
  deliberate and gets a documenting note (a short module docstring or README explaining why half its
  `test_*.py` files aren't under `tests/`), not a reshuffle into the mirrored layout.
- This spec deletes its apps' lines from spec 3's rule-2 and rule-1 baseline files; it never
  regenerates them.

## Open until the spec

- Whether `mail`'s `deployment.config` import is fixed (a local constant, a stub) or documented as an
  accepted exception under spec 1's intrinsic-dependency test.
- The concrete fix for each single-violation app is a per-app judgement call for the spec, not
  prescribed here: a local stub, moving the factory call to a fixture the owning app already
  exposes, or a documented exception.

## Out of scope

- The `course_interest` and `course_recommendations` optional-app collection guards: spec 4 adds
  `collect_ignore_glob` there.
- `panel_framework`: clean, and owned by the educator interface rebuild, not this effort.

## Resources

- `research_test_layout_audit.md` (parent `spec_dd/1. next/test-organisation-and-hygene/`): §3
  (conftest/fixture hygiene), §5 (per-app summary table) and §7 (groups A, C, K) are this spec's
  source list, corrected here against the current code.
