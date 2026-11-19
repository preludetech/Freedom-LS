# Research: codebase touch points

Question: what in the existing codebase does this work touch, reuse or conflict with?
All paths relative to the repo root. Line numbers are as of this worktree.

## 1. Key finding: one gate serves two audiences (the main conflict)

`open_to_organisation_expression(organisation)` (`freedom_ls/learner_management/queries.py:268`) is
`open_to_everyone_expression() | Q(organisation is an owner)`. `open_to_everyone_expression()` (:240)
is `~is_organisation_course_expression() | Q(audience=PUBLIC)`. A public course is therefore "open to
every organisation" today, and that single expression is used for BOTH:

- educator visibility (the thing this spec narrows): `courses_visible_to`, `registerable_courses`
- the write-path gate on registrations, which must NOT narrow, because learner self-join of public
  courses goes through it: `is_course_open_to_organisation` -> `require_course_open_to` /
  `validate_course_open_to`.

Learner self-join (`freedom_ls/learner_interface/views.py:1099-1113`, `self_register` in
`freedom_ls/learner_management/learner_actions.py:348`) picks `own_organisation_for_course(...)` or
falls back to the site's default Organisation (`get_default_organisation`), then asserts
`is_course_open_to_organisation(course, organisation)`, then `require_course_open_to` runs inside
`self_register`. For a public course of org A joined by a learner with no row in A, the organisation
is the default org, which is not an owner and (under the new rule) holds no grant. If the existing
expression is simply tightened, learner self-join of public courses breaks, and so do deactivated or
reactivated registrations, registration rules, and model `clean()`.

Implication for the spec: keep `open_to_organisation_expression`/`is_course_open_to_organisation`
(the "may this organisation hold a registration" rule) as is, and add a separate educator-facing
rule (e.g. "shared with / see-able by organisation") consumed only by the educator list, filters,
pickers and detail authorisation. The register picker needs a THIRD notion: owner OR `register`
grant (not merely `see`), and it must still pass the write gate (`require_course_open_to`), which a
non-public course shared by a `register` grant would FAIL today (see 3, "write-gate consequence").

## 2. queries.py symbols and every caller

`freedom_ls/learner_management/queries.py`:
- `is_organisation_course_expression()` :234: Exists on `Course.organisations.through` (auto through
  table, no extra columns). Used by `open_to_everyone_expression` only.
- `open_to_everyone_expression()` :240. Callers: `in_audience_expression`,
  `open_to_organisation_expression`, and `freedom_ls/learner_interface/templatetags/course_card_tags.py:41`
  (`get_course_by_path` embed card; its whole rule: not HIDDEN and open to everyone). The embed card
  is organisation-agnostic and must stay as is.
- `in_audience_expression(user, *, registered=None)` :247 and `is_in_audience(user, course)` :289.
  Callers: `freedom_ls/course_access/backends.py:539,544` (`VisibilityEnforcingBackend.filter_visible`),
  `backends.py:439` (`get_access`), `freedom_ls/course_access/visibility.py:28,39` (404 gate).
  This is the LEARNER's audience rule (own-org learner row, or registered). Do not change it.
- `open_to_organisation_expression(organisation)` :268. Callers: `courses_visible_to` (:541),
  `registerable_courses` (:554), `is_course_open_to_organisation` (:297), test
  `learner_management/tests/test_queries.py:2380`.
- `is_course_open_to_organisation` :295. Callers: `require_course_open_to` :306,
  `validate_course_open_to` :313, `freedom_ls/learner_interface/views.py:1111` (self-register view),
  `freedom_ls/registration_rules/evaluation.py:242` (`apply_rule_changes` skips closed courses).
- `require_course_open_to` raises `CourseNotOpenError(ValueError)` (:300). Callers:
  `learner_management/utils.py:202` (`register_cohort_for_course`), `learner_actions.py:311`
  (`register_for_course`), `learner_actions.py:358` (`self_register`). Educator catches it only in
  `ReactivateRegistrationAction.handle_submit` (`educator_interface/actions.py:932`).
- `validate_course_open_to` (ValidationError on field `course`, message `COURSE_NOT_OPEN_MESSAGE`).
  Callers: `LearnerCourseRegistration.clean` (`learner_management/models.py:311-313`),
  `CohortCourseRegistration.clean` (:354-356), `registration_rules/models.py:76-78`
  (`RegistrationRule.clean`).
- `courses_visible_to(user, organisation)` :523. Callers: `educator_interface/filters.py:26,48`
  (`VisibleCourseFilter.get_queryset`), `educator_interface/views.py:1936`
  (`CourseDataTable.get_queryset`), `views.py:2453` (`CourseConfig.authorise_instance`).
  Structure: `held = pk in registrations of visible cohorts | visible learners` (both via
  `cohorts_visible_to` / `learners_visible_to`, which are organisation-scoped, so "registration
  belongs to this organisation" is already satisfied). Result: superuser gets `open_to | held`
  (ignoring visibility); others `(open_to & PUBLISHED) | held`. Subqueries not joins, because
  `CourseDataTable` annotates `Count()` over the same relations.
- `registerable_courses(organisation)` :550 (published + hidden, not COMING_SOON, by title). Callers:
  `registerable_courses_for(cohort)` :560, `registerable_courses_for_learner(learner)` :569
  (these feed `educator_interface/forms.py:102,116` `CohortCourseRegistrationForm` /
  `LearnerCourseRegistrationForm`) and `educator_interface/actions.py:3082,3096`
  (`CoursePickerMixin`: bulk register learners / cohorts; `get_form` and `resolve_target` both use it,
  so a tampered POST target also 404s via `get_object_or_404`).
- `_resolved_or_none(user, everything)` :417: `.none()` for inactive/anonymous, `everything` for
  superuser, `None` otherwise. Used by `organisations_accessible_to`, `cohorts_visible_to`,
  `all_cohorts_visible_to`, `courses_visible_to`, `learners_visible_to`. Superusers are NOT exempt
  from the course rule today (test `test_a_superuser_does_not_see_another_organisations_course`,
  `learner_management/tests/test_queries.py:2402`). Keep that: pass the narrowed queryset as
  `everything`. Note: there is no staff-flag handling, only `is_superuser`.
- Not touched but sibling "course reach" helpers that read registrations only:
  `peers_through`/`peers_of`, `registered_course_pairs`, `courses_losing_access` etc. They are
  organisation-scoped already and unaffected.

## 3. Educator interface (`freedom_ls/educator_interface/`)

- Route: `OrganisationSectionConfig` registered as `CourseConfig` (`views.py:2440`), `url_name =
  "courses"`, `model = Course`, `list_view = CourseDataTable`, `instance_view = CourseInstanceView`.
  URLs are built by the panel framework (the educator `urls.py` has only a catch-all `re_path`, no
  per-course names; `app_name = "educator_interface"`). Paths: `/<org-slug>/courses`,
  `/<org-slug>/courses/<pk>`, panels `.../courses/<pk>/__panels/{details,content,cohorts,learners}`,
  actions `.../courses/<pk>/__panels/content/__actions/preview_content?item=<id>[&page=<id>]` and
  `.../__actions/preview_course_details` (see `tests/test_views.py:8172 _content_action_url`).
- `CourseDataTable` (`views.py:1918`): `get_queryset` -> `courses_visible_to` + annotate counts narrowed to
  visible cohorts/learners + prefetch. Row counts already show only this organisation's cohorts and
  learners (satisfies "own learners' progress"). `empty_message` text says "Courses open to this
  organisation will appear here." (reword if semantics change).
- Detail: `CourseInstanceView`/`CoursePanelStack` (`views.py:2427`): panels `CourseDetailsPanel`,
  `CourseContentPanel` (outline + `PreviewContentAction`, `PreviewCourseDetailsAction`),
  `CourseCohortRegistrationsPanel`, `CourseLearnerRegistrationsPanel`.
- 404 gate: `CourseConfig.authorise_instance` (:2450) -> `courses_visible_to(...).filter(pk=...)`,
  raising `OrganisationScopeDenied`. It runs for the instance and (per the framework) its panels and
  actions. Invariant test `educator_interface/tests/invariants/test_config_authorisation.py` requires
  every config to override `authorise_instance` or declare an exemption.
- Preview split is the new bit. The preview actions have `capability = None` (`views.py:2305,2342`) and
  authorise only through the instance gate, so today "can see" == "can preview". New rule "held
  registration => detail visible but no content preview" needs a preview-specific check in
  `PreviewContentAction.get_context_data` and `PreviewCourseDetailsAction.get_context_data` (404 /
  `Http404` when the organisation holds only `see` or only a registration), AND the `CourseContentPanel`
  (outline rows list titles of every item, which is arguably itself content; also `get_actions`
  currently always returns both preview actions) should be withheld or emptied for non-preview
  viewers. `CourseDetailsPanel` shows title/subtitle/learning outcomes/lesson count (metadata only).
  `outline_rows(course)` in `views.py:2209` builds the outline.
- Filters: `educator_interface/filters.py:42 VisibleCourseFilter(RelatedChoiceFilter)`:
  `get_queryset` = `courses_visible_to(...)` ; `apply` filters cohorts by active
  `CohortCourseRegistration`. `LearnerCourseFilter(VisibleCourseFilter)` :112 reuses `get_queryset`,
  applies `holds_registration_for_any_expression`. Used at `views.py:493` (cohort list) and `:661`
  (learner list). They inherit whatever `courses_visible_to` returns, so changing that one function
  fixes both pickers' filter choices. Tests: `educator_interface/tests/test_filters.py:68-143,291`.
- Register actions: `RegisterCohortForCourseAction` (`actions.py:582`, capability
  `freedom_ls_learner_management.add_cohortcourseregistration`, form `CohortCourseRegistrationForm`),
  `RegisterLearnerForCourseAction` (`actions.py:795`, `add_learnercourseregistration`, form
  `LearnerCourseRegistrationForm`). Their picker queryset comes from `registerable_courses_for` /
  `registerable_courses_for_learner` (forms) and then `register_cohort_for_course` /
  `register_for_course`. Bulk equivalents: `RegisterForCourseBulkAction` (:3125),
  `RegisterCohortForCourseBulkAction` (:3316), also via `CoursePickerMixin`. Deactivate bulk actions
  share the picker, so a course whose grant was later revoked would drop out of the deactivate picker
  too (same as today for closed courses; `courses_visible_to`'s `held` covers display only). Worth a
  decision.
- Educator interface never consults the course-access backend (no `get_access`/`can_self_register`
  in `educator_interface`; grep confirms). The educator register path already bypasses the
  price/application gate today: it only calls `require_course_open_to`. So "a `register` grant skips
  the price and application gate" is already true of the services; the decision is really about
  keeping non-owner/non-public (e.g. `organisation_learners` audience) courses registerable via the
  grant.
- Write-gate consequence: for a course with owners and a grant to org B, both
  `require_course_open_to` (services) and `validate_course_open_to` (model `clean()`, run by admin and
  `RegistrationRule.clean`) use `open_to_organisation_expression`. A `register` grant on an
  `organisation_learners` course is rejected today. The write gate must learn "registered via
  register grant" too, or the `register` flag is useless for non-public courses. Public courses pass
  regardless.
- Dashboard/reporting: `educator_interface/tests/test_dashboard.py`, `test_reporting.py` use course
  querysets; main code reads registrations (`views.py:619, 811, 1962, 2405`) not the open-to
  expression, so no change needed. `learner_management/utils.py:45` (direct registrations) likewise.

## 4. Course model, Organisation model, admin

- `Course` (`freedom_ls/content_engine/models/courses.py:156`): `organisations =
  ManyToManyField("freedom_ls_organisations.Organisation", blank=True, related_name="courses")` :175
  (auto through, no extra columns, migration `0009_course_audience_course_organisations.py`);
  `audience = CharField(choices=CourseAudience)` :178, `CourseAudience.{ORGANISATION_LEARNERS,PUBLIC}`
  :150. Comment: empty `organisations` => not an organisation course and `audience` has no effect.
  `Course.single_organisation` (~:406) reads prefetched organisations for the byline (used by
  `content_engine/course_details.py course_details_context`).
- Per-organisation flags need a new table (an explicit model such as a course-to-organisation grant
  row with three booleans and `unique(course, organisation)`), because the M2M through is implicit.
  Do not reuse the existing M2M through for grants: `is_organisation_course_expression` and
  `own_organisation_for_course` (`Learner.organisation__courses`), `in_audience_expression`,
  `Course.organisations` admin filter, `course_applications/queries.py:53` and
  `course_applications/tests/test_backends.py:962` all treat `organisations` as ownership.
- `Organisation` (`freedom_ls/organisations/models.py:63`): `SiteAwareModel`, `slug =
  SlugField(max_length=150, allow_unicode=True)`, unique `(site, slug)` constraint
  `unique_organisation_slug_per_site`, unique `(site, name)`; one default per site.
  Organisations are single-site, so a grant can only name an organisation on the same site.
- Admin: `content_engine/admin.py:178 CourseAdmin` (`list_filter` includes `organisations`;
  `organisations` and `audience` are read-only, shown via `organisation_names`; `get_queryset`
  prefetches `organisations`). Test `content_engine/tests/test_admin.py:333,355`. A new read-only
  grants display belongs here for consistency (file is the source of truth).

## 5. Content loader and schema (where `organisations:`/`audience:` are parsed)

- Pydantic: `freedom_ls/content_engine/schema.py:369 class Course(BaseContentModel...)`,
  `model_config = ConfigDict(extra="forbid", ...)` so a new front-matter key (e.g. `shared_with:`)
  must be added to the schema or the load fails. Existing fields: `organisations: list[str]` :395,
  `audience: CourseAudience` :399. Tests: `content_engine/tests/test_schema.py:646-662`.
- Standalone validator mirror: `claude_plugins/fls-content/validate/schema.py:709-715` (a copy of
  the same two fields). Docs for authors: `claude_plugins/fls-content/skills/content-types/resources/course-files.md:21-22`.
  Both must be updated alongside (generic-plugin rule does not apply: fls-content is FLS-specific).
- Saver: `freedom_ls/content_engine/management/commands/content_save.py:598-621` `save_course`:
  `organisations = _resolve_course_organisations(item, site)`; `save_with_uuid(Course, item, ...,
  exclude_fields={"children","categories","dashboard_category","price","time_limit_days","organisations"})`
  (a new key must be added to `exclude_fields`); then `course.organisations.set(organisations)` (replace
  semantics: absent key clears). `_resolve_course_organisations` :624: queries
  `Organisation._base_manager.filter(site=site, slug__in=...)`, and an unknown slug raises
  `ValueError("Unknown organisations [...] in <path> on site '<name>'. Valid organisation slugs: [...]")`
  (fails the whole load; no warning mode). Grants should reuse this resolver and keep the
  "replace on every load" semantics. Open points for the spec: grant to an org that is also an owner;
  duplicate slugs; grant on a course with no `organisations`; `register`/`preview` implying `see`
  normalised at load or at read.
- Tests: `content_engine/tests/management/commands/test_content_save.py:3117-3200`
  (`_write_organisation_course` helper at :3117; unknown-slug test ~:3155; clear-on-removal ~:3167).
- Demo content: `demo_content/functionality_demo_organisation_course_northwind/course.md`
  (`audience: public`, `organisations: [northwind-logistics]`, "visible to everyone" description) and
  `demo_content/functionality_demo_organisation_course_harbour/course.md`
  (`audience: organisation_learners`, org harbour). Load test:
  `content_engine/tests/demo_content/test_organisation_courses.py`. Add a grant to one of them (or a
  new demo course) so the feature has demo coverage; the Northwind description states it is public.
  Other course.md files carry no `organisations:`.

## 6. Course-access backend interface (`COURSE_ACCESS_BACKEND`, `config/settings_base.py:632`)

`freedom_ls/course_access/backends.py`: `CourseAccessBackend` (:120) with `get_access`,
`get_access_for_request`, `get_access_many`, `is_accessible_for_free`, `get_access_badge`,
`get_access_type`, `filter_visible`, `validate_course_config`, dashboard contributions; wrappers
`VisibilityEnforcingBackend` (:414, applies the audience rule via `in_audience_expression`) and
`DeadlineEnforcingBackend` (:611); default `FreeOnlyCourseAccessBackend` (:297); the shipped
application backend is `freedom_ls/course_applications/backends.py` (`ApplicationCourseAccessBackend`).
`Course.access_config` is backend-private (comment `courses.py:183`): the educator side must not read it,
which is consistent with "register grant bypasses the backend" being implemented by simply not calling
it. Learner-side registration through a grant: a learner registered by an educator gets access via
registration (backend already treats registered users as having access; check `get_access` for the
application backend before assuming, as `test_course_access.py` / `course_applications/tests` cover it).
No change needed to the backend interface.

## 7. "Open to organisation" semantics elsewhere that must not break

- Learner browse/dashboard/course detail: `VisibilityEnforcingBackend.filter_visible/get_access`,
  `course_access/visibility.py` 404 gate (`in_audience_expression`). Learner can see their own org's
  courses, public ones, and ones they are registered for. Unchanged by an educator grant. A learner
  of B who is registered via A's `register` grant keeps access through the "registered" clause.
- Learner self-register view (`learner_interface/views.py:1099`): see section 1.
- Embed card: `course_card_tags.get_course_by_path` uses `open_to_everyone_expression` (unchanged).
- Registration rules: `registration_rules/evaluation.py:242` (silently skips if closed) and
  `registration_rules/models.py:76` (clean). Rules register learners of an org for a course; they
  go through `is_course_open_to_organisation`, so an org with a `register` grant on a non-public
  course would be rejected unless the write gate learns the grant (section 3).
- Model `clean()` on both registration models (`learner_management/models.py:311,354`) and the
  admin.
- `course_applications/queries.py:53` prefetches `course__organisations` (ownership; byline).
- Isolation invariant tests: `educator_interface/tests/invariants/test_organisation_isolation.py:521`
  (organisation B course for `ORGANISATION_LEARNERS`); `test_config_authorisation.py`.

## 8. Existing tests to extend

- `freedom_ls/learner_management/tests/test_queries.py`: `TestOpenToOrganisation` :2332,
  `TestCoursesVisibleToOrganisationCourses` :2386, `TestRegisterableCoursesOpenToOrganisation` :2446,
  helper `_course_open_to` :2326; `registerable_courses_for*` :1580-1629; imports at :63-87. NOTE
  `test_a_public_course_of_another_organisation_is_open` asserts today's public-is-open behaviour for
  `is_course_open_to_organisation` (stays true if the write gate is kept); no existing test asserts a
  public other-org course appears in `courses_visible_to`, so the changed behaviour has no test to
  invert, but check `educator_interface/tests/test_views.py` (course list/detail, many hits),
  `test_course_visibility_and_interest.py`, `test_filters.py:68`, `test_forms.py:33`,
  `test_actions.py:2675,3051-3063,7596,8076` (picker/COURSE_NOT_OPEN_MESSAGE), `test_views.py:8172-8750`
  (preview URLs, org arrangements at 8403/8668/8853 add an unrelated org).
- Preview tests: `tests/test_views.py:8189-8750`; Playwright `tests/playwright/test_course_preview_flow.py`.
- Loader/schema/admin: see sections 4 and 5. Registration `clean()`: `learner_management/tests/test_models.py:467-543`,
  `registration_rules/tests/test_models.py:140-203`, services: `test_utils.py:588`, `test_learner_actions.py:538,1242`.
- Fixtures: `CourseFactory`, `OrganisationFactory`, `assign_object_role`, `mock_site_context`;
  scenario helpers `learner_management/tests/scenario_world.py` and `helpers.py`, and
  `qa_helpers/management/commands/qa_create_*_scenario.py` use `organisations`.

## 9. Docs and glossary

- Product docs: `docs/product/content-editing-workflow.md:96-101` (documents `organisations:` and
  `audience:`; says audience has no effect with no organisations; links to multi-tenancy doc) and
  `docs/product/multi-tenancy-and-isolation.md` `## Organisations` section (line ~43-64; one long line
  at :55 describes who sees an organisation course, to be updated). Possibly
  `docs/product/security-and-data-handling.md`. Author docs: `course-files.md` above.
- Glossary: `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`. Relevant entries:
  `Organisation` ("a client inside a site, a grouping, not an isolation boundary"), `Learner`,
  `LearnerCourseRegistration`/`CohortCourseRegistration`, "registration" = the word for course access.
  NAME CLASH: the glossary's "avoid" table says **grant** is a role/object permission
  (`assign_object_role`, `_granted_cohorts`, `_granted_organisations`, `_site_grants`) and for course
  access the term is **registration**; "Registration" is explicitly "not grant, not enrolment,
  not entitlement". Event-verb table forbids `granted`/`registered` for non-registration things.
  The decided feature's "grant" therefore collides with the permission "grant" vocabulary
  (`capabilities.py` `_granted_*`, `role_based_permissions`) and with `register` (a flag named
  `register` also overlaps "registration"). Suggest the spec pick a distinct noun (e.g. "course
  sharing" / "shared with", flags `see`/`register`/`preview`) and add glossary entries; avoid
  `audience` for it (taken by `Course.audience`, `in_audience_expression`, "audience gate").
  "Owner" is not yet a glossary term for `organisations:` ("belongs to"; code says "organisation
  course", "its organisations"); introduce deliberately.

## 10. Summary of the touch list

Change: `courses_visible_to`, `registerable_courses` (+ `_for`, `_for_learner`), a new educator-visibility
expression and preview/register predicates in `queries.py`; `CourseConfig.authorise_instance` and the
two preview actions + `CourseContentPanel` in `educator_interface/views.py`; `CourseDataTable.empty_message`;
`Course` schema + `content_save.save_course`; a new grants model + migration; `CourseAdmin` display;
fls-content validator/docs; demo content; product docs; glossary.
Keep as is: `open_to_everyone_expression` (embed card), `in_audience_expression`/`is_in_audience`
(learner audience), `is_course_open_to_organisation` for learner self-join (extend, do not narrow),
`VisibleCourseFilter`/`LearnerCourseFilter` (inherit the change), course-access backends.

status: ok
