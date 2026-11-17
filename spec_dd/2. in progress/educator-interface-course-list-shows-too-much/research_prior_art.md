# Research: prior art

Question: what has already been tried for this, here or elsewhere, and what happened?

## Here (earlier specs in `spec_dd/3. done/`)

Nothing in `1. next` or `0. maybe` was found by grep for these terms; all relevant history is in done specs.

1. **Educator-interface-6 cohort administration** (`2026-10-11_06:57_educator-interface-6-cohort-administration/1. spec.md` lines 124-136; plan lines 259-287).
   - Introduced `courses_visible_to(user, organisation)` in `learner_management/queries.py`: "every published course, plus any course registered to a cohort or learner the user can see in this organisation, active registration or not". Hidden and coming-soon courses appear only through such a registration.
   - `registerable_courses_for(cohort)` lists published and hidden courses, never coming-soon ones.
   - The premise was explicit: courses are shared across the site ("course is visible in every organisation, so it needs no organisation of its own"; comment "Courses are shared across the site"). So **showing other organisations' public courses was intentional**, a consequence of "a Course has no organisation". No spec weighed paid or application-gated courses against it. The only gating considered was visibility (published, hidden, coming_soon), not audience or access config.
   - Upgrade notes (line 67) and QA (`qa_report.md` line 197) record only the registration-keeps-hidden-course-visible behaviour. The QA's cross-organisation checks covered cohorts, registrations and hidden courses answering 404, not published courses of other organisations.

2. **Educator-interface-7 learner administration** (`1. spec.md` line 103, 208; plan line 10, 260). Reuses `courses_visible_to` and `registerable_courses_for` unchanged for the learner course filter and register picker. Cross-organisation moves are out of scope. Its isolation tests cover another organisation's learner, cohort and registration pks, never another organisation's course.

3. **Organisation-courses** (`2026-10-27_20:02_organisation-courses/1. spec.md`). This is the closest precedent and the one the current issue builds on.
   - Opening line: "Every course on a site is open to every organisation today."
   - Added `Course.organisations` (M2M) and `Course.audience` (`organisation_learners` | `public`), declared in course.md front matter by organisation slug. Content owns the link; the admin shows the fields read-only.
   - Defined "open to an organisation": not an `organisation_learners` organisation course, or the organisation is one of its organisations. Its §5.3 made `courses_visible_to`, `registerable_courses_for*`, the educator pickers and the Courses list leave out courses not open to the viewed organisation. Superusers are filtered too. A course the organisation already holds a registration for stays visible.
   - Decision (§4): "`public` changes the card and the self-registration organisation, nothing else. A public organisation course is seen, applied for and registered onto from any organisation." So **public organisation courses are deliberately visible and registerable from every organisation**. That is the behaviour the current idea objects to. The reasoning was learner-side discovery (a public course should be findable and applicable by anyone). It did not consider the educator view, even though §5.3 reuses `courses_visible_to` for educators.
   - Unowned courses (no organisations) stay open to every organisation. Courses owned by an organisation with `organisation_learners` audience are already hidden from other organisations' educators. So the gap is: (a) `public` organisation courses and (b) courses with no organisations that are paid, application-gated or otherwise restricted through `access_config`. `access_config` and `course_applications` were explicitly out of scope (§3).
   - Open questions recorded (§8): viewer-aware embed card; which organisation an approved application registers through (default organisation). Research files raised the many-organisation learner question ("most platforms sidestep this by single-membership") and the `RecommendedCourse` scoping collision with the `corporate-job-course-recommendations` effort. Rejected alternative noted in research_prior_art.md line 16: "one Site per client", judged disproportionate when groups share courses.
   - Tests and comments saying "courses are shared across organisations" were to be amended, never deleted. Expect more of these when this spec changes the rule again.

4. **Educator-interface-course-content-preview** (`2026-11-12_11:54_.../research_prior_art.md` line 48; spec line 109). Preview scoping already says the Courses list "omits other organisations' non-public courses", and a preview of another organisation's non-public course returns 404. So preview already treats `public` as the line. The idea here asks to move that line: public no longer implies visible to other organisations' educators. `CourseConfig.authorise_instance` uses `courses_visible_to(...).filter(pk=...)` (content-preview `research_codebase.md` line 39), so fixing the helper fixes list, detail and preview together.

5. **Learner-side gate** (`learner_management/queries.py`, `course_access/backends.py`, `visibility.py` in organisation-courses §5.2): `raise_404_if_unavailable`, `filter_visible` and `get_access` share one "in the audience" definition so list and single-course rules cannot drift. Lesson for this spec: put the educator rule in one shared predicate used by both queryset and single-course forms.

Summary of why it happened: the educator Courses list was built (spec 6) when courses had no owner, and organisation-courses scoped only the `organisation_learners` case while deliberately keeping `public` open to all. The paid and application-gated leak was never discussed in either spec; it is an unexamined interaction, not a recorded decision to expose them.

## Elsewhere (kept tight; no direct hit on the exact pattern)

- **IOMAD** (Moodle multi-tenant plugin). A review comment on iomad/iomad PR #1339 says users should only see courses in their active company but suspects corner cases where one can enrol in a course the editing company has not added, and notes open questions about which company a user belongs to for shared courses. Not a confirmed bug or CVE. https://github.com/iomad/iomad/pull/1339 (also issues 1961, 1970, 1977 on the same tracker, unrelated or tangential).
- **Totara forum**: partners could enrol users in courses they should not reach because a capability (`mod/facetoface:addattendees`) let editing trainers enrol non-enrolled participants; reported as a data-security risk. https://totara.community/mod/forum/discuss.php?d=26422
- **Open edX CVE-2025-68270** (CWE-862, CVSS 9.9): `CourseLimitedStaffRole` granted at organisation level gave access to and modification of courses in Studio beyond those explicitly assigned. Fix: check the role is granted at course level. Lesson: scope checks must be explicit per course and must not infer rights from organisation-level grants. https://dbugs.ptsecurity.com/vulnerability/PT-2025-51780 and https://www.mend.io/vulnerability-database/CVE-2025-68270
- **Open edX CVE-2026-53635** (CWE-862): `set_course_mode_price` protected only by login, no course-level permission check. Same class: a list or write endpoint that trusts "is staff" without checking the object. https://app.opencve.io/cve/CVE-2026-53635
- I found no public Moodle tracker or CVE specifically about a tenant admin viewing or enrolling into another tenant's paid course. The general pattern is missing object-level authorisation (CWE-862, OWASP broken access control), which matches the 404-by-URL requirement in `answers.md`.

## Implications for the spec

- The per-grant model in `answers.md` (`see`, `register`, `preview`, owners implied) goes beyond anything earlier specs had. It reverses spec 6's "shared across the site" premise for educators, and narrows organisation-courses §4 for educators only. Say so in the spec and amend the "shared" comments and tests, never deleting them.
- `courses_visible_to`, `registerable_courses_*`, `CourseConfig.authorise_instance`, the preview scoping and the line-1568 permission check in `educator_interface/views.py` all read one helper. Change the predicate once.
- Existing registrations of another organisation's course must keep showing (spec 6 and organisation-courses both did this; answers.md Q3 agrees).
- Learner-side behaviour (public courses seen and registered by any learner through the course's own gates) must stay unchanged, per answers.md Q7.
- Open items nobody settled: seat caps on a `register` grant (deferred in answers.md Q9); wildcard grants (rejected, Q6); how existing deployments with unowned paid courses migrate (these have no organisations, so "no organisations keeps today's behaviour" leaves the original leak for such courses, which needs an explicit decision).

status: ok · reason: complete; web search found no exact-match incident, only analogous CWE-862 cases
