---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html
  - freedom_ls/learner_interface/templates/learner_interface/dashboard.html
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html
  - freedom_ls/learner_interface/templates/cotton/course-section-pagination.html  # new component
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: better-learner-dashboard-course-display

## Breaking changes

**`Course.category` is gone, and the migration drops the column without preserving its
values.** It is replaced by two relations to a new `CourseCategory` model:
`Course.categories` (many-to-many, every category a course belongs to) and
`Course.dashboard_category` (nullable FK, the one category the dashboard places the course
in). Migration `freedom_ls/content_engine/migrations/0002_alter_course_options_remove_course_category_and_more.py`
runs `RemoveField` — there is no data migration and no automatic path for existing values.
**If you have data in that column, capture it before you migrate.** Nothing in FLS itself
populated the field, so for most projects this column is empty.

Any of your own code reading or writing `course.category` must change. `dashboard_category`
is a `CourseCategory` instance, not a string: `{{ course.category }}` becomes
`{{ course.dashboard_category.title }}`, and a filter on the old string becomes a filter on
`dashboard_category__slug` or `categories__slug`.

**The `category:` key on `course.md` is now rejected rather than ignored.** A content repo
whose course files still carry it fails `content_validate` and `content_save` with a message
naming `categories` and `dashboard_category`. Your content will not load until the key is
changed. (`Topic.category`, `Activity.category`, `CoursePart.category`, `FormPage.category`
and `FormQuestion.category` are untouched — this is only the course-level key.)

**The dashboard view's template context changed shape.** `learner_interface.views.dashboard`
no longer passes `registered_courses`, `completed_courses`, `recommended_courses` or
`available_courses`. It now passes `sections` (a list of `DashboardSection` objects from
`freedom_ls/learner_interface/dashboard_sections.py`), `dashboard_panels` and `has_history`.
Any override of `dashboard.html` or `partials/course_list.html` reading the old keys breaks.

**The per-section partials in `course_list.html` were replaced by one generic partial.**
`{% partialdef current-courses %}`, `recommended-courses`, `available-courses` and
`learning-history` no longer exist; there is now a single `course-section` partial rendered
once per section, plus `section-page`, `section-status`, `section-page-response`,
`section-gone-response` and `in-progress-empty`. An override that includes one of the old
partial names by name will raise.

**`CourseDetailsPanel.fields` in `freedom_ls/educator_interface/views.py` changed from
`["title", "category"]` to `["title", "dashboard_category"]`.** Adjust if you subclass or
override it.

**Visible behaviour changes on a site that configures nothing:**

- Every course grid is capped at three cards and pages to the rest. In progress, Recommended
  courses and Learning history were previously unbounded.
- Coming-soon courses moved out of Available courses into their own "Coming soon" section.
- Section headings are sentence case: "In progress", "Recommended courses", "Available
  courses", "Coming soon", "Learning history". "In Progress" and "Recommended Courses"
  changed.
- `Course.Meta.ordering` is now `["title", "pk"]`, so every unordered `Course` queryset —
  including the flat `/courses/` catalogue — is alphabetical by title where it previously had
  no order at all.
- The dashboard answers its own URL for HTMX section-page requests, keyed off `HX-Target`;
  a plain request to the same URL still returns the whole page.

## Manual steps

1. **Back up `freedom_ls_content_engine_course.category` if it holds anything you need**, then run
   `uv run manage.py migrate`. The column is dropped.
2. **Rebuild Tailwind** (`npm run tailwind_build`, or your project's equivalent). The new
   pagination component and rewritten dashboard sections introduce utility classes your
   bundle does not yet contain.
3. **Re-apply your customisations** to the templates listed in `changed_template_paths`, and
   to any override of the dashboard view's context. `partials/course_list.html` was rewritten
   around the new `sections` list.
4. **Update your content repo.** Author a `course_categories.yaml` at the repo root (see
   `demo_content/course_categories.yaml` for the shape), remove any `category:` key from your
   `course.md` files, and add `categories:` — plus `dashboard_category:` where a course names
   more than one category. Then reload with `content_save`. Category slugs must not be
   `in-progress`, `recommended`, `available`, `coming-soon` or `history`; those are reserved
   for the dashboard's built-in sections.

   Declaring no categories at all is valid: with no `course_categories.yaml` and no
   `categories:` on any course, no category sections render and every course falls through to
   Available courses, three at a time, as before. The pagination, Coming soon and
   sentence-case heading changes listed above still apply.
5. **If you repopulate `dashboard_category` or `categories` by hand** (in the admin or a
   script), declare matching entries in `course_categories.yaml` first. A course naming a slug
   no file declares fails validation, so your next routine `content_save` will fail every such
   course.
6. **Re-run `collectstatic`.** `freedom_ls/learner_interface/static/learner_interface/js/alpine-components.js`
   gained a `courseSectionPagination` Alpine component that moves focus after an HTMX page
   swap. Without it the controls still page — their `href` is a real link — but focus is lost
   on each swap.
