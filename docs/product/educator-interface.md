# Educator Interface

_Last updated: 2026-08-05_

## Summary

- Educators use a single-page HTMX panel with three sections: Cohorts, Users, and Courses.
- The cohort detail view includes a course-progress matrix showing completion, quiz scores, pass/fail, and deadlines for every student and course item.
- The Courses list shows each course's visibility and an interest count, with drill-down to the interested students. Visibility is read-only here.
- **Access control has a known gap** — the Cohorts and Users listings are permission-filtered, but no detail page is, and the Courses list is not filtered at all. Reads only; writes are gated. See [Access Control](#access-control).
- **Limits:** cohort membership, course registration, and deadline management are admin-only. There is no messaging capability.

## Panel Interface

![Educator panel](screenshots/educator_panel.png)

The educator interface is a single-page application. Navigation within it is HTMX-driven: selecting a section or item updates the main panel, sidebar, and breadcrumb without a full page reload.

### Cohorts

- **List view** — each cohort the educator has permission on, with its student count and registered courses.
- **Detail view** — cohort name (editable inline), student members, and registered courses. Cohorts can be created and deleted.
- **Course Progress tab** — the [progress matrix](#course-progress-matrix).

### Users

Lists users who belong to at least one cohort the educator has permission on, showing name, email, and cohort memberships. The *listing* is filtered this way; an individual user's detail page is not — see [Access Control](#access-control).

### Courses

![Educator courses list with visibility and interest count](screenshots/educator_course_visibility.png)

Lists all courses with their active student and cohort counts. Each course shows its **visibility** — published, coming soon, or hidden — so educators and admins see every course regardless of state; visibility filtering only ever applies to learners, never to educator or admin views.

Unlike the Cohorts and Users lists, this list carries **no permission filter at all** — it is every course on the site, hidden ones included. See [Access Control](#access-control).

Each course also shows an **interest count**: the number of learners who have expressed interest through the coming-soon waitlist. The count and its drill-down are shown for every course, not only coming-soon ones, so a course that has since launched still shows the demand it attracted.

![Interested-students drill-down panel](screenshots/educator_interest_panel.png)

The course detail view shows the title and category, the cohorts registered for the course, any direct non-cohort registrations, and a drill-down panel listing interested students by name with the date they expressed interest — making the waitlist actionable. All of it is scoped to the current site.

Visibility is **read-only** here and in the Django admin. It is set solely in the course's content frontmatter and takes effect on import — see [content editing workflow](./content-editing-workflow.md). The learner-facing experience of coming-soon and hidden courses is covered in [learner experience](./learner-experience.md).

## Course-Progress Matrix

![Cohort progress matrix](screenshots/educator_cohort_progress_matrix.png)

The Course Progress tab on a cohort detail page shows a paginated matrix of students (rows) against course items (columns). Each cell shows completion status (complete / in progress / not started), the quiz score and pass/fail outcome for form items, and the item's deadline with an overdue indicator where the deadline has passed and the item is not complete. Both cohort-level deadlines and per-student overrides are visible.

## Access Control

Educators are granted object-level permission on specific cohorts by an administrator in the Django admin. The educator interface itself has no permission-management UI.

**What is enforced.** Two things. The Cohorts and Users *listings* are filtered to the cohorts the educator has been granted, so an educator's lists show only their own cohorts and the students in them. And every *write* — creating, renaming, or deleting a cohort — checks the object-level permission before it runs.

**Known gap — reads are not permission-checked.** The only gate on the interface as a whole is that the visitor be logged in. Beyond the two listings above, nothing checks whether the visitor has been granted anything:

- **No detail page is permission-checked.** Cohort, user, and course detail pages are all fetched by identifier alone. Any authenticated user on the site who navigates directly to one can read it — for a cohort, that includes the full course-progress matrix: student names, email addresses, completion state, quiz scores, and deadlines.
- **The Courses list is not filtered at all.** It shows every course on the site, including courses authored as `hidden`, which learners cannot otherwise discover.

**Scope of the gap.** This is a read and disclosure defect. Write actions remain gated, so it is not a route to modifying or deleting another educator's data. It is a genuine authorisation gap, not a design decision, and it is tracked in the [roadmap](./roadmap.md).

**Site isolation is unaffected.** All educator interface queries remain scoped to the current site, so nothing here crosses a tenant boundary. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Limits

These operations are **admin-only** and cannot be performed from the educator interface:

- **Cohort membership** — adding or removing students.
- **Course registration** — registering a cohort or an individual student for a course.
- **Deadlines** — cohort deadlines, per-student deadlines, and overrides.

**There is no messaging capability.** Educators cannot send messages or emails to students from FLS.
