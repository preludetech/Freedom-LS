# Learner Experience

_Last updated: 2026-07-01_

## Summary

- Anonymous (logged-out) visitors can browse the home page, the course catalogue, and individual course detail pages without creating an account. Login is required only at the committing action (enrolment or application). The three personalised dashboard sections (In Progress, Recommended, Completed) are shown only to authenticated learners; anonymous visitors see a value-proposition hero and a discovery section instead.
- Each course listing entry shows an **access-model badge** (Free / By application) so a visitor can tell the access model before clicking through. Each course displays learning outcomes, difficulty, estimated duration, and a description; the acquisition CTA wording is action-forward: free courses show "Enrol for free", application-gated courses show "Apply now" (or "View my application" for a returning applicant).
- The course player enforces sequential item unlock (BLOCKED → READY → IN_PROGRESS → COMPLETE/FAILED) and resumes automatically at the last accessed item.
- Multi-page forms, quiz feedback (pass/fail, score, optional reveal of incorrect answers), and a course finish page are all built in.
- Hard deadlines lock uncompleted content after expiry; soft deadlines show an overdue indicator without locking.

## Dashboard

![Learner dashboard](screenshots/learner_dashboard.png)

The student dashboard (`student_interface:dashboard`) serves as the home page at `/`. Its content branches on whether the visitor is authenticated.

**Anonymous visitors** see a value-proposition hero (a short headline, subtext, and a single "Browse all courses" CTA) at the top of the page, followed by the **Available courses** discovery section showing a sample of courses on the site. The personalised sections — the "Welcome back" greeting, In Progress, Recommended, Learning History, and any backend panels — are not shown. They are omitted entirely rather than shown as "sign in to see this" placeholders.

![Anonymous home page with value-proposition hero and course discovery](screenshots/learner_home_anonymous.png)

**Authenticated learners** see the personalised greeting and three sections:

- **In progress** — courses the learner has started but not completed, ordered by recent activity.
- **Recommended** — courses surfaced via `RecommendedCourse` records (set by site administrators).
- **Completed** — courses for which `CourseProgress.completed_time` is set.

Each course card shows the course title, category, and progress percentage.

When the application-gated access type is in use, the authenticated dashboard also shows an **In-flight applications** panel listing any courses the learner has applied to but not yet been enrolled in, each linking to its application status page. This panel appears only when the active course-access backend contributes it; it is absent on installations using only free courses.

The site header shows **Log in** and **Sign up** affordances for anonymous visitors (carrying a `?next=` parameter so the visitor returns to the page they were on after authenticating). These affordances are absent from the header for authenticated users.

![Learner dashboard with in-flight applications panel](screenshots/learner_dashboard_applications.png)

## Course Listing

The course listing page (`student_interface:courses`) is publicly accessible — no login is required to browse it. It shows all courses available on the current site.

Each entry shows an **access-model badge** ("Free" or "By application") so a visitor can identify the access model before clicking through to the detail page.

![Course catalogue with Free and By-application access badges](screenshots/learner_catalogue_access_badges.png)

For authenticated learners, the listing additionally shows registration status (not registered, registered/in progress, or completed) and allows navigating directly to a registered course to resume. For anonymous visitors the "Not registered" status eyebrow is suppressed — the access badge serves as the at-a-glance signal instead. Card links point to the public course detail page for all visitors.

## Course Detail Page

![Course detail page](screenshots/learner_course_detail.png)

The course detail page (`student_interface:course_detail`) is publicly accessible. Anonymous visitors and authenticated learners alike can view:

- **Learning outcomes** — a list of what the learner will achieve.
- **Difficulty** — one of: beginner, intermediate, advanced, all levels.
- **Estimated duration** — a human-readable display of the `estimated_duration` field.
- **Description** — full course markdown description.
- **Access-model signal** — the "Enrolment" stat near the CTA shows "Free · open" for free courses and "By application" for application-gated courses.
- **Table of contents** — all items render as blocked (no URLs) for visitors who are not registered, which is the expected behaviour for both anonymous and not-yet-registered authenticated visitors.

**Acquisition CTA (not-registered visitors).** The CTA label and destination are owned by the active course-access backend, so a future access model can supply its own wording without changing the detail page. For the two access models that exist today:

- Free course → **"Enrol for free"**, which targets the enrolment endpoint.
- Application-gated course, no prior application → **"Apply now"**, which targets the apply view.
- Application-gated course, existing application → **"View my application"**, which links to the learner's application status page.

The CTA label is action-forward and does not mention login; an anonymous visitor is taken through the standard login or signup flow automatically when they click the CTA (see [Deferred-login intent completion](#deferred-login-intent-completion) below). See [configuration and extension](./configuration-and-extension.md) for how access types are configured per course.

**Progress-aware CTA (already-registered learners).** For learners who are already enrolled, the detail page shows a progress-aware CTA independent of the access backend: "Start course", "Continue", or "Review course", pointing at the appropriate position in the course.

## Deferred-login Intent Completion

When an anonymous visitor clicks an acquisition CTA ("Enrol for free" or "Apply now"), they are sent through the standard full-page login or signup flow via a `?next=` parameter. After authenticating, their intended action completes automatically:

- **"Enrol for free"** — after login or signup, the learner is enrolled and dropped straight into the course content with no additional click.
- **"Apply now"** — after login or signup, the learner lands on the apply confirmation page, ready to submit. The application is not auto-submitted; applying is a deliberate action.

This intent is preserved even through the new-user signup path that requires completing additional registration forms. For the technical details of how `?next=` survives the registration-completion step, see [Authentication](./authentication.md).

## Discoverability

Because the catalogue and course detail pages are public, they are crawlable. Each page emits a per-page `<title>` and `<meta name="description">`. Course detail pages include `schema.org/Course` JSON-LD structured data (populated only from fields that exist in the model: title, description, difficulty, estimated duration, learning outcomes, and whether the course is accessible for free). The catalogue page includes `schema.org/ItemList` JSON-LD covering the visible courses and their detail URLs.

The installation serves a dynamic per-site `sitemap.xml` listing the catalogue and all course detail pages, and a `robots.txt` that allows crawling of the public course paths and references the current site's sitemap. All URLs in structured data and the sitemap are absolute and tenant-correct. For details of per-tenant URL isolation, see [Multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Self-Registration

A learner who is not yet registered for a free course can register from the course detail page. The `initiate_course_access` view (`student_interface:initiate_course_access`) is the access chokepoint: it consults the active course-access backend and, for a free course, self-registers the learner — creating a `UserCourseRegistration` record and an initial `CourseProgress` record in a single step. No administrator action is needed for self-registration on a free course.

The chokepoint is enforced server-side: a learner cannot self-register for an application-gated course by guessing a URL. Attempting to do so routes them into the application flow instead. Administrator and cohort enrolment deliberately bypass this gate and work for any course regardless of access type.

Content within a course is also gated consistently: a learner who is not entitled to a course's content is redirected to the course detail page rather than reaching item content directly.

## Applying to a Course

Courses configured as application-gated present an "Apply now" CTA on the course detail page; the course content is locked until the learner is enrolled.

![Application-gated course detail page with "Apply now"](screenshots/learner_course_detail_gated.png)

Selecting "Apply now" leads to a confirmation page ("Apply to \<course\>?"); confirming creates a `CourseApplication` record and redirects the learner to a status page (`course_applications:status`) that confirms the application has been received and is pending review.

![Apply confirmation page](screenshots/learner_apply_confirm.png)

![Applicant status page](screenshots/learner_application_status.png)

Applying is idempotent: a learner who has already applied for a course is taken directly to their existing application's status page rather than creating a duplicate submission.

The application records only that the learner applied — it collects no questions or file uploads, and there is no review or approval workflow: the status page is static, with no reviewer messages or withdraw action. Multi-step application forms and application review are planned; see [roadmap](./roadmap.md).

Access type is configured per course through the content-loading pipeline; see [content editing workflow](./content-editing-workflow.md) for authoring details and [configuration and extension](./configuration-and-extension.md) for the backend settings.

## Course Player

![Course player](screenshots/learner_course_player.png)

The course player (`student_interface:view_course_item`) displays one content item at a time, identified by its position index within the course (`courses/<slug>/<int:index>/`).

### Sequential Item Unlock

Items are unlocked in order. Each item carries a status derived at runtime:

| Status | Meaning |
|---|---|
| `BLOCKED` | A preceding item is not yet complete; this item is inaccessible. |
| `READY` | The preceding item is complete (or this is the first item); the learner may start. |
| `IN_PROGRESS` | The learner has opened this item but not completed it. |
| `COMPLETE` | The item is finished. |
| `FAILED` | A form/quiz item was submitted and did not meet the pass threshold. |

The first item in a course always starts as `READY`. A learner cannot skip ahead; attempting to access a `BLOCKED` item redirects back.

### Course Parts (Chapters)

Courses may be divided into `CoursePart` groupings (chapters or sections). Each part derives a composite status (COMPLETE / IN_PROGRESS / BLOCKED) from the statuses of its child items. Parts are displayed in the player navigation for orientation.

### Resume

`CourseProgress.last_accessed_item` is a `GenericForeignKey` that records the most recently viewed item. Navigating to the bare course URL redirects the learner to this item automatically, so they do not need to find their place manually.

## Multi-Page Forms

Form-type content items may span multiple pages. The form workflow is:

1. Start (`student_interface:form_start`)
2. Fill a page (`student_interface:form_fill_page`)
3. Advance to the next page or submit the final page
4. Completion recorded (`student_interface:course_form_complete`)

A learner can also exit a form mid-way (`student_interface:form_submit_and_exit`); progress is preserved and the form can be resumed.

## Quiz Feedback

![Quiz feedback](screenshots/learner_quiz_feedback.png)

After submitting a quiz (form with `QUIZ` scoring strategy), the learner sees:

- **Pass or fail** — derived from `FormProgress.passed()`.
- **Score percentage** — derived from `FormProgress.quiz_percentage()`.
- **Incorrect answers** — if the course is configured with `quiz_show_incorrect=True`, the items the learner answered incorrectly are revealed. If `quiz_show_incorrect=False`, only the aggregate result is shown.

Multiple attempts are supported: a new `FormProgress` record is created for each attempt; only the most recent incomplete or the latest completed attempt is active.

## Course Finish Page

![Course finish page](screenshots/learner_course_finish.png)

When all items in a course are complete, the learner is directed to the course finish page (`student_interface:course_finish`). `CourseProgress.completed_time` is set and the course moves to the completed section of the dashboard. There is no certificate or downloadable completion evidence.

## Deadlines

Deadlines are set by administrators (cohort-level or per-student) and are read-only from the learner's perspective.

- **Hard deadline** — if the deadline has expired and the item is not yet complete, the item is locked. A lock icon is shown and the learner cannot access the item.
- **Soft deadline** — the deadline is shown as overdue without locking the item. The learner can still access and complete the content.

The most permissive deadline governs when both a cohort deadline and a per-student override apply. The deadline feature can be disabled site-wide via the `DEADLINES_ACTIVE` setting.
