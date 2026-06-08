# Specification: Course-player visual fixes & header branding

## Context

The work was carried out directly in code (PR #118, "Course player visual
fixes"). This spec is reconstructed **retrospectively from the merged branch**
so the change has the same SDD paper-trail as every other feature; it is the
authoritative record of *what shipped and why*, not a forward-looking design.

The fixes group into eight coordinated changes spanning theme branding, header
and player layout alignment, an HTMX-boosted player navigation, a compact
button size, and a refresh of the course-outline (table of contents). All of
the configurable surfaces default to today's behaviour, so sites that do not
opt in are visually unchanged.

---

## 1. Configurable header branding (logo, favicon, title)

### Why

The header showed only the site name as plain text. To let a deployment brand
the chrome — the most-visible surface in FLS — without forking the template,
branding needs to be settings-driven, mirroring the existing
`EMAIL_LOGO_STATIC_PATH` precedent already used for email templates.

### What

Four new settings in `config/settings_base.py`, each defaulting to `None` (so
the out-of-the-box look is unchanged):

| Setting | Purpose |
| --- | --- |
| `HEADER_LOGO_STATIC_PATH` | static path to a header logo image, resolved via `{% static %}` |
| `FAVICON_STATIC_PATH` | static path to the favicon |
| `HEADER_TITLE` | overrides the header-bar title text; falls back to the site name |
| `HEADER_TITLE_STYLE` | inline CSS applied to the title (e.g. `font-style: italic;`) |

`site_aware_models.context_processors.site_config` exposes all four to every
template, deriving:

- `header_logo_static_path` / `favicon_static_path` straight from settings;
- `header_title` = `HEADER_TITLE` **or** `site_title` (which itself already
  falls back to the site name);
- `header_title_style` straight from settings.

`partials/header_bar.html` renders the logo `<img>` (with the title as its
`alt`) when a logo path is set, and applies the inline title style when set.
When a logo **is** present the `<h1>` title is hidden on small viewports
(`hidden sm:block`) so the header doesn't crowd on mobile; without a logo the
title shows at every breakpoint as before. `_base.html` renders a favicon
`<link rel="icon">` when `favicon_static_path` is set.

The development config (`config/settings_dev.py`) wires the **FirstClass**
brand for local QA: `HEADER_LOGO_STATIC_PATH` and `FAVICON_STATIC_PATH` both
point at the new `static/images/first_class_logo.png` asset added on this
branch, `HEADER_TITLE = "FirstClass"`, and `HEADER_TITLE_STYLE =
"font-style: italic;"`.

Covered by `site_aware_models/tests/test_context_processors.py` (branding
paths exposed, default to `None`, title override, title falls back to site
name).

---

## 2. Header & player layout alignment

### Why

The rebase left the header gutter and the course-player content header out of
alignment with the content column, producing an off-by-a-gutter look.

### What

- The `.header` component (`tailwind.components.css`) padding becomes
  `py-3 sm:py-4 px-4 sm:px-6 lg:px-8`, so the header's horizontal gutter
  matches the content gutter at every breakpoint.
- In `base/templates/_base_interface.html` the shared content header gains
  `max-w-7xl mx-auto` so the breadcrumb row sits in the same centred well as
  the content below it, and the main content column gains
  `id="interface-main"` — which doubles as the HTMX swap target in §3.

---

## 3. HTMX-boosted course-player navigation

### Why

Moving between topics/forms in the player triggered a full page load, with a
white flash and a re-paint of the whole page chrome. The navigation should
feel like a single-page app: swap only the content column and refresh the
sidebar outline, while keeping the URL, history, and document title correct.

### What

A new `c-player-nav` cotton wrapper
(`student_interface/templates/cotton/player-nav.html`) is the single source of
truth for the boost configuration. It carries:

- `hx-boost="true"` — boosts the descendant anchors/forms (Previous / Next /
  mark-complete / form controls), auto-pushing the URL so back/forward and
  bookmarking keep working, and updating the document `<title>` from the
  response;
- `hx-target="#interface-main"` + `hx-select="#interface-main"` +
  `hx-swap="outerHTML show:window:top"` — swap only the content column and
  scroll to top;
- `hx-select-oob="#course-toc-region"` — out-of-band swap of the sidebar
  outline so the current-item highlight and progress icons update without a
  reload.

It wraps **only** the navigation controls in `course_topic.html` and
`course_form.html` — never the rendered markdown content, whose links may
point off-site and must stay un-boosted.

The sidebar outline in `_course_base.html` is wrapped in
`<div id="course-toc-region">` (inside the existing `<dialog>` / side-panel
`x-data` ancestor, so the panel's open/scroll/Alpine state survives the swap)
to serve as the OOB target.

`base/static/base/js/interface-swap-fallback.js` guards the swap: it listens
for `htmx:beforeSwap` on `#interface-main` and, if the server response does
**not** contain `#interface-main` (e.g. a deadline-lock redirect to course
detail, or a session-expiry redirect to login), cancels the swap and performs
a full navigation so the user lands on the real page instead of a blank swap.
It is loaded **globally** from `_base.html` (not scoped to the interface
template) on purpose: with `hx-boost`, htmx does not execute `<script>` tags
in a swapped-in `<head>`, so the listener must already be present from the
current full page load regardless of which page the user navigated from. It is
a no-op (early-returns) on pages without `#interface-main`.

### Test consequence

Because "Start Form" / "Continue Form" are now boosted, the form-UI e2e tests
(`student_interface/tests/form_ui_tests.py`) wait on the pushed
`…/fill_form/…` URL (`page.wait_for_url("**/fill_form/**")`) rather than
`networkidle`, which can race the async swap.

---

## 4. Compact buttons via `c-button size="small"`

### Why

The player navigation buttons (and the image-lightbox trigger) were visually
heavy. A reusable small size keeps the button system DRY rather than
hand-rolling padding on individual call sites.

### What

`cotton/button.html` gains a `size` variable. When `size="small"` the rendered
class adds `btn-sm`; `tailwind.components.css` defines
`.btn-sm { @apply px-4 py-1.5 text-sm }`, declared **after** `.btn` so it wins
the cascade. (The non-dropdown branch was also simplified to compute its class
inline rather than via a nested `{% with %}`.)

Applied to every course-player nav button in `course_topic.html`, and the
image-lightbox **"Open image"** trigger in
`content_engine/templates/cotton/picture.html` — which is migrated from a
hand-rolled `<button class="btn btn-secondary …">` to a
`<c-button variant="secondary" size="small" icon_left="fullscreen">`, keeping
the markup DRY while preserving its keyboard accessibility and Alpine
`x-ref`/`@click` bindings.

---

## 5. Course-outline (TOC) redesign

### Why

The outline carried two separate icons per row — a content type-icon and a
trailing status icon — which was visually busy, and the expand affordance for
course parts was a small inline chevron rather than a full-row target.

### What

In `student_interface/templates/student_interface/partials/course_minimal_toc.html`:

- **Status is conveyed by colouring the content type-icon** rather than a
  separate trailing icon: `BLOCKED` → muted, `COMPLETE` → success, `FAILED` →
  error, `READY`/`IN_PROGRESS` → primary, else neutral muted. An `sr-only`
  status word ("Locked", "Not started", "In progress", "Completed", "Needs
  retry") is rendered alongside so assistive tech still announces status. The
  standalone `status-icon` partial is removed, and the trailing status icon is
  dropped from every row type.
- For an **expandable course part**, the **whole row** is the toggle
  `<button>` (`x-on:click="toggleExpanded"`, `x-bind:aria-expanded`), and the
  decorative expand/collapse chevron moves to the **right end** of the row —
  where the status icon used to sit. The chevron stays `aria-hidden` because
  state is conveyed by `aria-expanded`. The `is_expandable` branch inside the
  `content-row-inner` partial is collapsed accordingly, and the nested
  children `<ul>` drops its `border-l-2 border-border` rule for a cleaner
  look.

---

## 6. first_class theme polish

### Why

Two brand-specific refinements that should be scoped to `first_class` and
leave the default theme untouched.

### What

In `themes/first_class/static/themes/first_class/theme.css`:

- **Course-card accent grid lines** are made more prominent: the
  `--fls-course-accent-pattern` line opacity goes `0.07 → 0.16` and the cell
  size `2.5rem → 2rem` (denser, more visible grid).
- **Top-level outline counters** render zero-padded in the brand mono face —
  `01`, `02`, `03`… — via a CSS `counter` (`decimal-leading-zero`) on
  `nav[aria-label="Course outline"] > ul > li`, replacing the server-rendered
  `1.` index. Child counters (e.g. `3.1`) keep the server-rendered
  `parent.child` form unchanged. The shared template carries inert
  `.toc-counter` / `.toc-counter-top` / `.toc-counter-value` hooks so this
  treatment is **scoped to first_class** and the default theme keeps `1.` /
  `1.1`. These rules are deliberately plain CSS (not wrapped in `@layer`) so
  Tailwind emits them verbatim rather than tree-shaking them as candidate
  utilities.

---

## Out of scope

- No new themes are added; only `first_class` and the default theme exist.
- The default theme keeps `1.` / `1.1` counters and uncoloured type icons —
  the colour treatment and zero-padded counters are first_class-only.
- No auto-hide-on-scroll header behaviour.
- Branding is limited to the four header settings above (logo, favicon, title
  text, title style); no per-site logo upload, colour theming, or additional
  header slots.

---

## Success criteria

1. With `HEADER_LOGO_STATIC_PATH` / `FAVICON_STATIC_PATH` / `HEADER_TITLE` /
   `HEADER_TITLE_STYLE` set (as in dev), the header renders the logo, the
   browser tab shows the favicon, and the title shows the configured text and
   inline style; with all four unset, the header shows the site-name title and
   no logo/favicon — unchanged from before.
2. `header_title` falls back to the site name when `HEADER_TITLE` is unset
   (covered by `test_context_processors.py`).
3. The header's horizontal gutter and the course-player breadcrumb header line
   up with the content column at every breakpoint.
4. Navigating Previous / Next / Finish Course in the player swaps only the
   content column with **no full-page flash**, pushes the URL (back/forward and
   bookmarking work), and updates the document title.
5. The sidebar outline's current-item highlight and progress icons update via
   the OOB swap on each navigation, without a full reload, and the side panel's
   open/scroll state is preserved.
6. A boosted navigation that resolves to a page without `#interface-main`
   (deadline-lock or session-expiry redirect) falls back to a full navigation
   and lands on the real page, not a blank swap.
7. Boosted "Start Form" / "Continue Form" swap in the fill-form page and push a
   `…/fill_form/…` URL (the e2e tests wait on that URL).
8. `c-button size="small"` renders a compact (`btn-sm`) button; the player nav
   buttons and the "Open image" lightbox trigger are compact and still
   keyboard-accessible.
9. The outline conveys status by type-icon colour plus an `sr-only` status
   word, with no separate trailing status icon; for a course part the whole
   row toggles expand/collapse and the chevron sits at the row's right end.
10. In first_class, top-level outline counters read `01`, `02`, `03`… in the
    mono face while child counters stay `3.1`; the default theme keeps
    `1.` / `1.1`.
11. In first_class, the course-card accent grid lines are clearly more
    prominent than before; the default theme is unchanged.
12. The shipped tests pass: `test_context_processors.py` and the updated
    `form_ui_tests.py`.
