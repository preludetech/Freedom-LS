# Research: best practices for organisation-scoped courses

## Web-sourced findings
1. LMS vendors scope the catalog by organisational unit and make unassigned units unable to see the course. Assigning a course to specific units is the main way to build a per-organisation catalog. Source: https://info.latitudelearning.com/blog/restrict-course-visibility-and-enrollment-timeline
2. Visibility is usually a small enum: public, private (manual enrolment only), or selected audience. Sesame HR offers all three. Source: https://sesamehr.helpjuice.com/en_US/tipos-de-visibilidad-de-curso
3. Multi-tenant LMS guidance: audience-based visibility so each department sees only its own learning, and course-creation rights limited to the organisation's own content. Sources: https://elearningindustry.com/learning-management-system-to-support-multi-tenancy-how-use and https://elearningindustry.com/when-a-multi-tenant-lms-actually-makes-sense
4. Catalog access limited through assignment profiles (SAP SuccessFactors, in Viva Learning). This is the same idea as an allow-list on the course. Source: https://learn.microsoft.com/en-us/viva/learning/manage-catalog-access
5. Django docs: use a plain `ManyToManyField` when the link carries no data. Use a `through` model when it does, and add a `UniqueConstraint` yourself on a custom through model. Source: https://docs.djangoproject.com/en/stable/topics/db/models/#extra-fields-on-many-to-many-relationships
6. I found no single authoritative best-practices guide. The points above are vendor documentation, so treat them as convention, not standard.

## Codebase observations
- `freedom_ls/organisations/models.py` already has `Organisation(SiteAwareModel, TimestampedModel)`. It has name, slug, `logo`, `logo_on_dark`, `is_default` and `initials` (a monogram fallback). Each Site has a default Organisation. The logo fields are documented as being for "anywhere the organisation appears on screen", so a card can reuse them.
- `Course` is in `freedom_ls/content_engine/models/courses.py`. It is a content model, loaded from markdown by the content loader. It has `access_config` (backend-private) and `application_form`. Course applications must not change, so the new restriction must not touch `access_config` or the access backend.
- Cards live in `freedom_ls/learner_interface/templates/cotton/course-card.html`, with `partials/course_list.html` and `course_row.html`, and views in `learner_interface/views.py`.

## Recommendations
1. Model: add a plain `ManyToManyField("organisations.Organisation", blank=True, related_name="courses")` on `Course`. Empty means available to all, and non-empty means restricted to the listed organisations. This is the allow-list pattern from findings 1 and 4. Use a through model only if per-link data is needed, and none is in the idea. Cross-app dependency direction: content_engine would then depend on organisations, so check for circular imports and use a string reference.
2. Independent per-organisation versions: model them as separate `Course` rows with the same title and different slugs. Each is restricted to its own organisation. This fits the idea ("completely independent"). The slug and title uniqueness constraints per site need checking, because same-name courses must be allowed. Progress, registrations and content stay per row with no extra sharing logic.
3. Enforce visibility in one place, a queryset or manager method such as `Course.objects.visible_to(organisations)`. Do not filter in each template or view. Filter in the learner dashboard, the course browse and the direct course URLs, so a restricted course returns 404 for a non-member who guesses the URL. A hidden card alone is not access control. Learners already registered or in progress should keep access, so that restriction changes do not strand them. This is a decision to confirm in the spec.
4. Keep the org-visibility check separate from the course-access backend. Applications and `can_self_register` stay untouched, in line with the idea and the "backend-private" rule on `access_config`.
5. Cards: show the organisation only when the course is scoped to exactly one organisation (the apply-to-join case). Show it on in-progress cards too. Reuse `Organisation.logo`, with the `initials` or name as fallback, as the Organisation docstrings intend. Pick `logo` or `logo_on_dark` by the card background. Prefetch the M2M (`prefetch_related`) to avoid N+1 queries on the dashboard. Compute "single organisation" once in the view or a template tag, not in the template.
6. For multi-organisation or unrestricted courses, show no organisation badge. The idea does not specify that case, so flag it as an open question.
7. Content loading: content comes from markdown, so decide how organisation links are declared (front matter, or admin only). Loading should not wipe admin-set links on reload. This is an open question for the spec.
8. Multi-site: Organisation is `SiteAwareModel`. Validate that a course's organisations belong to the same site as the course, in `clean()` or an M2M-changed signal.
9. Tests: cover unrestricted, single-organisation, multi-organisation, a non-member hitting the URL directly, and an in-progress card for a restricted course.

status: ok
