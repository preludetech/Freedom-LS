# Research: UX patterns for the educator course details page and content preview modal

Topic: `ux_patterns`. Scope: a course details page in the educator interface (course details plus table of contents), with a Preview button per TOC item that opens a modal showing that item as a learner sees it.

Sources are marked **[project]** (rules in this repo, binding) or **[web]** (external prior art, advisory). Where they disagree, project rules win.

## 1. Project rules the design must conform to

### 1.1 Panel framework (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`)
- The educator page is built from panel-framework pieces. A course is a record, so the natural shape is an `ObjectViewConfig` / `InstanceView` page. Its header is `<c-panel-page-header>`, and its details sit in `InstanceDetailsPanel`, `<c-panel-definition-list>` or `<c-panel-card>`. The TOC could be a custom panel.
- Page header: states each fact once. A badge only for a non-default state (for example Draft or Coming soon). No action in the header. Stats stay out if a tab or panel already shows them. The learner counts (for example "12 lessons") should appear once, not in both the header and the TOC.
- Triggers: every action trigger is `size="small"` (`<c-modal-trigger>` included). Per-row buttons sit inside `<c-data-table-actions>`, which owns the gap, with no margins on the buttons. On a phone, a button is 44px tall and as wide as its label.
- Two buttons in one row never share a bare verb. If a row has more than one action, name the noun ("Preview topic", "Preview form"). A single Preview button per row is fine, but give it an `aria-label` that includes the item title ("Preview Intro to Python"), because many identical "Preview" buttons are ambiguous to screen readers.
- Controls are components. Every anchor in educator templates is a control: it takes `no-underline text-on-surface` (or `text-muted`) for a clickable row. A Preview that is a link rather than a button needs the right component. `test_no_control_link_is_hand_styled` and `test_every_anchor_with_visible_text_carries_its_own_classes` fail on a forgotten anchor.
- Modal versus quick view:
  - `#app-modal` (the shared native `<dialog>`, loaded by `<c-modal-trigger>`) dims and blocks the page. It is the modal.
  - `#quick-view` opens with `show()`, no scrim, and the page behind stays tappable. It is for a list row's summary drawer.
  - The request is explicitly a "modal", so `#app-modal` is the match. A drawer is not what was asked for.
- Dialog chrome:
  - `<c-modal-header>` holds the title and a close control (`aria-label="Close"`, `<c-icon name="close">`).
  - The dialog ends in `<c-modal-footer>`: Cancel in the `cancel` slot at the left, actions at the right, primary last.
  - A read-only preview has no decision to confirm, so the footer should carry only the Close and any previous/next controls. Check that the footer slots allow this, and that the invariant `test_every_dialog_ends_in_the_modal_footer_not_a_button_group` is still met.
- Width: `#app-modal` is `min(92vw, 32rem)` (about 512px) from `sm` up. Below `sm` it is a bottom sheet: full width, `max-height: 85dvh`, rounded top corners, 200ms slide-up, with reduced motion respected. Learner content (rendered Markdown, forms) in 32rem is cramped. The spec must decide whether to add a wider variant of the shared modal (for example a size modifier), because this is the only place a large modal is needed. The default `#app-modal` should not be widened for all other dialogs.
- Overflow: the modal host clips horizontal overflow and the title wraps, so it stays inside the viewport at 375px. Learner content (wide tables, code blocks) must scroll or clip inside the modal body rather than pushing the dialog wider.
- Empty states use `<c-panel-empty-state>`. A course with no TOC items needs one ("No content yet" with a hint, in the project's voice).

### 1.2 Brand visual and voice (`.claude/skills/brand-guidelines/visual.md`, `voice.md`)
- Headings, body, lists and tables take no classes; the base layer styles them. Use `<c-page width="wide|narrow">`. Cards are `.surface` or `<c-panel-card>`. A callout in a page is `<c-callout level="info" title="…">`.
- Status and labels:
  - A record's state is a `<c-panel-status-badge tone=…>`.
  - A label that is not a status (item type, "Preview") is a `<c-chip variant="…" size="xs">`.
  - "Preview" is a mode and not a record state, so a chip is right. A status badge is not.
- Colour comes only from role tokens: no raw hex, and no `bg-midnight`-style brand names. `test_no_panel_component_uses_raw_colours` enforces this in panel components.
- Principle 4 is progressive disclosure: essentials by default and detail on demand. This supports collapsed course parts in the TOC and preview-on-demand.
- Principle 2 is obvious over clever: "If it's clickable, it looks clickable." The Preview control should be a visible button, not a hover-only reveal.
- Button labels fit on one line down to 375px. Use "Preview" (a verb), and keep counts and sentences out of the label.
- A long list inside a block scrolls in its own region (`max-h-96 overflow-y-auto`, focusable, `role="region"`, `aria-label`) when it can hold more than about ten rows. A big course TOC is likely over that, but a page-level TOC probably is the page's main content and should not be capped. This needs a deliberate decision, and the likely answer is no cap since the TOC is the primary content. Keep the tension in the spec.
- Placement: a control sits beside the thing it changes. Preview sits on each TOC row.
- Voice: direct, no SaaS words. Use "learners", not "students"; "content", not "curriculum". Section headings are "Course content" or "Contents" (the learner page uses "Course content"). Dates use the `3 Nov 2026` format. Examples of good copy:
  - Banner: "Previewing as a learner sees it. Nothing you do here is saved."
  - Empty: "No content in this course yet."
  - Avoid: "Experience your content like a learner!"
- A disabled action shows its reason beside it, wired with `aria-describedby`. If any item cannot be previewed (for example an item type that is unsupported), the Preview button is disabled with a visible reason and not hidden silently.

### 1.3 Icons (`claude_plugins/fls-dev/skills/icon-usage/SKILL.md`, `freedom_ls/icons/semantic_names.py`)
- All icons go through `<c-icon name="…">` using semantic names. No raw SVG, Font Awesome or Unicode glyphs. `class` replaces the default `size-5`, so always pass a size.
- Semantic names that already exist and fit this work:
  - Content types: `topic`, `form`, `folder` (the learner TOC uses `folder` for a course part).
  - Disclosure: `expand`, `collapse`. The learner TOC shows both with Alpine `x-show` on wrapper spans.
  - Modal navigation: `previous`, `next`, `close`.
  - Preview and open: `quick_view`, `open_page`, `fullscreen`. `quick_view` is the likeliest fit for a preview trigger, and it is probably already used for the quick view. The spec should check how `quick_view` is rendered and reuse it. If a distinct "eye"-style glyph is wanted, add a new semantic name (see `resources/configuring-icons.md`), do not use a raw glyph.
  - Meta: `deadline` (duration or time limit), `achievement` (level), `course`, `notes`.
- Sizes: `size-4` in lists and small UI, `size-5` in buttons, `size-6` for modal close.
- Accessibility: an icon is decorative by default. An icon-only button puts `aria-label` on the control, not the icon. A type icon that is the only carrier of meaning needs `aria_label`, or a visible type label or `sr-only` text beside it. The learner TOC uses `sr-only` status text.

## 2. How the learner side looks today (the educator TOC could mirror it)

Files: `freedom_ls/learner_interface/templates/learner_interface/course_detail.html` and `.../partials/course_minimal_toc.html`.

- Learner course detail page: back link, then a full-bleed hero (accent gradient, large faded course icon, organisation byline, category chip, H1 title, subtitle). A glass stats strip follows with cells for Lessons, Level, Duration, Time limit, Price and Enrolment, each rendered only when present. Below that is a two-column grid: a sticky sign-up panel (CTA, "This course includes") and the main column with "About this course" (rendered Markdown), "What you'll learn" (checkmark list) and "Course content" (the TOC).
- Learner TOC (`course-children` partialdef): `<nav aria-label="Course outline">` containing a `<ul>`.
  - Top-level rows show a counter ("1."), a type icon (`topic`, `form`, `folder`) coloured by status, and a truncated title.
  - A course part is a full-width `<button>` row with `aria-expanded`, a chevron (`expand`/`collapse`) at the right end, and an Alpine `coursePart` component that persists open or closed state in `localStorage` through `data-storage-key`. A part that contains the current item auto-expands. Nested items sit in a `ul` with `ml-6`, using `x-collapse`, and have counters like "1.2" in `text-xs`. An empty part shows "No items in this part" (italic, muted).
  - Titles are links to the learner URL, except course parts (muted text) and the current item (`aria-current="page"`, semibold).
  - The learner TOC has no per-row duration or counts. Its status colours come from learner progress.
- Reuse versus fork:
  - The educator TOC should mirror the shape: counters, icon plus title, collapsible parts, and the same `topic` / `form` / `folder` icons, so an educator recognises what a learner sees.
  - It must drop the learner-specific parts: progress status colours and sr-only statuses, "current item" highlighting, deadlines and "Closed" chips, and links to learner URLs.
  - It must add what the educator needs: an item type label, and the Preview button on each row.
  - The learner partial is hard-wired to `child.status` / `child.url` / `child.is_current`. Reuse by an include would drag in learner semantics, so a separate educator partial that follows the same markup conventions is likely cleaner. Extracting a shared presentational partial is an option the plan should weigh, given the project's "avoid repeating code" rule.
- The learner page has a hero and glass strip that are brand-heavy. The educator page should instead follow the panel-framework page header and definition list conventions. The educator interface is utilitarian, and the brand rule is "content first, chrome second".

## 3. Web prior art

### 3.1 Course overview and curriculum pages for instructors
- Pattern: a metadata header (title, subtitle, state, counts, duration, level), then the outline as the main body.
  - Open edX Studio: its Course Outline is a hierarchy (section > subsection > unit) with a collapse/expand-all control and per-row actions. Source: https://docs.openedx.org/en/ulmo/educators/references/roles_for_viewing.html
  - The pattern is common across Moodle, Canvas Modules and LearnDash. Disclosure is collapsible parts with the first or only part open by default. Rows use a type icon plus a title, and a trailing area for meta (duration, status) and row actions.
- Counts and durations are shown as quiet muted meta text on the row (`text-sm text-muted`, `tabular-nums` for figures, per this project's list-record rules), plus an aggregate in the header (for example "24 lessons"). Per-part counts ("5 items") sit on the part row. These are external conventions, and I did not fetch one authoritative source for them.
- An "expand all / collapse all" control is a common convenience once a course has more than a handful of parts. It is optional here. Without a real need, the project rule "don't build functionality not explicitly requested" applies, and a long course is the only argument for it.
- Item type must not be conveyed by icon alone: add a text label or `sr-only` text (matches the project icon rules).

### 3.2 Preview affordances (LMS prior art)
- Open edX: preview is launched from the outline, and it separates "preview" (draft content, ignoring release dates) from "live" (what an enrolled learner sees). Source: https://docs.openedx.org/en/ulmo/educators/references/roles_for_viewing.html and https://docs.openedx.org/en/open-release-sumac.master/educators/references/testing_course_content.html
- Schoox: preview opens with a modal notice that the user is previewing and no progress will be recorded. Preview bypasses the restrictions a learner would see. Source: https://sigmasupport.schoox.com/hc/en-us/articles/29840422846231-Course-Learning-Path-Preview-Functionality-Improvements
- Sage Vantage: a message at the top left of the page indicates preview mode. Source: https://vantagesolutions.sagepub.com/support/solutions/articles/7000089082-what-is-the-student-view-
- Masteriyo: a floating bottom-centre pill, "Viewing as Demo Student", with a "Switch to Admin" exit control. Source: https://docs.masteriyo.com/course-creation/demo-student-preview
- TalentLMS: warns that entering preview resets your progress; there is an exit back to instructor view. Source: https://help.talentlms.com/hc/en-us/articles/16512734888476-How-to-preview-course-content-in-TalentLMS
- Absorb: its preview uses the same player as the learner side, so results match. Source: https://ideas.absorblms.com/ideas/LMS-I-33
- Synthesis: a persistent "this is a preview" indicator, a statement about what is not recorded, and a clear way out are the consistent points. No source describes an outline inside the preview modal; previous/next within a modal is general carousel/lightbox practice, not LMS-specific.

### 3.3 Per-row preview affordance options
| Option | For | Against |
|---|---|---|
| Visible "Preview" small button per row (icon plus text, or icon only with `aria-label`) | Obvious over clever (brand rule); clear on touch; matches the request ("a preview button for each TOC item") | Adds visual weight on long TOCs, so use a quiet variant (secondary or ghost, small) |
| Icon-only eye or `quick_view` button | Compact | Ambiguous without a label; needs a tooltip and `aria-label`; a 44px target on phones |
| Whole row clickable | Large target | Conflicts with the course part toggle (row click = expand); hidden affordance; panel-framework permits a clickable row only styled as a row link |
| Hover-only reveal | Clean | Fails on touch and breaks the "looks clickable" rule |

Recommended direction (for the spec to confirm): a visible small button on item rows. Course parts toggle on row click and carry no Preview, unless a part preview is wanted (the idea says "each TOC item", so this needs a decision). Buttons are `<c-modal-trigger size="small">` with `aria-label="Preview <title>"`, and they sit in the row's trailing area.

### 3.4 Content-preview modal
- Size: desktop wants a wide, tall dialog (about 48-64rem, up to 90dvh) because learner content is prose, code and forms. The shared `#app-modal` at 32rem is too narrow, so a size variant is needed (see 1.1).
- Header: item title (wraps), a type chip ("Topic" or "Form"), and the close button at the right. The `<c-modal-header>` supplies title and close.
- Scrolling: body scrolls inside the dialog, header (and footer navigation) stay pinned. The page behind does not scroll (`html:has(#app-modal:modal) { overflow: hidden }` already).
- Previous/next:
  - Place it in the modal footer, for example "Previous" at the left and "Next" at the right, with `previous` and `next` icons and the neighbour's title as secondary text.
  - Order follows the TOC order across parts. Disable (with a visible reason, `aria-describedby`) or hide at the ends. The project rule favours disabled with a reason.
  - It is optional: the idea doesn't ask for it, so the "don't build what isn't requested" rule applies. It is cheap to add if the modal content is loaded by HTMX from a URL per item, since "next" is the next item's URL.
  - Moving between items must keep focus management intact: focus to the dialog title on swap, and announce the new title through the existing `#app-modal-status` live region.
- Keyboard and accessibility:
  - A native `<dialog>` with `showModal()` traps focus, closes on Esc, and returns focus to the trigger.
  - Title is linked through `aria-labelledby="app-modal-title"`.
  - Arrow-key previous/next shortcuts are not a standard and would conflict with in-content controls, so avoid them.
- Preview indicator inside the modal (this is the strongest cross-LMS pattern):
  - A `<c-callout level="info">` or a strip at the top of the modal body: "Preview. This is how a learner sees this item. Nothing you do here is saved." Persistent, not dismissible.
  - Do not use a dismissible toast. Do not rely on colour alone: text plus an `info` icon.
  - Optionally a `Preview` chip in the header beside the type chip.
- Read-only forms:
  - Native `disabled` controls are dropped from the tab order and have low contrast. Prefer `fieldset disabled` around the form body so nothing can be submitted, or render the learner form template with a preview flag that removes the submit button.
  - Keep the form legible: contrast of disabled text is a known issue. Consider `aria-disabled` plus `readonly`, or an `inert` wrapper with normal styling. The mechanism is a technical question for the spec/plan.
  - Submit buttons are removed or disabled with a visible reason: "Submitting is turned off in preview." Nothing may write learner progress.
- Links inside previewed content (to other topics, next-activity buttons, "Mark complete") should be neutralised or disabled in preview. Otherwise the educator navigates away from the page or creates progress. The spec should list which learner controls (complete button, next/previous player nav, breadcrumbs) are omitted. The learner `player-nav.html` and `player-footer.html` are the likely sources of these controls.
- Reuse the learner rendering (Absorb's "same player" idea) so the preview matches what learners see; chrome (player nav, progress, breadcrumbs) is stripped out.

### 3.5 Mobile behaviour
- The project already defines it: below `sm` (640px) `#app-modal` becomes a bottom sheet with rounded top corners, `max-height: 85dvh`, a slide-up transition, and a header with close. Panel-framework rule: "Every sheet and dialog shares one chrome." A learner-content preview on a 375px phone is cramped at 85dvh, but the framework rule says sheets rise from the bottom. A full-screen variant (100dvh, no rounded corners) for the preview modal is a deliberate deviation. The spec must say whether to accept the standard bottom sheet (consistent, framework-compliant) or define a full-height preview variant (more room, but a new chrome pattern needing a rule and an invariant test). Default recommendation: bottom sheet, with a raised max-height for the preview variant (for example 92-95dvh) if the shared mechanism allows it, so as to stay inside the framework's chrome.
- The Preview button is 44px tall and as wide as its label on phones (framework rule). Icon-only buttons still reach 44px height.
- The TOC row on a phone: counter, icon, title (truncate, or wrap for the educator since truncated titles hide which item is previewed) and the Preview button. At 375px, put the button at the end of the row and let the title wrap rather than truncate. Part counts and durations drop under the title (as the learner page puts deadlines on their own line) and not beside it.
- The prev/next footer buttons: labels short ("Previous", "Next") so each fits on one line at 375px, with the neighbour title omitted on phones.
- Page-level: the details panel goes above the TOC on phones, in one column, then side by side from `lg` if a two-column layout is used. The learner page puts its CTA first on mobile for the same reason.

## 4. Suggested page structure (for the spec to adopt or adjust)

1. Breadcrumbs / `<c-back-link>` to the course list. Check which one the educator pages use (the learner page notes the framework breadcrumbs partial navigates by HTMX into `#main-content`).
2. `<c-panel-page-header>`: course title; badge only if the state is non-default.
3. Course details panel: `<c-panel-definition-list>` of subtitle, category, level, duration, time limit, price, and so on (render a row only when it has a value, like the learner stats strip); the rendered course description if wanted. Counts (lessons, forms) shown once.
4. "Course content" panel: nested TOC, with parts collapsible (open by default for a short course; do not copy the learner `localStorage` persistence unless asked), each item row showing the counter, the type icon, the title, the type chip and the Preview button.
5. Preview in `#app-modal` (wide variant), opened by `<c-modal-trigger>`, content loaded by HTMX from a per-item preview URL, with the preview callout at the top and, if included, previous/next in the footer.
6. Empty states via `<c-panel-empty-state>`.

## 5. Open questions the spec must answer
1. Which item kinds are previewable (topics, forms; activities and course parts)? What do parts do on click (toggle only)?
2. Modal width on desktop: a new size modifier on the shared dialog, or a dedicated dialog host?
3. Mobile: standard bottom sheet, or a full-height variant (needs a panel-framework rule and an invariant test)?
4. Previous/next: in scope or not (it wasn't requested)?
5. How are form controls made inert (fieldset disabled, `inert`, or a preview flag in the form template)? Which learner controls are removed (complete, next, breadcrumbs)?
6. Does the preview write anything (progress, attempts, view logs)? It should not.
7. Preview trigger icon: reuse `quick_view`, or add a new semantic name?
8. Share a TOC partial with the learner side, or create an educator partial following the same markup?
9. Is there a cap on TOC height for very large courses, or does the page just grow?
10. The spec/plan must note that the panel-framework skill gets a new rule for any new modal size or chrome, with an invariant test, per the project's "documentation is source of truth" rule.

## References
Project: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, `claude_plugins/fls-dev/skills/icon-usage/SKILL.md`, `.claude/skills/brand-guidelines/visual.md`, `.claude/skills/brand-guidelines/voice.md`, `freedom_ls/panel_framework/templates/panel_framework/partials/modal_host.html`, `freedom_ls/icons/semantic_names.py`, `freedom_ls/learner_interface/templates/learner_interface/course_detail.html`, `freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html`, `freedom_ls/learner_interface/templates/learner_interface/partials/course_toc_header.html`.

Web (from a single search; I read only the search summaries and did not open the pages):
- https://docs.openedx.org/en/ulmo/educators/references/roles_for_viewing.html
- https://docs.openedx.org/en/open-release-sumac.master/educators/references/testing_course_content.html
- https://sigmasupport.schoox.com/hc/en-us/articles/29840422846231-Course-Learning-Path-Preview-Functionality-Improvements
- https://vantagesolutions.sagepub.com/support/solutions/articles/7000089082-what-is-the-student-view-
- https://docs.masteriyo.com/course-creation/demo-student-preview
- https://help.talentlms.com/hc/en-us/articles/16512734888476-How-to-preview-course-content-in-TalentLMS
- https://ideas.absorblms.com/ideas/LMS-I-33

Caveat: sections 3.1 (outline conventions), 3.4 (modal sizing, prev/next, read-only forms) and 3.5 are drawn from general UX practice and not from fetched pages.

status: ok
