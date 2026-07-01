# Learner Experience

_Last updated: 2026-07-01_

## Summary

- Anonymous (logged-out) visitors can browse the home page, the course catalogue, and individual course detail pages without creating an account. Login is required only at the committing action (enrolment or application). The three personalised dashboard sections (In Progress, Recommended, Completed) are shown only to authenticated learners; anonymous visitors see a value-proposition hero and a discovery section instead.
- Each course listing entry shows an **access-model badge** (Free / By application) so a visitor can tell the access model before clicking through. Each course displays learning outcomes, difficulty, estimated duration, and a description; the acquisition CTA wording is action-forward: free courses show "Enrol for free", application-gated courses show "Apply now" (or "View my application" for a returning applicant).
- The course player unlocks items in sequence and resumes automatically where the learner left off.
- Multi-page forms, quiz feedback (pass/fail, score, optional reveal of incorrect answers), and a course finish page are all built in.
- Hard deadlines lock uncompleted content after expiry; soft deadlines show an overdue indicator without locking.

## Dashboard

![Learner dashboard](screenshots/learner_dashboard.png)

The student dashboard serves as the home page at `/`. Its content branches on whether the visitor is authenticated.

**Anonymous visitors** see a value-proposition hero (a short headline, subtext, and a single "Browse all courses" CTA) at the top of the page, followed by the **Available courses** discovery section showing a sample of courses on the site. The personalised sections — the "Welcome back" greeting, In Progress, Recommended, Learning History, and any backend panels — are not shown. They are omitted entirely rather than shown as "sign in to see this" placeholders.

![Anonymous home page with value-proposition hero and course discovery](screenshots/learner_home_anonymous.png)

**Authenticated learners** see the personalised greeting and three sections:

- **In progress** — courses the learner has started but not completed, ordered by recent activity.
- **Recommended** — courses an administrator has surfaced for the learner.
- **Completed** — courses the learner has finished.

Each course card shows the course title, category, and progress percentage.

When application-gated courses are in use, the authenticated dashboard also shows an **In-flight applications** panel listing any courses the learner has applied to but not yet been enrolled in, each linking to its status page. This panel is absent on installations offering only free courses.

The site header shows **Log in** and **Sign up** affordances for anonymous visitors (carrying a `?next=` parameter so the visitor returns to the page they were on after authenticating). These affordances are absent from the header for authenticated users.

![Learner dashboard with in-flight applications panel](screenshots/learner_dashboard_applications.png)

## Course Listing

The course listing page is publicly accessible — no login is required to browse it. It shows all courses available on the current site.

Each entry shows an **access-model badge** ("Free" or "By application") so a visitor can identify the access model before clicking through to the detail page.

![Course catalogue with Free and By-application access badges](screenshots/learner_catalogue_access_badges.png)

For authenticated learners, the listing additionally shows registration status (not registered, registered/in progress, or completed) and allows navigating directly to a registered course to resume. For anonymous visitors the "Not registered" status eyebrow is suppressed — the access badge serves as the at-a-glance signal instead. Card links point to the public course detail page for all visitors.

## Course Detail Page

![Course detail page](screenshots/learner_course_detail.png)

The course detail page is publicly accessible. Anonymous visitors and authenticated learners alike can view:

- **Learning outcomes** — a list of what the learner will achieve.
- **Difficulty** — one of: beginner, intermediate, advanced, all levels.
- **Estimated duration** — a human-readable estimate of how long the course takes.
- **Description** — full course markdown description.
- **Access-model signal** — the "Enrolment" stat near the CTA shows "Free · open" for free courses and "By application" for application-gated courses.
- **Table of contents** — all items are shown locked for visitors who are not registered, whether anonymous or signed in.

**Acquisition CTA (not-registered visitors).** The CTA label and destination follow the course's access model, so new access models can supply their own wording. For the two access models that exist today:

- Free course → **"Enrol for free"**, which enrols the learner.
- Application-gated course, no prior application → **"Apply now"**, which starts an application.
- Application-gated course, existing application → **"View my application"**, which links to the learner's application status page.

The CTA label is action-forward and does not mention login; an anonymous visitor is taken through the standard login or signup flow automatically when they click the CTA (see [Deferred-login intent completion](#deferred-login-intent-completion) below). See [configuration and extension](./configuration-and-extension.md) for how access types are configured per course.

**Progress-aware CTA (already-registered learners).** For learners who are already enrolled, the detail page shows a progress-aware CTA regardless of access model: "Start course", "Continue", or "Review course", pointing at the appropriate position in the course.

## Deferred-login Intent Completion

When an anonymous visitor clicks an acquisition CTA ("Enrol for free" or "Apply now"), they are sent through the standard full-page login or signup flow via a `?next=` parameter. After authenticating, their intended action completes automatically:

- **"Enrol for free"** — after login or signup, the learner is enrolled and dropped straight into the course content with no additional click.
- **"Apply now"** — after login or signup, the learner lands on the apply confirmation page, ready to submit. The application is not auto-submitted; applying is a deliberate action.

This intent is preserved even through the new-user signup path that requires completing additional registration forms. For how the intended destination is preserved through signup, see [Authentication](./authentication.md).

## Discoverability

Because the catalogue and course detail pages are public, they are crawlable. Each page emits a per-page `<title>` and `<meta name="description">`. Course detail pages include `schema.org/Course` JSON-LD structured data (populated only from fields that exist in the model: title, description, difficulty, estimated duration, learning outcomes, and whether the course is accessible for free). The catalogue page includes `schema.org/ItemList` JSON-LD covering the visible courses and their detail URLs.

The installation serves a dynamic per-site `sitemap.xml` listing the catalogue and all course detail pages, and a `robots.txt` that allows crawling of the public course paths and references the current site's sitemap. All URLs in structured data and the sitemap are absolute and tenant-correct. For details of per-tenant URL isolation, see [Multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Self-Registration

When a learner enrols in a free course from its detail page, they are registered and their progress record is created in a single step — no administrator action is needed for a free course.

Access is enforced server-side: a learner cannot self-register for an application-gated course by guessing a URL. Attempting to do so routes them into the application flow instead. Administrator and cohort enrolment deliberately bypass this gate and work for any course regardless of access type.

Content within a course is also gated consistently: a learner who is not entitled to a course's content is redirected to the course detail page rather than reaching item content directly.

## Applying to a Course

Courses configured as application-gated present an "Apply now" CTA on the course detail page; the course content is locked until the learner is enrolled.

![Application-gated course detail page with "Apply now"](screenshots/learner_course_detail_gated.png)

Selecting "Apply now" leads to a confirmation page ("Apply to \<course\>?"); confirming creates the application and shows a status page confirming it has been received and is pending review.

![Apply confirmation page](screenshots/learner_apply_confirm.png)

![Applicant status page](screenshots/learner_application_status.png)

Applying is idempotent: a learner who has already applied for a course is taken directly to their existing application's status page rather than creating a duplicate submission.

The application records only that the learner applied — it collects no questions or file uploads, and there is no review or approval workflow: the status page is static, with no reviewer messages or withdraw action. Multi-step application forms and application review are planned; see [roadmap](./roadmap.md).

Access type is configured per course through the content-loading pipeline; see [content editing workflow](./content-editing-workflow.md) for authoring details and [configuration and extension](./configuration-and-extension.md) for the backend settings.

## Course Player

![Course player](screenshots/learner_course_player.png)

The course player displays one content item at a time.

### Sequential Item Unlock

Items unlock in order: a learner can start an item once the previous one is complete, cannot skip ahead, and a form or quiz that does not reach its pass threshold is marked failed. The first item is always available.

### Course Parts (Chapters)

Courses can be divided into parts (chapters); the player shows part-level progress for orientation.

### Resume

Returning to a course sends the learner straight back to the item they last viewed, so they never have to find their place.

## Multi-Page Forms

Form items can span multiple pages. A learner can leave a form part-way through and resume later with their answers preserved.

## Quiz Feedback

![Quiz feedback](screenshots/learner_quiz_feedback.png)

After submitting a quiz, the learner sees:

- **Pass or fail.**
- **Score percentage.**
- **Incorrect answers** — if the quiz is authored to reveal incorrect answers (`quiz_show_incorrect`), the learner sees which they got wrong; otherwise only the pass/fail result and score are shown.

Learners can attempt a quiz more than once.

## Course Finish Page

![Course finish page](screenshots/learner_course_finish.png)

When every item in a course is complete, the learner reaches a finish page and the course moves to the completed section of their dashboard. There is no certificate or downloadable completion evidence.

## Deadlines

Deadlines are set by administrators (cohort-level or per-student) and are read-only from the learner's perspective.

- **Hard deadline** — if the deadline has expired and the item is not yet complete, the item is locked. A lock icon is shown and the learner cannot access the item.
- **Soft deadline** — the deadline is shown as overdue without locking the item. The learner can still access and complete the content.

The most permissive deadline governs when both a cohort deadline and a per-student override apply. The deadline feature can be disabled site-wide via the `DEADLINES_ACTIVE` setting.
