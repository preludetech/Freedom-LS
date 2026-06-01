# All courses list page & course card simplification

Two related pieces of work, informed by the research docs in this directory:

- `research_ux_patterns.md` — LMS course-list UX patterns & accessibility
- `research_component_theming.md` — making card templates easy to theme/override
- `research_query_costs.md` — query-cost analysis (progress bar is cheap; "Next up" is the N+1)

---

# Part A — All courses list page

The "All Courses" page (`student_interface:courses`, view `all_courses`) needs a simpler,
denser presentation.

## Layout

- Replace the tall vertical grid cards (accent hero + centred icon) with a compact
  horizontal **row**: an `icon` area on the **left**, course details on the **right**.

  `[icon][details]`

- The details area leads with the **course title** and a **status indicator**.
- Keep it a single **flat list** of all courses, no grouping or special ordering.
- The whole row is the click target. Use the **stretched-link** pattern (anchor on the
  title with a `::before`/`::after` overlay), not a row-wrapping `<a>` — wrapping the
  whole row in an anchor breaks screen readers and forbids nested interactive elements
  (see `research_ux_patterns.md`).

## Course status (must be correct everywhere)

Every course shows exactly one of four statuses:

- **Not registered** — the user is not registered for the course.
- **Registered** — the user is registered but progress is 0%.
- **In progress** — registered with progress > 0% and not complete.
- **Complete** — the course is complete.

Convey status with **text + icon** (e.g. an eyebrow label and/or a small badge), with
colour only as reinforcement — never colour alone (WCAG 1.4.1). The completed card
already does this well (eyebrow + check badge); follow that pattern.

These four statuses must be derived **cheaply** from a small, constant set of batched
queries for the whole list (all courses + registrations + a single
`CourseProgress.filter(user=…, course__in=…)` read of `progress_percentage` +
`completed_time`). No per-course status queries. See `research_query_costs.md` for the
exact recipe.

## Progress bar

- Show a progress bar on **all registered rows**, including 0% for a registered course
  that hasn't been started yet (mirrors the dashboard card's behaviour).
- This is safe: `progress_percentage` is a **stored column** on `CourseProgress`, so
  reading it for the whole list is one batched query — **no N+1** (`research_query_costs.md`).
- Do **not** show "Next up: <item>". Removing it also removes the expensive
  `_annotate_next_up` → `get_course_index` walk (~20–30 queries *per registered course*),
  which is the real N+1 on this page today.

## Click behaviour (status-aware)

- **Not registered** → open the preview (modal on desktop, preview page on mobile) —
  same as today.
- **Registered** / **In progress** → go straight into the course (course home / first or
  next item), as today for registered courses.
- **Complete** → go to the course finish page.

## Constraints

- **Do not add any new functionality.** This is a simplification + correctness pass.
- **IMPORTANT: the student dashboard course cards must NOT change.** This work only
  changes the all-courses list presentation (and the shared templates *behind* it, in a
  way that keeps the dashboard pixel-identical).

---

# Part B — Course card components & partials

The course-card templates (`cotton/course-card-shell.html`, `partials/course_card.html`,
`partials/course_card_complete.html`, `partials/course_list.html`) are overly
complicated and hard to style/extend/override. Simplify them so a concrete FLS
implementation can easily restyle the **look** of cards without changing how they
**function**.

Full refactor, guided by `research_component_theming.md`, while keeping the dashboard
cards visually identical:

- **Tokenise card shape** — the shell hard-codes radius, hero height and padding. Promote
  these to component-tier theme tokens (e.g. `--fls-card-radius`, `--fls-card-hero-height`,
  `--fls-card-padding`) so a theme can reshape cards without editing markup. (Colour
  theming via `--fls-course-accent-*` is already good and stays.)
- **Kill the duplication** — the stretched-link title block, the eyebrow `<p>`, and the
  repeated link class string appear several times across the card partials. Hoist them
  into the shared shell as named slots / a small partial.
- **Add named cotton slots** (e.g. `eyebrow`, `footer`) plus a mergeable `class` on the
  shell, so an implementation can recompose the card's look without forking behaviour.
- **One card state = one file** — lift the `is_registered` branch out of `course_card.html`
  up to the `dispatch-card` seam so each leaf template is thin and easy to override.
  Keep modal-vs-deeplink as an internal branch (that's behaviour, not look).
- **Document the override ladder**: theme token (shape/colour) → cotton slot/class
  (content) → whole-file template shadow (Django's loader already supports the last via
  the `themes/*/templates` glob).

## Override layers (look vs behaviour)

The goal is that downstream implementations override the **look**, never the
**behaviour**:

1. **Theme tokens** — colours and shape via CSS custom properties.
2. **Cotton slots / vars / class** — recompose content and layout.
3. **Template shadowing** — replace a whole leaf template as a last resort.

---

## Out of scope / guardrails

- No new features, no behaviour changes to navigation or registration.
- Dashboard cards stay exactly as they are.
- Keep this work high-level here; specifics (token names, exact markup) are settled in
  the spec/plan stages.
- Consider adding a `django_assert_num_queries` regression test for the all-courses page —
  no test currently guards its query count (`research_query_costs.md`).
