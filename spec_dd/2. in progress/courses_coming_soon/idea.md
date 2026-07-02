# Coming Soon & Hidden Courses

## Summary

Give every course a **visibility status** so the platform can show courses that
aren't yet open for enrolment ("coming soon") and keep some courses out of student
discovery entirely ("hidden"). Today every course is always discoverable, and access
is decided entirely by the active **course-access backend**
(`settings.COURSE_ACCESS_BACKEND`) based on each course's `access_config` (its
*access type*: free vs application-gated).

Visibility is a **new dimension, orthogonal to access type**. A course is independently
*free-or-gated* (its `access_config`) **and** *published / coming-soon / hidden* (its
visibility). The two compose: an application-gated course can also be "coming soon", a
free course can be "hidden", and so on. Crucially, visibility must be enforced **once, in
shared backend code that every concrete backend inherits**, so free, application-gated, and
any future backend honour coming-soon and hidden without bespoke per-backend code.

Note the shipped hierarchy this plugs into: the abstract `CourseAccessBackend` declares the
seams (its `get_access`/`filter_visible` raise `NotImplementedError`); the core
`FreeOnlyCourseAccessBackend` implements the free path; and the **shipped default
`ApplicationCourseAccessBackend`** (in `course_applications`) *subclasses* `FreeOnlyCourseAccessBackend`
to add the `application_gated` access type. Free and application-gated are therefore one
inheritance chain, not two sibling backends — which is exactly what lets a single shared
visibility short-circuit cover both.

For "coming soon" courses, students can't register but can **express interest**
(a lightweight waitlist), giving educators a demand signal for what to launch next.

## Course visibility states

A single `visibility` field on `Course` — a `CourseVisibility` `TextChoices` enum
mirroring the existing `DifficultyLevel` pattern in `content_engine/models.py`. This is a
**normal first-class field, separate from the backend-private `access_config` blob**.
Three states for now:

- **Published** — current behaviour: discoverable everywhere, access decided by the
  active backend (e.g. enrollable for a free course, apply-gated for a gated course).
  This is the **default**, so existing courses stay visible after migration.
- **Coming soon** — appears everywhere a course normally appears (listings, dashboard,
  detail page), clearly badged. Students can't register; they can express interest.
- **Hidden** — not discoverable by students: excluded from all browse/discovery
  surfaces, and the detail page returns 404 for students who aren't registered.

A single enum (rather than separate boolean flags) keeps states mutually exclusive,
makes filtering a one-line predicate, and is trivially extensible. A future `draft` state
(educator-only, invisible even by direct link) can be added as a one-line enum addition if
needed — out of scope for now.

`visibility` is deliberately *not* part of `access_config`: `access_config` is opaque and
backend-private (only the active backend may interpret it), whereas visibility is a
universal lifecycle concept the platform, the content-import layer, and templates all
understand directly.

## How visibility plugs into the access backend

The course-access backend is the single authority for access decisions. It exposes four
seams (`freedom_ls/course_access/backends.py`): `get_access()` returning a
`CourseAccessDecision`, `filter_visible()` for discovery, `validate_course_config()`, and
`get_dashboard_contributions()`. `CourseAccessDecision` is a frozen dataclass whose fields
are `cta_label`, `cta_url`, `can_self_register`, `can_access_content`, plus optional
detail-page funnel copy (`enrolment_summary`, `acquisition_heading`, `acquisition_subtext`).
Visibility hooks into the first two seams:

- **`filter_visible(*, user, courses)`** — the discovery choke-point already wired into
  `dashboard` and `all_courses` (it replaces the old "filter at `get_all_courses()`"
  idea). The base backend drops `hidden` courses **except** those the user is already
  registered for, so registered learners keep access mid-course.
- **`get_access(*, user, course)`** — checked on visibility **before** any access-type
  branching, so the result is uniform across backends:
  - `coming_soon` → an express-interest decision (`can_self_register=False`,
    `can_access_content=False`) whose `cta_label` / `cta_url` drive the "I'm interested"
    affordance.
  - `hidden` + unregistered → a safe no-access decision (`can_self_register=False`,
    `can_access_content=False`, no CTA).
  - `published` → falls through to the existing access-type logic (free → "Start",
    application-gated → "Apply now", etc.).

A naive placement won't be uniform: `FreeOnlyCourseAccessBackend.get_access` holds the
free/registered logic, but `ApplicationCourseAccessBackend.get_access` **overrides** it and
only calls `super().get_access()` for the free-or-registered cases — its
`application_gated`-and-unregistered branch returns its own "Apply now" decision without
ever delegating up. So a visibility check sitting only inside `FreeOnlyCourseAccessBackend.get_access`
would be **bypassed** for a coming-soon or hidden application-gated course. The short-circuit
must therefore live in a **shared prelude / template-method on the abstract
`CourseAccessBackend`** (e.g. a concrete `get_access` that resolves visibility first, then
calls a subclass hook for the published case), or equivalently in a shared helper both
`get_access` overrides call first. It must not be duplicated per subclass. This is the
mechanism that satisfies "every access backend supports coming-soon and hidden". The spec
must pin down the exact placement.

### Visibility rules

- **Students** see Published + Coming soon in browse/discovery surfaces. Hidden courses
  are filtered out at **`backend.filter_visible()`** (already called by `dashboard` and
  `all_courses` over `get_all_courses()`).
- **Hidden detail page**: unregistered students get a 404; registered students keep
  access. Note `get_access()` returns no 404 signal, so `course_detail` must derive
  "visible to this user" (registered, or survives `filter_visible`) to decide the 404 —
  flag this as a spec-level detail.
- **Content gate** (`course_home` / `view_course_item`) is already keyed on
  `decision.can_access_content`; coming-soon and hidden-unregistered naturally yield
  `False`, so the player is closed without extra wiring.
- **Educators / admins** always see all courses regardless of visibility (their querysets
  are unchanged), with the visibility shown as a badge in the course-management list.
- **Hidden + already-registered students keep their access.** Hidden only removes the
  course from discovery — students mid-course aren't disrupted; their dashboard and direct
  URL still work.

## Express interest (waitlist) for coming-soon courses

- On a coming-soon course, the usual enrol/apply CTA is replaced by an **"I'm interested"**
  action (avoids implying a capacity-limited queue). The CTA label and URL come from the
  backend's `CourseAccessDecision` (e.g. `cta_label="I'm interested"`,
  `cta_url=express_interest`), so every backend presents it consistently. Clicking it
  records the student's interest. The same coming-soon decision should also set (or
  deliberately blank) the detail-page funnel copy fields (`enrolment_summary`,
  `acquisition_heading`, `acquisition_subtext`) so the page reads as "coming soon" rather
  than inheriting the free "One click. No credit card." or gated "Application required" copy.
- A new **`CourseInterest`** record captures `user`, `course`, `created_at`, and a
  nullable `notified_at` (unused in v1, but present so launch-notification can be wired up
  later without a migration). Unique on `(user, course)`; created via `get_or_create` so
  repeated clicks are idempotent.
- After expressing interest the CTA visibly changes state (e.g. "Interested" + a quiet
  "remove interest" link) and the user gets inline confirmation. **Students can leave the
  waitlist** — a low-prominence secondary action, not a prominent toggle.
- Coming-soon course cards/rows get distinct status variants (e.g. interested vs.
  not-interested), fitting the existing template-dispatch pattern for card states. The
  per-user "interested vs not" state needs a `CourseInterest` lookup; the "Coming soon"
  badge itself can read `course.visibility` directly (it is a normal field, **not**
  `access_config`, so the backend-private rule does not apply).

## Launch transition (coming soon → published)

**v1 records interest only.** When an educator flips a course's `visibility` from
`coming_soon` to `published`, it simply becomes enrollable (or apply-gated, per its access
type); interested students see it as available on their next visit. There is **no
notification** — FLS has no email/notification system yet, so the UI must not promise one.
The `CourseInterest.notified_at` field is included now so that notify-on-launch (or
auto-enrol) can be added later without model changes. This dependency should be flagged in
the spec.

## Educator visibility of demand

Surface the waitlist as a demand signal: show an **interest count** per coming-soon course
in the educator course-management list, with a drill-down to the list of interested
students. This is what makes the waitlist data actionable (which course to prioritise
launching) rather than data that goes nowhere.

## Content import

Course `visibility` is set from the course front-matter at import (like `difficulty`),
defaulting to `published` for backward compatibility. Because `visibility` is a normal
field — **not** part of `access_config` — it is **not** subject to the backend's
`validate_course_config()` nor the `freedom_ls_course_access.E001` system check, which
validate only the access-type config. Keep the two pipelines distinct so they aren't
conflated.

## Things to design against (from UX research)

- No feedback after clicking interest → must visibly change CTA state + confirm.
- Coming-soon cards indistinguishable from enrollable ones → clear "Coming soon" badge,
  no enrol button.
- Courses stuck in "coming soon" forever with a waitlist nobody looks at → educator
  count/drill-down addresses this.
- No way to leave the waitlist → quiet "remove interest" action included.

## Open questions / dependencies

- **Notification system** is a deferred dependency. The data model is built ready for it;
  the spec should note that "notify interested students on launch" is future work pending
  an email/in-app notification system.
- The **visibility short-circuit must live in the shared base-backend path** so that all
  backends (free + application-gated + any future backend) honour coming-soon and hidden
  without duplication. The spec should pin down exactly where in the
  `CourseAccessBackend` / `FreeOnlyCourseAccessBackend` / `ApplicationCourseAccessBackend`
  hierarchy this lives.
- **Detail-page 404 for hidden courses**: `get_access()` carries no 404 signal, so
  `course_detail` needs a "visible to this user" derivation (registered, or survives
  `filter_visible`). Spec to specify the exact check.

## Out of scope (for now)

- Email / in-app notifications on launch.
- Auto-enrolling interested students on launch.
- A separate `draft` state (educator-only).
- Capacity-limited waitlists / queue positions / scarcity mechanics.

## Research

See `research_visibility_states.md` (how to model course visibility states; reference
implementations) and `research_waitlist_ux.md` (coming-soon + waitlist UX patterns,
pitfalls, educator view) in this directory.
