---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/course_applications/templates/course_applications/application_status.html
  - freedom_ls/course_applications/templates/course_applications/check_your_answers.html
  - freedom_ls/course_applications/templates/course_applications/claim.html
  - freedom_ls/course_applications/templates/course_applications/form_page.html
  - freedom_ls/course_applications/templates/course_applications/partials/application_state_badge.html
  - freedom_ls/course_applications/templates/course_applications/partials/dashboard_applications.html
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: multi-step-course-applications-1-review-states

## Breaking changes

- `CourseApplication` now has a `state` field (`draft`, `submitted`, `approved`, `rejected`, `withdrawn`) and a
  required `organisation` foreign key. Code that creates a `CourseApplication` directly must set `organisation`;
  `freedom_ls.course_applications.queries.organisation_for_new_application(course)` picks the same one FLS uses.
  Change state only through the functions in `freedom_ls/course_applications/transitions.py`
  (`submit_application`, `withdraw_application`, `approve_application`, `reject_application`). Check constraints
  reject rows whose `submitted_at`, `decided_at`, `withdrawn_at` or `rejection_message` disagree with `state`.
- `CourseApplication.is_submitted` and `submitted_time` now read the stored `submitted_at` instead of the form
  sitting's completion time.
- The unique constraint `unique_application_per_site_user_course` is replaced by
  `unique_active_application_per_site_user_course`, which covers only `draft`, `submitted` and `approved`
  rows. An account can now hold several rejected or withdrawn applications for one course.
- `freedom_ls.course_applications.queries.get_active_applications` is renamed to `get_dashboard_applications`.
- The course-applications API payload gains `state`, `organisation_id`, `decided_at` and `withdrawn_at`.
- `CourseAccessDecision` (`freedom_ls/course_access/backends.py`) gains the optional fields `secondary_cta_label`
  and `secondary_cta_url`. Custom backends keep working unchanged because both default to `None`.

## Manual steps

- Run `uv run manage.py migrate` with the app stopped. Migration
  `freedom_ls_course_applications.0010_backfill_application_state` backfills `state`, `submitted_at` and
  `organisation`. It stops with "Site … has no default organisation" when a site has applications on a course
  without exactly one owning organisation and the site has no default organisation. Set a default organisation for
  that site, then migrate again.
- If your project overrides any template in `changed_template_paths`, review it against FLS's version and
  re-apply your changes. `course_detail.html` now renders the secondary call to action (`secondary_cta_label`,
  `secondary_cta_url`). The status page now has the withdraw form, the rejection message and "Apply again".
  `partials/application_state_badge.html` is new.
- Update any call to `get_active_applications` to `get_dashboard_applications`.
