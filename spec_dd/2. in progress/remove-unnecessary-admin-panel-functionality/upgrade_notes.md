---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/deadlines/templates/admin/deadlines/_action_form.html       # deleted
  - freedom_ls/deadlines/templates/admin/deadlines/extend_deadline.html    # deleted
  - freedom_ls/deadlines/templates/admin/deadlines/pause_course.html       # deleted
  - freedom_ls/deadlines/templates/admin/deadlines/resume_course.html      # deleted
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: remove-unnecessary-admin-panel-functionality

The Django admin no longer manages content, form definitions, learners, cohorts or course
registrations. Learner progress and form answers are view-only in the admin. No model, migration,
URL setting or settings key changed.

## Breaking changes

**Admins removed.** These models are no longer registered with `admin.site`, so their admin URL
names (`admin:freedom_ls_<app>_<model>_changelist`, `_add`, `_change`, `_delete`, `_history`) no
longer reverse:

- `content_engine`: `Topic`, `Article`, `Activity`, `CourseCategory`, `Course`, `CoursePart`,
  `ContentCollectionItem`, `File`. The read-only reference-parts inline on the course page went
  with them.
- `form_engine`: `Form`, `FormPage`, `FormQuestion`, `FormContent`, `QuestionOption`.
- `learner_management`: `Learner`, `Cohort`, `LearnerCourseRegistration`,
  `CohortCourseRegistration`.

A downstream template, link or test that reverses one of these names raises `NoReverseMatch`. A
downstream admin with `autocomplete_fields` pointing at `Course`, `Cohort`, `Learner`,
`LearnerCourseRegistration` or `CohortCourseRegistration` now fails `manage.py check` with
`admin.E039`/`admin.E040`: drop the entry, or use `raw_id_fields` for learner and registration
fields. The same applies to `AutocompleteSelectFilter` on those relations; FLS now uses unfold's
`RelatedDropdownFilter` instead. A project that still wants one of the removed admins registers its
own.

**Custom deadline admin URLs removed.** `admin:freedom_ls_learner_progress_courseprogress_pause`,
`admin:freedom_ls_learner_progress_courseprogress_resume` and
`admin:freedom_ls_learner_progress_courseprogress_extend` are gone, along with the pause, resume and
extend actions on the course progress page and the deadline override inlines on the cohort and
learner registration pages.

**Modules and names removed.** Imports of any of these fail:

- `freedom_ls/content_engine/admin.py`, `freedom_ls/content_engine/forms.py` (`FileAdminForm`)
- `freedom_ls/content_base/admin_filters.py` (`ContentTagListFilter`)
- `freedom_ls/learner_management/admin.py`, including the `LEARNER_SUMMARIES` and
  `LEARNER_SUMMARIES_FIELD` seams, `LearnerAdmin` (and so `LearnerAdmin.inlines`) and the
  `OrganisationCohortInline` and `OrganisationLearnerInline` that were added to `OrganisationAdmin`
- `freedom_ls/learner_management/forms.py` (the four admin forms)
- `freedom_ls/deadlines/admin_views.py` and `freedom_ls/deadlines/forms.py`
- from `freedom_ls/form_engine/admin.py`: `FormAdmin`, `FormPageAdmin`, `FormQuestionAdmin`,
  `FormContentAdmin`, `QuestionOptionAdmin` and their inlines
- from `freedom_ls/hr_attributes/admin.py`: `LearnerHRAttributesInline`
- from `freedom_ls/learner_progress/admin.py`: `LearnerCourseProgressInline`

`ORGANISATION_SUMMARIES` and `OrganisationAdmin.inlines` in `freedom_ls/organisations/admin.py`
remain extension points.

**`ReadOnlyAdminMixin` moved** to `freedom_ls.site_aware_models.admin`. It denies add, change and
delete to every user, superusers included, and works on inlines. Import it from its new home.

**View-only admins.** `TopicProgressAdmin`, `CourseProgressAdmin`, `CourseFormAttemptAdmin`,
`FormProgressAdmin`, `QuestionAnswerAdmin` and `QuestionAnswerFileAdmin`, and their inlines, now
refuse add, change and delete, and have no bulk delete action. The form answers change view and the
answer-file download still work.

**Capabilities with no replacement yet:**

- Editing a learner's HR attributes (it was only on the Learner admin page).
- Deadline overrides, and pausing, resuming and extending a learner's course.
- The course admin's list of reference parts. Educators see reference parts in the Reference panel
  of the course outline in the educator interface.
- Erasing, from the admin, a user who has form progress records. `UserAdmin` refuses, as it already
  did for a user with course progress records.

Learners, cohorts and course registrations are managed in the educator interface. Content comes
from `content_save` only.

## Manual steps

- Search your project for the removed URL names, modules and names above, and for
  `ReadOnlyAdminMixin` imported from `freedom_ls.referral_tracking.admin`; update or remove each.
- If you override any of the four deleted `admin/deadlines/` templates, delete the override.
- If your admins extended `LearnerAdmin`, the other removed admins, or `LEARNER_SUMMARIES`, register
  your own admin for that model or move the feature to the educator interface.
- Run `manage.py check` and fix any `admin.E039`/`admin.E040` errors in your own admins.
- Run `manage.py collectstatic`: `site_aware_models/css/admin.css` changed so changelist card labels
  no longer break mid-word on narrow screens.
