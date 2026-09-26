# Research: what the code looks like now, where the idea touches it

Scope: this file answers "does the code still match the idea's diagnosis and its stated targets,
after spec 1 (`panel-framework-core`) landed." It is not a plan. All paths are relative to the repo
root unless stated otherwise.

## 1. The current modal

Both files the idea names still exist, unchanged by spec 1 (spec 1's scope was panels/views/actions
plumbing and the shell scaffolding, not the dialog itself):

- `freedom_ls/base/templates/cotton/modal.html` — the shared modal *component*. An Alpine `div`
  (`x-data="modal"`, `role="dialog"`, `aria-modal="true"`), not a native `<dialog>`. Every instance is
  rendered eagerly wherever it's used: the trigger button and the (initially empty-of-request, but
  fully rendered) modal body sit in the DOM from first paint, gated by `x-show`/`x-cloak`, not created
  on demand.
- `freedom_ls/panel_framework/templates/panel_framework/partials/modal_form.html` — wraps a `<c-modal>`
  around a `<form hx-post hx-target="closest div[x-data]" hx-swap="outerHTML">`. This is the template
  every `FormPanelAction` (`CreateInstanceAction`, `EditAction`) renders through
  (`freedom_ls/panel_framework/actions.py:50`).
- `freedom_ls/panel_framework/templates/panel_framework/partials/delete_confirmation.html` — the same
  `<c-modal>` pattern, used only by `DeleteAction` (`actions.py:219`). It does not go through
  `modal_form.html`.

**Who uses `cotton/modal.html`:** only `modal_form.html` and `delete_confirmation.html` (confirmed by
grep across `freedom_ls` and `spec_dd`). No other template composes `<c-modal>` directly today. So the
idea's claim that these two are "the modal" the framework currently has is accurate and exhaustive —
there is no third modal usage to account for.

**Eager rendering, confirmed in code, not just in the idea's prose:**
`FormPanelAction.get_context_data()` (`actions.py:92-101`) always calls `self.get_form(ctx.request)`
and returns a bound context containing the unbound `form` — this runs on *every* render of the panel
that owns the action, whether or not the user opens the modal. Same for `DeleteAction.get_context_data`
(`actions.py:293-313`), which even runs a `Collector` (`get_cascade_summary`) to compute the cascade
summary on every render, not just on open.

**Validation error handling today:** `FormPanelAction.form_invalid()` (`actions.py:75-90`) re-renders
`modal_form.html` with the same context plus `modal_open="True"`, returns `HttpResponse(status=422)`.
The form posts to itself and swaps `closest div[x-data]` — i.e. the whole modal wrapper — with
`outerHTML`. This matches the idea's diagnosis exactly ("a validation error swaps the whole component
and drops the focused field"): there is no dedicated fragment inside the modal to swap; the entire
`x-data="modal"` root, trigger included, is replaced. Nothing moves focus to the error or re-opens the
modal automatically beyond the `data-open`/`modal_open` flag being read again by Alpine's `init()`.

**Status codes and headers seen today, all in `actions.py`:**
- `form_invalid` → `422`, body only, no headers.
- `CreateInstanceAction.form_valid` (`actions.py:158-167`): "save and add another" → `200` with
  `HX-Trigger: <event name from get_created_event_name()>` (a per-subclass custom name, e.g. no fixed
  convention). Plain save → `204` with `HX-Redirect` to `get_success_url(instance)` — a client-side
  hard navigation, not an htmx-managed one.
- `EditAction.form_valid` (`actions.py:196-202`): `204` with
  `HX-Trigger: {"panelChanged": {"instanceTitle": str(form.instance)}}`. No `HX-Redirect`/`HX-Location`.
- `DeleteAction.handle_submit` (`actions.py:315-338`): success → `204` with `HX-Redirect` to
  `self.success_url`; a `ProtectedError` at submit time (stale page) → re-renders
  `delete_confirmation.html` at `422`.
- The modal closes itself client-side: `cotton/modal.html`'s Alpine component listens for
  `htmx:afterRequest` and sets `open = false` on any `204` (`freedom_ls/base/static/base/js/alpine-components.js:184-189`) — there is no dedicated "close" `HX-Trigger` event today; `204` alone closes it.
- `panelChanged` is the only "domain event" name that exists anywhere in the codebase today. It is
  consumed two ways: (a) every leaf panel's own root re-fetches itself on `panelChanged from:body`
  (`panel_framework/templates/panel_framework/panels/_panel_base.html:11-14`), and (b) a document-level
  listener updates `#instance-title`'s text from `event.detail.instanceTitle`
  (`panel_framework/static/panel_framework/js/alpine-components.js:69-73`). There is no naming
  convention beyond this single event; the idea's open question ("exactly which domain events the
  modal emits on success, named once and reused by specs 6-9") is still fully open — nothing in the
  landed code answers it.

**`HX-Trigger`/`HX-Location`/`HX-Redirect`/`hx-on`/422 across `freedom_ls` generally** (grepped
site-wide, not just panel_framework): `HX-Redirect` and `HX-Trigger` appear only in
`panel_framework/actions.py` and a handful of unrelated apps (`course_interest/views.py`,
`course_applications/views.py`, `form_engine/views.py`, `accounts/utils.py` — none of these use
`HX-Location`). **`HX-Location` is used nowhere in the codebase today** — the idea's plan to use it for
post-success navigation is a genuinely new pattern for this project, not an extension of an existing
one. `hx-on` is not used anywhere (consistent with the CSP build and the idea's "no `hx-on`" rule).
`422` is used only by the two `panel_framework` action classes above; the generic `ds:htmx` skill also
documents `422` as the project convention for HTMX validation errors.

## 2. `sidePanel` and whether extraction is clean

**Location:** `freedom_ls/base/static/base/js/alpine-components.js:403-599`, registered as
`Alpine.data("sidePanel", ...)`. Hosted from a single `<div x-data="sidePanel">` wrapping a single
`<dialog x-ref="panelDialog">` in `freedom_ls/base/templates/_base_interface.html:150-204`. Every
interface that extends `_base_interface.html` gets exactly one `sidePanel` instance for its sidebar.

**Who uses it:** both the educator interface (`educator_interface/templates/educator_interface/interface.html` extends `_base_interface.html`, sidebar nav is the panel_framework menu) and the
**learner course player** (`learner_interface/templates/learner_interface/_course_base.html` also
extends `_base_interface.html`, with `data-desktop-lock="true"` behaviour referenced in its own
comments) — confirmed: it is one shared component serving two different sidebar contents (nav vs.
course TOC), each configured through `data-storage-key` / `data-desktop-lock` / `data-variant`
(`side-drawer` vs `bottom-sheet`).

**Full behaviour, read from the component:**
- Desktop (`≥1024px`, hardcoded via `matchMedia("(min-width: 1024px)")`, `init()` line 421): the panel
  is a **docked, non-modal, persistent** column. Opened with `dialog.show()`. Open/closed state
  persists to `localStorage` under `data-storage-key`. A `_desktopLock` flag (set for the course TOC)
  forces it always open and disables the toggle. `_syncGrid()` flips a `data-panel-open` attribute the
  CSS grid reads to collapse to one column when closed.
- Mobile (`<1024px`): the panel is a **true modal** (`dialog.showModal()`), giving native inertness,
  focus trap and Escape for free. Opening it does `history.pushState({flsSidePanel:true}, "")` so
  device/browser Back closes it (`_popstateHandler`, lines 501-509); closing (by any route) calls
  `history.back()` unless the close was itself caused by Back or by an in-flight htmx navigation
  (`_closingFromPopstate`/`_closingForHtmxNav` guards, lines 429-443).
- A `dialog.addEventListener("close", ...)` is the **single funnel** every dismiss route (Escape,
  backdrop click via the dialog's own `click` handler at line 444, programmatic `close()`, Back) goes
  through; it resets `open`, refocuses `this.triggerEl`, and unwinds the pushed history entry.
- Extra, sidebar-specific mobile logic that has nothing to do with "dialog + breakpoint": intercepting
  clicks on in-sheet `<a href>` links to replace (not push) the browser history entry so Back doesn't
  replay the sheet (lines 444-477); and closing the sheet on `htmx:beforeRequest` fired *from inside the
  dialog* so an htmx-driven nav control inside the sheet (the organisation switcher) also dismisses it
  (lines 495-499).
- Breakpoint-change handling (`_mq.addEventListener("change", ...)`, lines 524-543) closes/reopens and
  re-derives state for the new mode.

**Judgment on extraction — recommend copying the pattern, not extracting shared code, for this spec:**
Reasons, all grounded in the component as read:
1. **Different breakpoint.** `sidePanel` hardcodes `1024px` (Tailwind `lg`). The idea specifies quick
   view flips at `md` (768px). The breakpoint isn't a parameter today; making it one is itself a (small
   but real) change to a component that just shipped and is already exercised by two consumers and a
   Playwright/shell smoke test (spec 1's Testing section, "Shell" bullet).
2. **The `htmx:beforeRequest`-closes-the-dialog listener is actively wrong for quick view.** Quick
   view's whole point is that clicking a *second* trigger re-fetches into the still-open drawer
   (`hx-get` into the drawer body, `hx-sync` replace). If quick view's dialog carried `sidePanel`'s
   listener verbatim, its own content-loading request (which originates from inside the dialog) would
   trigger the "close for htmx nav" branch and slam the drawer shut on every click. This isn't a matter
   of passing a flag — it inverts the intended behaviour and would need to be branched out.
3. **Persistence and lock semantics don't apply.** `localStorage`-backed open/closed state and
   `_desktopLock` exist for the sidebar's "stays open across visits" and "TOC can't be closed" needs.
   Quick view is idea-specified as ephemeral (`No HTTP caching`, "closing hides the drawer without
   clearing it" — an in-memory concern, not a persisted one) and always closeable. Reusing the storage
   plumbing would mean either dead code paths in the shared component or new parameters just to turn
   them off.
4. **Focus contract differs.** `sidePanel` only refocuses the trigger *on close*. The idea requires
   quick view to *also* refocus the trigger immediately *after* `show()` on desktop, since `show()`
   itself moves focus — a behaviour `sidePanel` doesn't need (its desktop `show()` open is a passive
   dock, not focus-stealing in the same way, and it's driven by a toggle button that itself receives
   focus by being clicked).
5. What genuinely *is* shared and worth lifting as a literal pattern (not a shared component) is small:
   the "one `<dialog>`, `show()` non-modally above the breakpoint, `showModal()` below it, and push/pop
   one history entry only in the modal-below-breakpoint case" skeleton (`init()`'s branching in
   `toggle()`, lines 572-590, and the `close`-event funnel, lines 432-443) — on the order of 30-40 lines
   out of ~200. Copying that skeleton into a new, small `Alpine.data("quickView", ...)` costs little,
   avoids entangling an already-shipped, tested, two-consumer component with a third and
   behaviourally-different one, and matches the idea's own instruction not to let this decision "grow
   the spec." **Recommendation: copy, don't extract**, and leave a code comment cross-referencing
   `sidePanel` as the sibling pattern (as the codebase already does for other duplicated-on-purpose
   logic, e.g. the `@claude` comment at `educator_interface/views.py` around `CourseDataTable`).

## 3. Interface layout: where the dialogs sit, and the main content swap target

`freedom_ls/base/templates/_base_interface.html` **already carries the two empty host blocks spec 1
added** (requirement 25 of the landed spec): lines 252-253,

```
{% block quick_view_host %}{% endblock %}
{% block modal_host %}{% endblock %}
```

immediately after the closing `</div>` of `.side-panel-grid` (line 246) and *outside* both
`<div id="interface-main">` (line 207) and the sidebar `<dialog x-ref="panelDialog">` (line 185). The
template's own comment (lines 248-251) states the reason explicitly: "These sit outside
`#interface-main` and the sidebar `<dialog>` so any overlay they host survives an htmx swap of
`#main-content`." **This means spec 3 does not need to create or relocate anything in the shell — the
scaffolding the idea assumes already exists, in exactly the place and for exactly the reason the idea
wants.** Spec 3's job here is purely to fill those two blocks.

**Main content swap target:** the actual `id="main-content"` div is written in exactly one place,
`freedom_ls/panel_framework/templates/panel_framework/views/_main_base.html:5`
(`<div id="main-content" class="space-y-4 pl-2 sm:pl-6">{% block main %}{% endblock main %}</div>`),
per every view template (`instance_view.html`, `list_view.html`, `base_view.html`) extending it. This
sits *inside* `{% block content %}` in `educator_interface/interface.html:31-36`, which is itself inside
`<div id="interface-main">` in `_base_interface.html` — so `#main-content` is nested well inside the
region an htmx navigation swaps, while `quick_view_host`/`modal_host` are one level up, as siblings of
`#interface-main`, safe from that swap.

**Navigation mechanics: explicit `hx-get`/`hx-target`/`hx-push-url`, not `hx-boost`.** Every
panel_framework navigation site greps to the same triple:
`freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html:12-13,43-44`,
`freedom_ls/panel_framework/templates/panel_framework/partials/breadcrumbs.html:7`, and
`freedom_ls/base/templates/cotton/data-table-cells/link.html:9-12` (gated on `column.htmx_nav`) all use
`hx-get="..." hx-target="#main-content" hx-push-url="true" hx-swap="outerHTML"`. `hx-boost` exists in
the codebase (`learner_interface/templates/cotton/player-nav.html:27`, the header bar's admin link
opts *out* with `hx-boost="false"`) but panel_framework itself never uses it. Server-side, `views.py`
branches on `HX-Target: main-content` explicitly (`views.py:443,453` — falls through to the
"navigation response" branch when the target is `main-content` or unrecognised) rather than on
`hx-boost`'s implicit target.

## 4. Alpine setup: CSP, registration, load order, and where new JS would live

**CSP build confirmed.** `freedom_ls/base/templates/_base.html:69-70` loads
`@alpinejs/csp@3.15.8` (not the standard build) — so every Alpine component in scope must be a
registered `Alpine.data()` factory with no inline expressions, matching `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` and the `ds:alpine-js` skill it defers to.

**Registration files, in load order** (`_base.html:63-70`):
1. `freedom_ls/base/static/base/js/interface-swap-fallback.js` — loaded unconditionally, a
   document-level `htmx:beforeSwap` guard for `#interface-main` swaps.
2. `@alpinejs/collapse` plugin.
3. `freedom_ls/base/static/base/js/alpine-components.js` (defer) — `headerScroll`, `dropdownMenu`,
   `modal`, `toast`, **`sidePanel`**, `scrollTableLabels`, `debugBadge`.
4. `{% block extra_alpine_components %}` — per-page opt-in scripts. Filled by
   `educator_interface/templates/educator_interface/interface.html:4-6` with
   `panel_framework/js/alpine-components.js`, and separately by `learner_interface` and
   `course_applications` pages with their own app-scoped files.
5. `@alpinejs/csp` build itself (must come after every `Alpine.data()` registration).

**`freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`** is the framework's own
script, loaded only on pages that render through `panel_framework_view` (via the `extra_alpine_components` block). It currently registers `sidebarMenuItem` and `listRefresh`, plus two bare
`document.addEventListener` handlers (`htmx:afterSwap` for tab `aria-current`, and `panelChanged` for
the instance title). **This is the file both this spec and spec 2 (`educator-interface-2-panel-framework-tables`) would touch**: spec 2's idea (row selection checkbox column, "n selected" bar,
mobile filter/sort sheet) needs its own new `Alpine.data()` components, and this spec's modal/quick-view
components are framework-level, not educator-interface-level, so they belong here too, not in
`base/alpine-components.js` (which is for generic, non-panel-framework widgets) nor in
`educator_interface`'s own scope (there is no `educator_interface/static/.../alpine-components.js`
today — the educator interface reuses the framework's file wholesale). Any existing component here
listening to htmx events: `sidebarMenuItem` does not; `listRefresh` does (listens for the events named
in `data-refresh-events` and re-`htmx.ajax`s); the two bare document listeners both key off htmx events
(`htmx:afterSwap`, and the custom `panelChanged` trigger).

**Where new framework dialog JS would live:** `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`, alongside `sidebarMenuItem`/`listRefresh` and whatever spec 2 adds — it is
already the framework's shared, per-page-opt-in script, loaded after `base`'s and before the CSP
build finalises, which is the ordering `Alpine.data()` registration requires.

## 5. `panel_framework` API as landed: panels, actions, permission hook, event/`HX-*` naming

- **Actions** (`freedom_ls/panel_framework/actions.py`): `PanelAction` is the base — `template_name`,
  `get_context_data(ctx)`, `handle_submit(ctx: PanelContext) -> HttpResponse`,
  `has_permission(request, instance=None)`, `get_action_url(ctx)` builds
  `f"{ctx.base_url}/__actions/{self.action_name}"`. `FormPanelAction` adds `form_class`, `get_form`,
  `form_valid`/`form_invalid`. Concrete subclasses: `CreateInstanceAction`, `EditAction`,
  `DeleteAction`. An action declares its form via `form_class` (a `forms.ModelForm` subclass, class
  attribute) and its URL is always the derived `__actions/<action_name>` path — there is no separate
  "endpoint" concept to configure.
- **Permission hook:** `Panel.has_permission(self, request) -> bool` (defaults `True`,
  `panel_framework/panels.py` per the landed spec's requirement 2) gates whole panels; each
  `PanelAction.has_permission(request, instance)` gates individual actions and is checked before
  rendering (`Panel.get_actions()` filters by it). Spec 5 (permissions) is explicitly out of scope for
  what these return for the educator interface's roles — the hooks exist, the policy doesn't yet.
- **Domain-event / `HX-Trigger` naming:** see section 1 above — only `panelChanged` exists as a fixed,
  reused name; everything else (`get_created_event_name()`) is per-subclass and un-standardised. There
  is no naming convention document or constant registry for event names.
- Dispatch (`views.py`) branches on `HX-Target` (`main-content`, a `TabSet`'s `region_id`, a panel's
  `region_id`, else "navigation response") per spec 1 requirement 15, all confirmed present at
  `views.py:369,443,453`.

## 6. Where a table cell shows a learner or cohort name today

The shared cell template is `freedom_ls/base/templates/cotton/data-table-cells/link.html` (loaded via
`{"template": "cotton/data-table-cells/link.html", ...}` column declarations). It is used for the
learner name columns (first/last name, e.g. `LearnerDataTable` in
`freedom_ls/educator_interface/views.py:155-171` and `CourseLearnerRegistrationDataTable:561-576`) and
for cohort/course name columns (`CohortDataTable:104-113`, `CourseDataTable:460-480`). It renders one
`<a href="{{ resolved_url }}">{{ object|getattr_str:column.text_attr }}</a>`, optionally with
`hx-get`/`hx-target="#main-content"`/`hx-push-url`/`hx-swap="outerHTML"` when `column.htmx_nav` is set
(`base/templates/cotton/data-table-cells/link.html:7-13`). A second cell template,
`freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_links.html`, renders
a comma-separated list of cohort links for a learner row's "Cohorts" column, using the same
`resolve_url_path_template` helper. **This single shared cell template is exactly the seam the idea's
"first consumers" section wants** ("Reachable from every table cell that shows a learner, through one
shared cell template") — it already is one shared template, just not yet a quick-view trigger.

## 7. Contradictions between the idea and the landed code

**None found that break the idea's premises.** Specifically checked and confirmed *consistent*, not
contradictory:
- `cotton/modal.html` and `panel_framework/partials/modal_form.html` both still exist, unrenamed,
  exactly where the idea says they are, doing exactly what the idea's "Why" section describes (eager
  render, no focus management, whole-component swap on error).
- `sidePanel` still exists under that exact name (the idea's own wording), still in
  `_base_interface.html`, still the component to "model" the quick view on.
- The `quick_view_host`/`modal_host` blocks the idea implicitly needs a place for are **already landed**
  (spec 1 requirement 25) at exactly the position the idea would want (outside `#interface-main` and
  the sidebar dialog). This is worth flagging explicitly even though it isn't a contradiction: it means
  spec 3 inherits ready-made scaffolding rather than having to add it, which the idea (written before
  spec 1 landed) doesn't call out.
- One inconsistency worth flagging, though it's in a *skill* file rather than the idea: `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`'s component inventory table lists the sidebar
  component as `sidebarComponent`; the actual registered name is `sidePanel`
  (`base/static/base/js/alpine-components.js:403`). Not the idea's error, but worth a fix note since
  the idea's Resources section points at this skill.
- The idea's proposed use of `HX-Location` for post-success navigation is **new to this codebase** —
  `HX-Location` is used nowhere today (see section 1); `HX-Redirect` (a full client-side redirect, not
  an htmx-managed navigation) is what `CreateInstanceAction`/`DeleteAction` use today. This isn't a
  contradiction (the idea is explicitly proposing to change this), but it means there is no existing
  local pattern to copy for it — it will be new plumbing, not a refactor of existing plumbing.

## Skills/conventions the idea should mind

- `claude_plugins/django-stack/skills/htmx/SKILL.md`: confirms `422` for validation errors (matches
  idea), "always specify `hx-target` and `hx-swap` together," prefer `outerHTML`.
- `claude_plugins/django-stack/skills/alpine-js/SKILL.md` / `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`: CSP build is `enabled` for this project (confirmed directly in `_base.html` rather than
  via `.claude/ds/config.md`, which wasn't read but the runtime evidence is unambiguous) — every new
  modal/quick-view component must be `Alpine.data()`-registered, no inline expressions, data passed via
  `data-*` attributes read through `this.$el.dataset` (exactly as `sidePanel` and `modal` already do).
  Rule 8 ("close overlays on Escape via `x-on:keydown.escape.window`") is superseded for native
  `<dialog>` by the platform's own Escape handling, which the idea correctly relies on instead.
- `claude_plugins/fls-dev/resources/templates_and_cotton.md`: cotton's flat namespace means a new
  `<c-modal>`/quick-view trigger component, if it replaces the current `cotton/modal.html`, shadows
  cleanly for themes at the same `cotton/<name>.html` path — no special handling needed there.

status: ok
