# Unstarted course click behaviour — dedicated course detail page

When a student clicks an **unstarted** course (one they have not registered for / started),
take them to a dedicated, beautiful, mobile-responsive **course detail page** that helps them
decide to enrol. Replace the current "modal" preview approach entirely — we will not go back to it.

Clean up as we go: remove the modal code and any code that becomes dead as a result. Tidy up the
files involved and remove debt.

## Approach

- **Navigate to a real page** (full page load / HTMX navigation), not a modal.
- There is already a standalone preview page used as the mobile fallback
  (`course_preview` view + `course_preview.html`, served at `courses/<slug>/preview/`). Make **this**
  the single canonical detail page for everyone (desktop and mobile) and enhance it to match the design,
  rather than introducing a brand-new route. Confirm naming during spec (e.g. rename `preview` → `detail`).
- The course list cards/rows for unstarted courses link straight to this page on **all** screen sizes
  (no desktop modal branch any more).

## Design references

External designs (made by a tool unaware of our setup; they target the First Class theme):

- Hero: ![hero](image.png)
- Main content + sign-up panel: ![main](image-1.png)

**Honesty rule (important):** the designs contain invented stats and placeholder text. Do **not** render
fabricated data. Where a value is unknown for a course, **omit** that element entirely — no `—`, "N/A",
"TBD", or default placeholders on the student-facing page. (See research notes.)

## Page structure

### Breadcrumbs
- Re-use the existing breadcrumbs (`panel_framework/partials/breadcrumbs.html`; crumbs are a list of
  `{label, url}` dicts, last crumb is the current page).
- First crumb: "← all courses" linking back to the all-courses list.

### Hero
- Background uses the course's accent colour (existing `course-accent-<slot>` system — no new colour data).
- Course icon rendered large and semi-transparent, anchored bottom-right (use existing `course_icon` tag).
- Title and brief description (the existing `subtitle`).
- Basic stats strip — render only stats that are genuinely set, each omitted when empty:
  - Number of modules / lessons (derived from the course content structure — always available).
  - **Difficulty level** (new field — see Data model changes).
  - **Estimated duration** (new field — see Data model changes).
- An honest "Free · open enrolment" label is allowed (no payment exists in the system, so this is always
  true). Do **not** show "self-paced" (cohort deadlines mean it isn't universally true).
- If the course has a `category`, it may be shown as a small eyebrow/tag. Do not invent tags like
  "PROBATION" / "OPEN COURSE" from the mock.

### Main content area (left / primary column)
- **About this course** — the longer course description / rendered markdown content. Omit if absent.
- **What you'll learn** — new outcomes list (see Data model changes). Omit the whole section if empty.
- **Course content** — re-use the existing table-of-contents component
  (`student_interface/partials/course_minimal_toc.html`). Do **not** reinvent the TOC.
  - Course content **preview** (opening/viewing items before enrolling) remains out of scope — the TOC
    shows structure only.

### Right-hand sign-up panel
- A surface that lets the user enrol. Single clear primary CTA (e.g. "Enrol & start"); the existing
  one-click `register_for_course` flow is reused unchanged.
- Honest "Free / open to everyone" messaging + short supporting microcopy.
- A small "this course includes" list using **real, derived** data only:
  - lesson/module count, and "includes assessments" when the course has Form children.
- No star rating, no "save for later" / wishlist, no fabricated includes.
- Sticky on desktop; stacks sensibly on mobile (single column). Keep CTA reachable without scrolling to
  the very bottom.

## Data model changes (confirmed with user)

Add these as **real** optional fields on the `Course` model. All degrade gracefully (omitted when empty).
For each: create a migration, add to the admin, and **add values to demo content** so we can see them
in action.

- **What you'll learn** — a list of short outcome statements.
- **Difficulty level** — e.g. Beginner / Intermediate / Advanced (decide field type in spec; likely a
  small set of choices).
- **Estimated duration** — decide representation in spec (free-text like "~2 hours" vs. minutes integer
  that we format). Lean toward something that displays cleanly and sorts/validates sanely.

Decide exact field names, types, and demo-content updates during `/spec_from_idea`.

## Out of scope

- Course content **preview** (viewing/opening course items before enrolling).
- **Certificate on completion** (we issue no real certificate, so a "certificate" claim would itself be
  fake data — explicitly dropped).
- Ratings / reviews and enrolment counts (no backing data).
- "Save for later" / wishlist (no backing model).
- Any payment / pricing concept.

## Cleanup (important)

- Remove the modal-based preview for unstarted courses and the now-dead desktop modal branches in the
  unstarted course card/row partials.
- Remove `course_preview_content.html` (or fold its content into the page) if it is no longer needed once
  the modal is gone.
- Only remove the shared `c-modal` component / its Alpine code if nothing else uses it — verify before
  deleting.
- Leave any unrelated TODO / @claude comments in place.

## Research

See `research_course_landing_ux.md` and `research_enrolment_panel_patterns.md` in this directory for the
UX patterns, honesty guidance, mobile/sticky behaviour, and reference implementations behind the above.
