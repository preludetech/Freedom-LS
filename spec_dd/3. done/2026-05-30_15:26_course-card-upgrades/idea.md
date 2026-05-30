When a learner logs in they land on their home page. This is a dashboard from which they can navigate to courses. We need to update it in many ways.

# 1. Course icons - data structure

Courses can have a thumbnail icon, referenced by a **semantic name** from the FLS icon system (the same name space `c-icon` resolves — e.g. `"star"`, `"topic"`, `"course_part"`). It is a string field on the course content schema, not a file upload.

- Add an `icon` field to the course schema and the `Course` model.
- Update `freedom_ls/content_engine/management/commands/content_save.py` so that when a course definition specifies `icon`, the value is persisted to the database.
- If a course does not specify an icon, fall back to a default. **Add a new `"course"` entry to the icon registry** (the existing semantic set already has `topic`, `form` and `course_part` but no plain `course`) and use it as the default.
- Update one of the `demo_content/` courses to demonstrate a custom icon, so the demo data exercises both the explicit and default paths.

# 2. Per-course accent colour

Each course gets a deterministic accent drawn from the active theme's tokens, so the same course always looks the same and theme switches keep working.

- Build a small helper modelled on `freedom_ls.base.context_processors.branch_name_to_color`, but **the output must be a role-token name from a fixed palette subset**, not an arbitrary HSL hex. Hash the course slug (or title) and pick from: `primary`, `secondary`, `accent`, `info`, `success`. Deliberately **excludes `error` and `warning`** — a red "Intro to Python" card reads as broken (see `research_palette_mapping.md`).
- The helper returns the role token name (e.g. `"accent"`), not a hex value. Templates render the icon at the role colour over a tinted background derived from the same role (the Material 3 "container / on-container" pattern, e.g. `bg-{{ role }}-soft text-{{ role }}`). The course title text stays on `--color-on-surface`.
- Don't store the resolved colour on the model — recompute it on read.

# 3. Dashboard course card

Three visually distinct states. Same overall card silhouette in each state; different content slot.

**In progress**
- Themed icon on tinted background
- Eyebrow: `In progress`
- Course title
- `Next up: <next topic title>` — small muted line so learners know where Continue will land (Coursera / Khan Academy / LinkedIn Learning all converge on this).
- Progress bar + numeric percent. Use `role="progressbar"` with proper aria.
- Click → next portion of the course.

**Not started**
- Themed icon on tinted background
- Eyebrow: `Not started`
- Course title
- Click → preview UI containing title, subtitle, description, table of contents, and a `Start` button (when the learner can start). **No deadlines, no extra metadata.**
- The preview is a **modal on desktop** and a **dedicated page on mobile** — modals on narrow viewports overflow and fight the back gesture. The modal/page contents are the same; only the presentation differs.

**Complete**
- Themed icon on tinted background
- Eyebrow: `Completed` plus a check-shape badge — state is conveyed by text **and** shape, never colour alone (WCAG 1.4.1).
- Click → existing "Course is complete" page.

## Click target & accessibility

- The whole card is the click target, but **don't wrap the card in `<a>`**. Use the "linked title + stretched pseudo-element" pattern (Inclusive Components / NN/g): the semantic link sits on the title, a `::before` overlay extends the hit zone, focus ring uses `:focus-within` so it wraps the whole card.
- Eyebrow text and badge shape carry the state; colour is decorative.
- One primary action per card. Any future secondary controls (unenrol, view certificate) sit above the overlay with their own focus.

# Out of scope for this spec

- Card secondary actions (unenrol, share, view certificate).
- A "Continue where you left off" hero block above the card grid (research suggests this is a strong follow-up, but it's a separate feature).
- Editor-controlled colour override on a course (the role-token helper makes this easy to add later — leave the seam, don't build it).
- Photographic course thumbnails (uploaded images). The icon-on-tint approach is the only path for now.

# Resources

- `card/in-progress-card.html` — reference layout. Note: it uses the `first_class` theme's bespoke colour classes (`ct-weather`, `fc-chip-primary`, etc.) and adds extras like deadlines that are out of scope. Use **theme tokens** (`--color-primary`, `bg-{role}-soft`, etc.), not first_class-specific classes, and only render the fields listed above.
- `research_reference_implementations.md` — how Coursera, Udemy, Khan Academy, edX, Canvas, Duolingo, LinkedIn Learning and Pluralsight handle the same three states.
- `research_ux_best_practices.md` — accessibility rules for whole-card clickability, modal-vs-page tradeoffs, progress bar conventions, fallback states.
- `research_palette_mapping.md` — deterministic name→palette patterns (GitHub Linguist, Material 3, XEP-0392), hashing strategy, contrast on tinted backgrounds.


# Simplify learner dashboard

This section is a server-side cleanup of the existing `student_interface.home` view. It is independent of the card / icon / colour work above and could ship separately, but it lives in the same spec because the dashboard is where the new cards land.

## Rename Home → Dashboard

- Rename the URL **name** from `home` to `dashboard` in `freedom_ls/student_interface/urls.py`. The URL **path** stays at `/` — no bookmark or `LOGIN_REDIRECT_URL` churn.
- Rename the view function `home` → `dashboard` in `freedom_ls/student_interface/views.py`.
- Update every `{% url 'student_interface:home' %}` call site (currently `course_finish.html`).
- Update visible labels everywhere they appear in the student interface: page `<title>`, the "Return to Home" button on `course_finish.html`, and the "Home" breadcrumb on `course_topic.html` all become "Dashboard".

## Require login

- Add `@login_required` to the dashboard view. Anonymous users hitting `/` redirect to the login page and return after auth (`LOGIN_REDIRECT_URL = "/"` already points back here).
- Drop the anonymous `Welcome / login prompt` branch from `home.html` — it becomes dead code. The template only needs to handle the authenticated case.

## Drop the HTMX-on-load for courses

- Today `home.html` renders an empty `<div hx-get="…partial_list_courses" hx-trigger="load">` and the user sees a spinner before the course list paints. The data is computed in-process — there is no remote call or expensive op that justifies the round trip.
- Render the course list directly in the dashboard view: call the same helpers (`get_current_courses`, `get_completed_courses`, `get_recommended_courses`) and pass the context straight into the template. The course-list partials in `partials/course_list.html` can be reused unchanged.
- After this, the `partial_list_courses` view and its URL are unreferenced. The spec should decide whether to delete them (and the four `test_partial_list_courses_*` tests in `test_course_list_views.py`) or leave them as a public partial endpoint. Default: delete — dead code rots.
- If we ever measure a real perf problem here, HTMX can be reintroduced surgically. Don't pre-optimise.

## Out of scope (this section)

- A separate public marketing/landing page at `/`. Anonymous users get the login page; that's enough for now.
- Any change to `all_courses` (the `/courses/` page) or the other student-interface views.
