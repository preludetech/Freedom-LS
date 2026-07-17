# Make the course details page reachable for registered learners

## Problem

Once a learner has registered for a course, the app sends them into the course
player and there is no obvious way back to the **course details page** (the
public overview: description, "what you'll learn", content table-of-contents).
That page is useful for revisiting the overview and, because it is a stable
public URL, for sharing the course with a friend or organisation.

The details page already exists (`student_interface:course_detail`, slug-based)
and is already accessible to registered learners — it just isn't linked from the
places a registered learner naturally is. We only need to add entry points; we
do **not** need a new "share" feature: the details page *is* the shareable URL,
so simply landing on it and copying the address bar is enough (this matches how
Udemy, Coursera and edX handle it).

## Approach

Add a consistent, secondary "Details" entry point on three surfaces. It must
stay clearly secondary — "Continue / Start" remains the one primary action on
each course; the "Details" affordance is low-emphasis and must not compete with
it.

### 1. Dashboard course cards

- The card as a whole keeps its current behaviour (the stretched link into the
  course player).
- Add a **direct, always-visible "Details" affordance** in the card's
  **bottom-right** corner, linking to the course details page.
  - This replaces the originally-proposed single-item kebab menu: UX authorities
    (NN/g, Material, Carbon, Apple HIG) reserve overflow/3-dots menus for hiding
    *two or more* secondary actions; wrapping one link in a menu only adds a
    click and roughly halves discoverability. A visible affordance is simpler and
    more discoverable. If per-card actions grow to 2+ later, revisit a menu then.
  - Bottom-right is the conventional "more options" corner (top-right is busy on
    the registered card, which already carries the hero + status eyebrow;
    bottom-left is not an attested placement anywhere).
  - The affordance is a real `<a>` that is a **sibling** of the stretched link,
    raised above the stretched overlay (`relative z-10`) so it stays clickable,
    with the overlay's hit area kept clear of that corner to avoid mis-clicks.
    The card/row shells already reserve this seam.
  - Accessibility: adequate touch target (≈44×44px) and an accessible name. If
    rendered icon-only, pair the icon with an `aria-label`/visible label of
    "Details".

### 2. Course index / list rows

- Give each course row the same "Details" entry point, keeping the label and
  destination identical to the card. Consistency here means same *meaning and
  wording*, not pixel-identical presentation — a row has more horizontal room, so
  an inline "Details" link is fine even though the card uses a corner affordance.

### 3. Course player breadcrumbs

- Repoint the **first breadcrumb** (the course title) to the course **details
  page**. It currently links to the first course item, which behaves like a
  "start over" action.
- Linking the course title to the details/overview page is the standard,
  least-surprising behaviour (Moodle and Canvas both do exactly this) and doubles
  as the shareable-URL entry point from inside the player.

## Reuse notes

- Existing building blocks cover this: `student_interface:course_detail` (the
  destination), the `more_options`/info `<c-icon>` set, and the card/row shells
  (`cotton/course-card-shell.html`, `cotton/course-row-shell.html`) whose
  `relative` + z-index seam is already reserved for a control above the stretched
  link. No new models or URLs are needed.
- The breadcrumb change is a small edit to
  `partials/player_breadcrumbs.html` (the first crumb's `href`).

## Out of scope

- A bespoke share feature (social buttons, copy-link, Web Share API). The
  details page URL already satisfies the sharing need; a "Copy link" action could
  be a fast-follow if there is demand, but it is not part of this work.
- Any change to the details page content itself or to who may access it.

## Open questions / to confirm during spec

- Exact affordance styling (icon-only vs icon+label) and label wording
  ("Details" is the working label; keep it identical across all surfaces).
- Whether every card/row *state* (registered/in-progress, complete,
  not-registered, coming-soon) gets the affordance, or only states where a
  registered learner benefits. The not-registered card already links to the
  details page as its whole click target, so it likely needs nothing extra.
