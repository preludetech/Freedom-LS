# Research: shell, sidebar navigation, mobile nav and drawer/modal slots

Evidence for the idea's three open questions. Does not decide them.

(a) Does `_base_interface.html` / `sidePanel` need to change, given the learner course player extends the same shell?
(b) Add the mobile bottom tab bar the mockups show, or keep the sidebar sheet (default no)?
(c) Reserve layout slots now for the quick view drawer and modal host that spec 3 adds?

## 1. The shell as it stands today

### `_base_interface.html` (`freedom_ls/base/templates/_base_interface.html`)

Extends `_base.html` and defines the blocks every consumer overrides:

- `sidebar_storage_key` — localStorage key for open/closed persistence (defaults `"sidebar"`; educator interface sets `"sidebar-educator"`, course player sets `"sidebar-course-toc"`).
- `sidebar_class` — extra classes on the `.side-panel-grid` wrapper (course player uses it to widen the desktop column to `20rem` via `[--sidebar-width:20rem]`).
- `sidebar_presentation` — `bottom-sheet` (default) or `side-drawer`, set as `data-variant` on the `<dialog>`; controls the mobile-only slide direction (bottom sheet slides up, side drawer slides from the left). Neither current consumer overrides this — both use the default bottom-sheet.
- `sidebar_heading_aria`, `panel_toggle_label`, `sidebar_body_top_pad` — accessibility/label text.
- `sidebar_content` — the actual sidebar markup slot. Educator interface fills it with the organisation switcher partial then `sidebar_nav.html`; the course player fills it with the course TOC header and tree.
- `breadcrumbs`, `header_extra`, `page_title` — content-header slots above `{% block content %}`.
- `content` — the main content area, inside `<div id="interface-main">`.
- `footer` — compact footer bar.

Structurally the shell is one `x-data="sidePanel"` wrapper containing a CSS grid (`.side-panel-grid`, two columns `var(--sidebar-width, 16rem) minmax(0, 1fr)` at `lg+`, one column below) with two children: a single `<dialog x-ref="panelDialog">` (the sidebar, docked on desktop via `dialog.show()`, a modal overlay below `lg` via `dialog.showModal()`) and `<div id="interface-main">` holding the header and `{% block content %}`. There is **no third grid column and no reserved slot** for anything else — no quick-view drawer, no modal host. Any drawer or modal added today would either have to be its own dialog placed outside this grid (as siblings after `</div>` closing the grid) or would need the grid itself extended.

### `sidePanel` (`freedom_ls/base/static/base/js/alpine-components.js`)

One Alpine component drives every sidebar in the app (learner course TOC, educator nav, panel-framework test harness). Key behaviour: `show()`/non-modal + `showModal()` toggle by breakpoint (`matchMedia("(min-width: 1024px)")`), desktop state persisted per `data-storage-key` in `localStorage`, mobile modal pushes one `history` entry so device Back closes the sheet, `htmx:beforeRequest` on the dialog closes the mobile sheet before an in-sheet navigation completes (so Back does not show the sheet reopened over the wrong page), and a `_desktopLock` mode (used by the course player) pins the panel permanently open on desktop with no toggle. The `research_current_structure.md` in this directory documents the same file's coupling in more detail — this note does not repeat it.

**Who extends the shell:** `freedom_ls/educator_interface/templates/educator_interface/interface.html` and `freedom_ls/learner_interface/templates/learner_interface/_course_base.html` are the only two direct consumers found in the codebase (confirmed by grep across `freedom_ls/`). Both inherit the same grid, the same `sidePanel` component and the same CSS in `_base_interface.html`'s `<style>` block. Any change to the grid, the dialog markup, or the component's public behaviour is a change both interfaces get; the idea's own text is accurate that a shell change is a change to both, and the course player is the one to smoke-test if the shell changes.

### `sidebar_nav.html` (`freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html`)

Renders `menu_items` as a flat `<ul>` — **no section headings, no grouping, no item counts today**. Built by `_build_menu_items()` in `freedom_ls/panel_framework/views.py` (confirmed by `freedom_ls/panel_framework/tests/test_menu_items.py`), which iterates a flat `dict[str, type[ListViewConfig]]` and returns one dict per item: `label`, `url`, `active`, `expanded`, `instance_label`, `instance_url`. Each `<li>` is an `x-data="sidebarMenuItem"` disclosure: a top-level link plus, if the section has a "currently viewed instance" (e.g. Cohorts → the cohort you're looking at), one expandable child `<li>` showing that instance's label with `aria-current="page"`. There is no data field for a count badge and no wrapping structure for a section heading — `idea.md`'s "settled" text ("Sidebar links group into sections with headings and optional counts") is new work this spec adds, not something already present. The whole `<nav>` is OOB-swapped (`hx-swap-oob="true"` when `oob` is truthy) on every htmx navigation so `active`/`expanded` stay in sync.

### `list_view.html` and `main_content.html`

`panel_framework/partials/main_content.html` is a one-line wrapper (`<div id="main-content">{{ content|safe }}</div>`) — the htmx swap target for all `main-content`-targeted navigation, fed pre-rendered HTML strings from `views.py` (per `idea.md`'s complaint that panels currently return HTML strings assembled in Python). `educator_interface/partials/list_view.html` and `panel_framework/partials/list_view.html` were not read in full for this note (out of scope for shell/nav) but both live under the same `#main-content` swap target, so a quick-view or modal host placed as a **sibling of `#main-content`** (outside the swap target, inside or after the grid) survives every in-app navigation; one placed inside `#main-content` does not (this exact point is also flagged in the drawer/modal research, section 5 below).

### Organisation switcher (`educator_interface/partials/organisation_switcher.html`)

Renders above `sidebar_nav.html` inside `sidebar_content`, per `idea.md`'s framing ("the host slots its own content above the nav, as the organisation switcher does now"). A `c-dropdown-menu` when more than one organisation is accessible, else static text. No footer/user area or settings item exists in the current shell — the mockup's sidebar footer (user avatar/name/role/settings icon) has no counterpart in the codebase today.

### Learner course player shell (`learner_interface/_course_base.html`)

Uses `_desktopLock="true"` (via `data-desktop-lock`) so the outline can never be closed on desktop, widens the sidebar column to `20rem`, and renders the course TOC inline (not via `hx-get`) so the "current item" highlight is present on first paint. It overrides `header_extra` to show a mobile-only progress bar under the breadcrumbs. This is the second, and only other, direct consumer of the shell and its component — it has no organisation switcher, no `sidebar_nav.html` include, and no dependency on `_build_menu_items()`.

## 2. What the mockups show

Source: `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/`. Read `Sidebar.dc.html` in full; grepped/read `Educator Dashboard.dc.html`, `Educator Mobile Dashboard.dc.html`, `Educator Learners.dc.html` and `Educator Mobile Learners.dc.html` for the elements the idea asks about. Ignoring what `spec-order.md`'s assumptions rule out (custom roles/"create role", messaging, "reset attempt", certificates, schedule, compliance, "this week").

### `Sidebar.dc.html` — desktop sidebar structure

Fixed 264px column, top to bottom:

1. **Brand header** (64px): logo mark, product name — not relevant to FLS (FLS uses its own theme header, not shown here).
2. **Organisation switcher**: an `Organization` overline label, then a bordered row with an org initials avatar, org name (truncated), and a caret-updown icon — a dropdown trigger, matching what `organisation_switcher.html` already does today (avatar chip is new; FLS's version is text/icon only).
3. **Two labelled sections**, each an overline heading followed by nav rows:
   - **Teaching**: Dashboard (no count), Cohorts (count "12"), Learners (count "284"), Courses (count "9").
   - **Administration**: Educators (count "16"), Roles & permissions (no count), Organization settings (no count).
   Each row: icon, label (`flex:1`), and a right-aligned monospace count badge when present. The active row gets a tinted background, a left inset "active" bar (`box-shadow: inset 2px 0 0 var(--color-primary)`), bold label and tinted icon — active-state styling FLS's `sidebar_nav.html` already does with its `aria-[current=page]` Tailwind variant, just without the count badge or the section-heading grouping.
4. **Footer/user area**, pinned to the bottom (`margin-top:auto`) with a top border: user avatar-initials chip, name, role/title ("Lead instructor"), and a trailing gear icon. FLS's shell has no equivalent element today.

Two grouped sections is the mockup's whole vocabulary — no third "more" or "settings" group, no nesting beyond the two headings, no per-item disclosure/expand affordance shown (unlike FLS's current sidebar, which expands to show the viewed instance under its section).

### `Educator Dashboard.dc.html` — desktop page layout (1440px frame)

The sidebar is imported as a shared component (`<dc-import name="Sidebar" active="Dashboard">`) sitting flush against the main content, i.e. sidebar and content are **flex siblings in one row**, not a floating overlay — matching FLS's own `.side-panel-grid` approach (grid columns rather than flex, but the same "docked column, not overlay" idea). Main content: a top bar (greeting, search box, bell icon — out of scope per spec-order.md's assumptions on notifications/search not being named in-scope here, noted only as present in the mockup), then a 4-column KPI stat-tile grid, then a two-column content area (`1.35fr` learner list / `1fr` sidebar-style cards for course progress and an agenda-style list).

On the `Educator Learners.dc.html` screen (skimmed, not exhaustively read), the same three-region idea appears with the third region **replaced by a quick-view panel**: sidebar (264px) | table (`flex:1`) | quick view (`width:380px` or `420px` depending on state, `border-left`, flex-column). The quick view sits **in-flow as a third flex column**, not as a floating overlay — see section 5.

### `Educator Mobile Dashboard.dc.html` — mobile navigation

Two things, both explicit and both germane to question (b):

- **M01 Dashboard**: the mockup screen literally states "The left navigation panel becomes a drawer plus a **four-item tab bar**" and renders a bottom bar with icon + 11px label pairs: **Dashboard, Cohorts, Learners, "More"** (a "…" / dots-in-circle icon, not a fifth real destination — it is an overflow trigger). The active tab is tinted primary; inactive tabs are muted grey.
- **M02 Navigation drawer**: a separate screen shows the *same* content as the desktop sidebar (organisation switcher, "Teaching"/"Administration" sections with counts) as a full-height drawer, i.e. the mockup keeps the sidebar-as-sheet pattern **in addition to** the bottom tab bar, reachable via the "More" tab or a menu icon — the two are not exclusive alternatives in the mockup, the tab bar is a shortcut layered on top of the same sheet.

`Educator Mobile Learners.dc.html` confirms the pattern is consistent: the same bottom tab bar (Dashboard / Cohorts / Learners / More) recurs on a second mobile screen, with Learners as the active/highlighted tab, and adds an M06 "quick view — snapshot sheet" screen (the drawer's mobile form, see section 5) plus a "sort & filter" bottom sheet for the table.

### Where FLS structurally differs already

FLS's current sidebar is a single flat list, already collapsible into a mobile sheet via `sidePanel`, with a "current instance" disclosure the mockup does not show at all (the mockup's sidebar never expands to show "Cohort X" nested under "Cohorts" — a `Cohorts` count of 12 stands in for that). The mockup also has no permission-per-row concept, no "current instance" disclosure, and a `Cohorts` count badge that FLS's config-driven `menu_label` items would need a new data field to populate (the `Panel` framework's `has_permission(request)` hook the idea settles could plausibly gate item visibility, but nothing today computes a live count per section).

## 3. Gap table

| Mockup element | Current shell/nav state | Kind of change |
|---|---|---|
| Sidebar grouped into labelled sections ("Teaching", "Administration") | `sidebar_nav.html` renders one flat `<ul>`, no headings | panel-framework/educator-interface (`_build_menu_items()`, `sidebar_nav.html`) — `idea.md` already settles this as new framework work, not a shell change |
| Per-item count badge (e.g. "Cohorts · 12") | No count field on menu items | panel-framework/educator-interface — new data on `ListViewConfig`/`_build_menu_items()`, template addition to `sidebar_nav.html` |
| Organisation switcher with avatar-initial chip | Existing switcher has no avatar chip, text/dropdown only | educator-interface (template-only; shell's `sidebar_content` slot already hosts it, no shell change needed) |
| Sidebar footer: user avatar, name, role, settings gear | No footer/user area in `_base_interface.html` or educator interface today | **shell** if the footer should be common to every consumer of `_base_interface.html` (course player has no equivalent need); otherwise educator-interface-only if added inside its own `sidebar_content` block, which needs no shell change since that block already exists |
| Desktop docked sidebar as first grid/flex column | Already true: `.side-panel-grid` two-column layout, `sidePanel` `show()` | no change — shell already matches |
| Mobile sidebar as a bottom sheet / drawer | Already true: `sidebar-presentation` default `bottom-sheet`; mockup's M02 drawer screen is compatible with either `bottom-sheet` or `side-drawer` variant, both already supported | no change — shell already matches |
| Mobile four-item bottom tab bar | Not present anywhere in FLS today | **shell**, if added — a new persistent, fixed element outside the existing `sidePanel` grid, present on every screen regardless of sidebar-sheet open/closed state; would need its own reserved region in `_base_interface.html`. Idea.md already frames this correctly: "If yes, it is a shell change and belongs here [spec 1], not in a later spec." |
| Desktop right-hand quick view (380–420px, in-flow, `border-left`) | No third region/column in `.side-panel-grid` or the flex row it wraps | **shell**, if reserved now — needs either a third grid-template-column or a sibling flex/grid region next to `#interface-main`; per idea.md, "probably one block each in the interface template" |
| Modal host (shared `<dialog>` overlay) | No modal host in `_base_interface.html` (only the sidebar's own `<dialog>`); `cotton/modal.html` is currently instantiated per-use inside page content, not shared | **shell**, if reserved now — the modal-drawer research (section 5) explicitly recommends "one shared host in the layout", i.e., a `_base_interface.html` block, not a per-page element |
| Mobile quick view as a bottom sheet | No quick-view component exists yet at all | panel-framework/dialogs (spec 3) — mobile presentation reuses the same `bottom-sheet` `<dialog>` variant `sidePanel`/the interface CSS already define, so the CSS variant is shell-adjacent but already exists; the component itself is out of scope for spec 1 |
| Sidebar item disclosure showing the current instance nested under its section | Already present (`instance_label`/`instance_url`/`expanded` in `_build_menu_items()`) — mockup does not show this at all | no change — FLS already does more here than the mockup shows |

## 4. Bottom tab bar vs hamburger/sheet: UX evidence

**Material 3** (`m3.material.io`): the navigation bar component "can hold three to five navigation destinations across the same hierarchy level. Don't use a navigation bar for fewer than three destinations" and, "for products with more than five navigation items, don't use a navigation bar; the elements may collide and there likely won't be enough space for translated text." Material 3 ties the choice to screen width, not just item count: compact windows (phone portrait) should always use a navigation bar, while medium-and-larger windows should switch to a navigation rail (3–7 items) or drawer instead of a bar. The mockup's four visible items plus an in-bar "More" overflow tab sits at the low end of the 3–5 band, with the fourth slot spent on overflow rather than a fifth real destination — Educators, Roles & permissions and Organisation settings (three more sections in the mockup's own sidebar) are not directly reachable from the bar. [Navigation bar – Material Design 3](https://m3.material.io/components/navigation-bar/guidelines), [Navigation rail – Material Design 3](https://m3.material.io/components/navigation-rail/guidelines)

**Apple HIG**: "In general, use between three and five tabs on iPhone… Keep the number of tabs small (about five or fewer); use a sidebar for complex hierarchies, and avoid overflow or 'more' tabs" — a direct tension with the mockup's own "More" tab, which HIG explicitly advises against. HIG also specifies tab bars are for navigation only, never for actions, and that every tab should stay visible and tappable even when its section is empty (explain emptiness inside the section, don't disable/hide the tab). [Tab bars – Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/tab-bars)

**NN/g on hidden navigation**: NN/g's quantitative study (179 participants, desktop and mobile) found hiding a site's main navigation behind a hamburger/hidden pattern roughly halved discoverability and made users measurably slower to complete navigation tasks (39% slower on desktop, 15% slower on mobile) versus visible or "combo" (partially visible) navigation, and that the effect showed up on both mobile and desktop. [Hamburger Menus and Hidden Navigation Hurt UX Metrics](https://www.nngroup.com/articles/hamburger-menus/), [Hidden vs. visible navigation methodology](https://www.nngroup.com/articles/hidden-navigation-methodology/) — a related follow-up specifically addresses how to make navigation discoverable without relying on the icon alone. [Beyond the Hamburger: navigation discoverable on mobile](https://www.nngroup.com/articles/find-navigation-mobile-even-hamburger/)

**How this fits a sidebar with grouped sections**: FLS's sidebar already groups a superset of sections (per the idea's own "settled" navigation model — sections with headings, and per the mockup, Teaching/Administration) larger than the 3–5 a tab bar can comfortably hold without an overflow tab. A bottom tab bar surfacing the top few sections still leaves the remaining sections behind a "More" affordance that is, in effect, the same hidden-navigation pattern NN/g's research flags — the tab bar would not replace the sheet, only add a second, partially-redundant entry point to the same items the sheet already exposes (as the mockup's own M02 "drawer" screen shows: the tab bar's items plus the sheet's items are the same list). Given the mockup shows 7 total sidebar items against a 4-slot bar (3 real + 1 overflow), Material 3's and Apple's own item-count guidance is already strained by FLS's actual section count, independent of any FLS-specific judgement.

## 5. Drawer/modal host placement

Read `htmx-modal-drawer-url-state.md` sections 1–2, dated 2026-09-24, researched against htmx 2.0.8, Alpine 3.15.8 CSP build, Django 6.0 (see that file for full sourcing; summarised here for the layout question only).

**Quick-view drawer** (section 1 of that file): "One `<dialog id="quick-view">` in the interface layout, a sibling of `#main-content` (outside anything that navigation swaps), driven by a `quickView` Alpine component. Model it on `sidePanel`." Its own pitfalls list is explicit about why: "Putting the drawer inside `#main-content`: every sidebar navigation destroys it mid-open. Keep it in the layout and close it on `htmx:beforeRequest` for `main-content` navigations." This matches the mockup's desktop layout exactly (section 2 above): the quick view is a flex/grid **column**, not a fixed overlay, sitting to the right of the main content column, in flow, non-blocking — closer to extending `.side-panel-grid` to a third column than to a `position:fixed` overlay. On mobile, the same research recommends the drawer flip to `showModal()` (an overlay, matching the mockup's M06 "quick view — snapshot sheet" bottom-sheet screen) via `matchMedia`, reusing the same modal/non-modal dialog mechanics `sidePanel` already implements — the research explicitly suggests factoring that shared "non-modal on desktop, modal on mobile, Back closes on mobile" logic out of `sidePanel` so both the sidebar and the drawer use it.

**Modal host** (section 2 of that file): "Native `<dialog>` opened with `showModal()`, **one shared host in the layout**, content loaded over HTMX... Don't use an Alpine-drawn `div`: it reimplements what `showModal()` gives natively." One `<dialog id="app-modal">` lives once in the page (i.e., in `_base_interface.html` or a shell-level include), and every action's form loads into it over `hx-get`/`hx-target="#app-modal-body"`, rather than each page eagerly rendering its own modal markup (the current `cotton/modal.html` pattern, which the same research flags as a source of duplicate-id and stale-CSRF-state bugs). Being a single host, it can be defined once per shell rather than per page.

**What reserving a block means concretely**: both hosts want to exist exactly once, outside `#main-content`, so that in-app htmx navigation (which swaps `#main-content` / `#sidebar-nav`) never destroys or reinitialises them mid-interaction. The cheapest way to guarantee "exactly once, outside the swap target" for every future consumer of `_base_interface.html` is a named block in the shell itself (e.g., alongside the existing `content`/`sidebar_content`/`footer` blocks) that the shell renders unconditionally with an empty default — a consumer that wants the quick view or modal fills the block; a consumer that doesn't (the course player, today) leaves it empty and pays only the cost of an unused `<dialog>` that never opens. Reserving now means adding the block(s) to the shell without wiring any Alpine/JS behaviour, which spec 3 supplies. Retrofitting later means finding every place in the shell's grid/flex structure a new sibling would need to be inserted and re-verifying it doesn't fall inside `#main-content` or inside the sidebar's own `<dialog>` — a smaller edit today than a structural one later, matching the idea's own framing ("Cheap to add here, awkward to retrofit").

## Status

status: ok
reason: n/a
