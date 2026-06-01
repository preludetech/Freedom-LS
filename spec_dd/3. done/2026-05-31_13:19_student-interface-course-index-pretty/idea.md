Update the student dashboard (course index landing page) so it looks and feels
good, in line with designs made by Claude Design. This is a **visual / layout
refresh only** — we are making the current implementation look more like the
design, not adding new functionality or faked data.

**Scope: strictly the changes listed below.** No continue-learning hero, no
stats/streak panel, no card-level restyling, no faked placeholder content. Where
the design implies heavier infrastructure, it is explicitly out of scope here.

## Changes needed

### Heading / greeting area

- Left-align the "Welcome back, {first name}" greeting (currently centred).
- It remains the page's single H1, visually the largest/boldest text on the page.
- Add a small **date eyebrow** line *above* the greeting (e.g. "Friday · 30 May
  2026"). Keep it visually subordinate to the greeting — smaller, lighter/muted,
  unambiguous locale-appropriate format. It is calm orientation chrome, not a
  load-bearing element.

### Section styling (In progress / Recommended / Available / History)

- **Remove the borders / boxed `surface` containers** around the sections. Group
  sections with whitespace and typographic hierarchy instead (the modern,
  research-backed default — boxes around whole sections add visual noise without
  signalling a real relationship).
- Section headings become **smaller and left-aligned**, with a clear size/weight
  step down from the H1 greeting (H1 → section heading → card title). Headings
  front-load the meaningful keyword.

### Available courses section (new)

- Add a **new "Available courses" section** to the dashboard. The existing
  "Recommended Courses" section stays as-is alongside it.
- Show a **capped preview of max 3 courses**: the first 3 available courses the
  student is **not** registered for, using the existing default ordering from the
  all-courses page.
- Add a **right-aligned "Browse all courses" link/affordance** in the section
  header, next to the "Available courses" heading (Netflix/Spotify/LinkedIn
  convention — the user learns more exists before scanning). It links to the
  existing all-courses page (`student_interface:courses`).
  - Must be a real, keyboard-focusable `<a>`/link with self-describing text for
    screen-reader users ("Browse all courses").
- **Remove the bottom "All Courses" button** — the header-right "Browse all
  courses" link replaces it. (Keep the existing empty-state "Browse courses"
  button shown when the student has no registered courses.)

## Confirmed behaviour

- If there are **fewer than 3** unregistered available courses, show whatever is
  available (1–2 cards). If there are **none**, the whole section (heading +
  "Browse all courses" link) hides gracefully — no empty box.
- "Available courses" **excludes courses already shown in the "Recommended
  Courses" section**, so the same course never appears in both. The exclusion
  applies before the max-3 cap (i.e. the first 3 *non-recommended* unregistered
  courses).

# Source material

Visual designs (external React prototype): `@ $HOME/workspace/lms/design/Learner
Experience v3.html` — look only at the "dashboard".

The designs come from an external tool that is **not** aware of our codebase.
They assume functionality and intentions that don't always fit our stack.
**Don't scope creep.** Where a design implies heavy infrastructure, ask for
scoping decisions.

Do not add any weird placeholder content or faked functionality. We are simply
making our current implementation look more in line with the given design.

Supporting research lives alongside this idea:
- `research-dashboard-ux-patterns.md` — per-platform patterns (greeting, capped
  sections + "Browse all", section structure).
- `research-dashboard-ux-best-practices.md` — NN/g-grounded guidance on
  borderless grouping, heading hierarchy/alignment, date display, "show a few +
  see all".

## Theming

The prototype was drawn to match the **first_class** theme. Implement each widget
in the **default** theme using standard role tokens (`--color-primary`,
`text-on-surface`, `bg-surface`, status tokens, `--fls-radius-*`, etc.), then
override in the **first_class** theme only where the brand look needs it. The
brand colours/shapes in the prototype already flow from the first_class theme
tokens — widgets should not hardcode hex values.
