# Course Player

Rework the student course-reading experience into a focused two-pane **course
player**: a persistent left-hand Table of Contents (TOC) panel and the current
section's content on the right. Remove the intermediate course start page so
enrolled students go straight to the content, add breadcrumbs and per-section
page titles for orientation, and make the TOC behave well on phones.

This stays high-level on purpose. Research backing each decision lives in:
- `research_desktop_toc_sidebar.md`
- `research_mobile_bottom_sheet_nav.md`
- `research_breadcrumbs_resume_titles.md`

---

## 1. Remove the course start page

Today opening a course lands on a course-home / start page. Enrolled students
should skip it and go straight into the player.

- The bare course URL (e.g. `http://127.0.0.1:8000/courses/functionality-demo-show-end-with-topic/`)
  should no longer render the old start-page template.
- **For an enrolled student** it resolves to the right item in the player
  (`/courses/{slug}/{N}/`):
  - **No progress yet → the first item** (a true start).
  - **Has progress → the last-accessed item** (resume where you left off).
  - Because it always resolves to the student's *current* spot, the bare course
    URL stays a stable, bookmarkable "take me to where I am" entry point.
- **For a visitor who is not registered**, the player is off-limits. Nothing
  should link an unregistered user into the player. They belong on the existing
  **course preview page**, which is where the course description / overview /
  register call-to-action lives. (So the description does not need a new home —
  it stays on the preview page; for enrolled students the always-on outline is
  their overview.)
- Verify the **browser Back button** behaves sanely from the resolved item
  (no redirect loop back through the bare course URL).

---

## 2. Breadcrumbs

At the top of the main content area, show a breadcrumb trail:

```
{course title} > {course-part if there is one} > {title of current section}
```

![breadcrumb example](image-1.png)

- When the current section has no course-part, **drop that crumb** — don't show a
  dangling separator or pad the trail.
- The **current section is plain text, not a link** (and marked as the current
  location for assistive tech). Ancestor crumbs are links.
- Wrap in a breadcrumb navigation landmark; render the `>` separators as
  decoration (not real text) so screen readers don't announce them.
- Truncate an over-long course or section title gracefully rather than wrapping
  or breaking the layout.

---

## 3. Left-hand TOC panel

![TOC panel](image.png)

### Header (pinned to the top of the panel)

```
COURSE OUTLINE          ← small eyebrow label
{Course Title}
[####......] progress bar
{X}% complete           {N} / {M} mods
```

- The bar %, the `% complete`, and the `N / M` counter must all derive from the
  **same progress data** so they never disagree.

### Body (scrolls independently of the content)

- Show the table of contents. **Course parts are expandable** (collapse/expand
  disclosure controls), matching the style in the image above.
- Keep nesting to **two levels** (part → item); no third tier.
- **Highlight the current item** and auto-expand the part that contains it; keep
  it scrolled into view after navigation. Preserve any expand/collapse the
  student does manually during the session — don't reset it on every navigation.
- Per-item **status icons** (complete / current / not-started / locked / failed)
  must not rely on colour alone — pair with an icon and accessible text.
- The panel and the content area **scroll independently**.

---

## 4. Left-hand panel responsive behaviour

### Large screens (laptops)

- The TOC panel is **always open**. No option to close it.

![always-open panel](image.png)

### Phones

- The panel is **collapsed by default** (not expanded).
- It opens as a **bottom sheet that scrolls up from the bottom** — explicitly
  *not* a slide-in drawer from the side.

  ![bottom sheet on phone](image-2.png)

- Treat it as a **modal** sheet: a scrim dims the background, the background is
  inert while it's open, and it opens to a partial height (showing current
  context) with the TOC list scrolling **inside** the sheet.
- Provide **multiple dismiss routes with the same outcome**: a visible close
  (×) control, tapping the scrim, swiping the sheet down, the Escape key, and the
  device Back button. A drag handle is an affordance hint only — never the sole
  way to close.

> Implementation note: this differs from the side-drawer behaviour of the shared
> interface sidebar, so the course player likely needs its own mobile treatment
> rather than changing the shared component used elsewhere. The native `<dialog>`
> element is a strong, low-JS baseline (focus trapping, inertness, Escape,
> backdrop for free). Decide details at spec/plan time.

> Implementation note: the course player will need **several distinct kinds of
> modal**, presented differently depending on content. The mobile TOC bottom
> sheet is one kind; another is expanding a picture/diagram in the course player
> (e.g. tap-to-zoom a figure), which should present as a centred lightbox rather
> than a bottom sheet. These share common **background behaviour** — the scrim /
> background blur, inertness of the background, and dismiss routes (scrim tap,
> Escape, Back) — but differ in how the foreground content is laid out and
> animated. Plan for the shared scrim/blur/inertness behaviour to be **factored
> out and reused** across modal types, with each modal type supplying its own
> presentation. Decide details at spec/plan time.

### Compact header on phones (instead of full breadcrumbs)

Instead of the full breadcrumb trail, show a compact bar at the top of the
content:

![compact mobile header](image-3.png)

- Back arrow on the far left.
- A condensed trail (e.g. `RPAS · M3 · Pre-flight`) — keep the course root and
  the current section, abbreviating/eliding the middle if space is tight.
- A **clearly labelled TOC toggle** button on the right that opens the bottom
  sheet (an obvious control, not a bare hamburger).
- A thin progress bar with a `%`.
- (The bookmark icon shown in the mockup is **out of scope** — omit it.)

---

## 5. Page title

The browser page `<title>` should reflect the current section of the course.

- Order **most-specific first**: `{Section} — {Course} — {Site}`. Drop the
  course-part (if any) before dropping the section, and the site/brand can be
  trimmed first if length is a concern.
- If sections ever swap without a full page load, the title must still update on
  navigation.

---

## Out of scope

- **Bookmarking** sections (the bookmark icon in the mobile mockup is decoration).
- Reworking the shared interface sidebar used by other parts of the app.
