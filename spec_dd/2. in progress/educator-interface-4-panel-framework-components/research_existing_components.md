Research: what FLS already has that overlaps with the components spec 4 plans to build, and how
spec 1's panel framework renders today.

## 1. Per-component inventory

For each, current state, its API/styling, and a reuse/wrap/build recommendation.

### Page header (title, subtitle, status badge, action group)

Nothing today is a page header component. What exists:

- `c-page` (`freedom_ls/base/templates/cotton/page.html`) — a width/padding wrapper only (`width`,
  `flush`, `class` vars). It wraps a page's content column; it does not render a title.
- `panel_framework/views/_instance_view_base.html:5` renders `<h1 id="instance-title">{{ main.instance }}</h1>`
  directly (autoescaped `str(instance)`, no subtitle/badge slot) followed by `main.actions` in a
  `c-button-group variant="right"` (`:6-11`), then `{% render_panel main.panel %}`. This `<h1>` +
  actions block is the only "page header" analogue in the framework, and it is inline markup in the
  view template, not a component.
- `c-breadcrumbs` (`freedom_ls/base/templates/cotton/breadcrumbs.html`) sits above this via
  `panel_framework/partials/breadcrumbs.html`, which is a separate region (`#breadcrumbs`, OOB-swapped),
  not part of any header component.
- `c-button-group` (`freedom_ls/base/templates/cotton/button-group.html`) already gives the "action
  group" half (`variant="right"` is what's used for instance actions).

**Recommendation: build new** `panel-page-header` (title, optional subtitle, optional status badge
slot, `c-button-group` for actions), composing the existing `c-button-group`. It should probably
replace the raw `<h1 id="instance-title">...` block in `_instance_view_base.html:5` — note that id is
read by JS (`panelChanged` listener sets `#instance-title`'s text, `alpine-components.js` per spec 1
requirement 23) so the new component must keep emitting `id="instance-title"` verbatim, or the JS
contract breaks silently.

### Stat tile (value, label, delta/sub-line, responsive row)

Nothing exists. No card/tile component in `base`, `learner_interface` or `panel_framework` shows a
bare metric. **Build new**, `panel-stat-tile`.

### Status badge (fixed vocabulary → semantic tokens)

- `c-chip` (`freedom_ls/base/templates/cotton/chip.html`) is the closest existing primitive: vars
  `variant` (maps to `.chip-{variant}` in `tailwind.components.css`'s themable-primitives list —
  `.chip*` is named there per `claude_plugins/fls-dev/resources/frontend_styling.md:24`), `size`,
  `icon`, `class`. It is generic (any variant string), carries text in its slot already (satisfies
  the idea's accessibility note "badges carry text, not just colour"), and supports an icon.
- It has **no fixed vocabulary** — a status badge needs a closed status→token mapping
  (active/inactive/pending/complete/in progress/stalled, per idea.md) that `c-chip` does not own.

**Recommendation: wrap**, not build from scratch. A `panel-status-badge` component that takes a
`status` prop, maps it to a `variant` + label internally (the vocabulary decision is explicitly open,
coordinated with spec 10), and renders `<c-chip>` underneath. This keeps `.chip*`'s themable-primitive
styling (dark mode, theme overrides already flow through `tailwind.components.css`) rather than
duplicating it.

### Avatar chip (initials + name, optional email/role)

Nothing exists — `c-chip` is a single-slot label chip, not a two-line identity chip with initials.
No avatar/initials helper found anywhere in `base` or `learner_interface`. **Build new**,
`panel-avatar-chip`. Likely composes `c-icon`-free initials (no icon needed) in a circular token
(background from a role/semantic token per the idea's "FLS role tokens only" rule) plus a two-line
text stack — nothing to wrap.

### Attention list (row per learner: reason, badge, one action)

Nothing exists as a component. `c-data-table` (`freedom_ls/base/templates/cotton/data-table.html`)
is the closest structural analogue (rows + cell templates + pagination) but it's a `<table>`, and the
idea explicitly wants "the attention list is a list" (accessibility requirement) — i.e. `<ul>/<li>`,
not `<table>`. **Build new**, `panel-attention-list`, as its own list markup; it will likely compose
`panel-status-badge` (reason badge) and `c-button`/`c-button-group` (the one action) per row rather
than reusing `c-data-table`.

### Progress bar (percentage + optional label)

- `c-course-progress-bar` (`freedom_ls/learner_interface/templates/cotton/course-progress-bar.html`)
  is a real, working progress bar: native `<progress>` (implicit ARIA role, no manual `aria-value*`),
  vars `percentage`, `accent_slot_key`, `label` (aria-label), `bar_class`, `label_class`, `suffix`.
  It is learner-interface-owned and its fill colour is hard-tied to
  `course-progress-{{ accent_slot_key }}` — a course-accent-palette class from
  `tailwind.components.css` (`--fls-course-accent-*` tokens, per `frontend_styling.md:99-107`), not
  a role token. The idea's progress bar (mockups 01, 03) needs semantic-token fills (e.g. success/
  warning/error for stalled/complete/in-progress), not course-accent tinting.
- Out of scope note in idea.md: "Changes to `base` components... leave it" and this lives in
  `learner_interface`, not `base` — either way it's out of scope to touch.

**Recommendation: build new**, `panel-progress-bar`, on the *same* underlying `<progress>` markup
pattern (native element, `aria-label`, percentage readout) but parameterised on a role/semantic token
rather than a course-accent slot. The idea itself flags this component as general enough to note for
a later move to a shared location — do that noting, don't move `course-progress-bar.html` now (out of
scope: "Changes to `base` components" is about `base`, but the safer reading given the idea's own "if
general enough for learner interface, note for later move, not moved now" line, §"Where", is: build
the new one under `panel_framework`, and leave a note that the two might merge later).

### Section card (heading, description, body, actions footer) vs `_panel_base.html`

This is the idea's flagged open question. Current state of `panel_framework/panels/_panel_base.html`:

```
<section class="surface" data-panel="{{ name }}" ...>
    {% block panel_header %}{% if title %}<header class="mb-4"><h2>{{ title }}</h2></header>{% endif %}{% endblock %}
    <div>{% block panel_body %}{% endblock %}</div>
    {% block panel_actions %}{% if actions %}<div class="mt-4 pt-4 border-t border-border"><c-button-group variant="right">...</c-button-group></div>{% endif %}{% endblock %}
</section>
```

This is *already* heading + body + actions-footer shaped, styled with a bare `.surface` utility class
(no border/shadow/radius/padding at all currently — `.surface` is just the background-colour role
token, defined in `tailwind.components.css`'s base layer, not a card treatment). It has no
`description` slot. It carries load-bearing plumbing that a pure cotton component doesn't have to
worry about: `data-panel="{{ name }}"` (Playwright's nesting assertion locates this, per spec 1
requirement 20), the `id="{{ region_id }}"` on the root when there's no separate region template, and
the `hx-get`/`hx-trigger="panelChanged from:body"` self-refresh wiring (requirement 9). Every leaf
panel (`instance_details.html`, `data_table.html`, `panel.html` itself) extends
`panels/_panel_base.html` via the thin leaf/`_base` pairing spec 1 established
(`freedom_ls/panel_framework/templates/panel_framework/panels/panel.html` is one line:
`{% extends "panel_framework/panels/_panel_base.html" %}`).

**This is genuinely the fork the idea leaves open, and the code confirms both options are live:**
- *Wrap*: change `_panel_base.html`'s `panel_header`/`panel_body`/`panel_actions` blocks to render a
  new `<c-panel-section-card>` (or similar) around `{{ slot }}`-equivalent content, keeping the
  `<section>` root, `data-panel`, `id`, and `hx-*` attributes on the outer element so Playwright/htmx
  contracts are untouched, and pushing only the *visual* chrome (border, shadow, radius, description
  slot) into the cotton component.
- *Replace outright*: make `panels/_panel_base.html` itself the section-card component (no separate
  cotton file), i.e. the framework's only "card" is this template, and `panel-section-card` is not a
  separate reusable unit — anything outside a panel that wants the same look calls the cotton
  component, and `_panel_base.html` is rewritten to look like it.

Given the spec-1 contract that "a component owns its own styling" and lives in one shadowable file
(`templates_and_cotton.md:24-30`), and that cotton's `<style>`/utility rule already governs
`panel_framework` templates too (they are ordinary Django templates, not cotton, but follow the same
"utilities on the markup, `@layer components` only where needed" rule per idea.md "Styling rules"),
the cleaner fit is **wrap**: keep `_panel_base.html` as the plumbing (hx-*, ids, `data-panel`) and
have its `panel_header`/`panel_body`/`panel_actions` blocks render through the new cotton
section-card so both a bare panel and a hand-placed section card in some other page look identical
and are themed from one file. But this is exactly the decision idea.md defers to the spec — flag it,
don't resolve it here.

### Definition list vs `_instance_details_base.html` / `_details_value.html`

`panel_framework/panels/_instance_details_base.html` already *is* a responsive definition list:

```html
<dl class="md:hidden space-y-3">
    {% for row in rows %}<div><dt>{{ row.label|capfirst }}</dt><dd>{% include "..._details_value.html" ... %}</dd></div>{% endfor %}
</dl>
<table class="hidden md:table">...<th>{{ row.label|capfirst }}</th><td>{% include ... %}</td>...</table>
```

— stacked `<dl>` under `md`, a two-column `<table>` from `md` up, exactly the idea's "Definition list
for label and value pairs, responsive (03 'Learner details')" requirement. `_details_value.html` is a
one-line boolean/plain-value renderer (`c-icon boolean_true/boolean_false` or `{{ row.value }}`) fed
by the vendored `field_display.py` (spec 1 requirement 7 — `label_for_field`, `lookup_field`,
`display_for_field`). Both are Python-data-driven (a panel's `fields: list[str]` of `__` paths),
extending `panels/panel.html` (so it inherits the section/header/actions chrome above).

**Recommendation: reuse/wrap, not build a parallel component.** A `panel-definition-list` cotton
component (rows in, dt/dd or table out) could be extracted so it's usable outside an
`InstanceDetailsPanel` (e.g. a section-card body assembled by hand), with
`_instance_details_base.html` calling into it instead of inlining the markup — this satisfies "Cotton
components... built once" without breaking the panel's Python-side field-resolution contract, and
`_details_value.html`'s boolean-icon convention should carry over unchanged (it already follows
`fls-dev:icon-usage`'s "no ad hoc booleans" pattern).

### Toolbar (search, filter chips, primary actions)

Nothing exists as a standalone component. `c-data-table` has an inline search form
(`data-table.html:14-32`, `show_search` var, hx-get on submit/input, no filter chips) baked directly
into its own markup — it is not extractable as-is because it's coupled to `base_url`/`table_id`/
`sort_by`/`sort_order` and the table's own `hx-target`. Spec 2 (`educator-interface-2-panel-framework-tables`,
"tables2_viability" research) owns the table layer's "filters, selection and export" per spec 1's
scope note (`1. spec.md:38`) — so a toolbar built here needs to compose with whatever spec 2 lands,
not duplicate it. **Build new**, `panel-toolbar` (search input + filter-chip slot + action slot), but
coordinate the search-input shape with spec 2 so `c-data-table` can eventually delegate its own
search UI to it rather than the two diverging.

### Empty state (icon, sentence, one action)

Nothing exists. `c-loading-indicator` (below) is the nearest sibling concept (a full-block state
message) but is loading-specific. No `empty_message` component — `c-data-table`'s `empty_message` var
(`data-table.html:97-99`) is just a plain-text table-row fallback (`<td colspan=...>{{ empty_message }}</td>`),
no icon, no action. **Build new**, `panel-empty-state`.

### Tab bar vs `_tab_set_base.html`

`panel_framework/panels/_tab_set_base.html` (spec 1 requirement 19) already implements the exact tab
bar the idea wants shared: `<nav aria-label="{{ title }}">` + `<ul>` of `<a>` links, each carrying
`href`, `hx-get`, `hx-target="#{{ region_id }}"`, `hx-push-url="true"`, `hx-swap="innerHTML"`, and
`aria-current="page"` on the active one; styling is inline utility classes
(`aria-[current=page]:border-b-2 aria-[current=page]:border-primary ...`, explicitly said to "follow
`sidebar_nav.html`'s `aria-[current=page]` variant" per spec 1 requirement 19). There is no cotton
component here at all — it's plain Django-template markup with Tailwind utilities directly on it, no
`<style>`/`@layer components` block.

**Recommendation: wrap the styling, keep the plumbing.** Same shape of answer as the section-card
question: `_tab_set_base.html`'s nav/list *structure* is load-bearing (region id targeting, the
`data-tab-set` attribute the `htmx:afterSwap` JS listener keys on per spec 1 requirement 23, the
`aria-current` contract), so it should stay Python/Django-template, not become a duck-typed cotton
component the way a page-level tab bar might be. What moves into a cotton `panel-tab-bar` is the
*classes* — extract the `<nav>`/`<ul>`/`<a>` markup's presentation into a component that
`_tab_set_base.html`'s `tab_nav` block calls with `tabs`/`region_id` passed in, so the same visual tab
bar can be reused verbatim wherever mockups 03/05 show tabs outside an actual `TabSet` (if that ever
happens) and so theming happens in one file.

### Skeleton blocks vs `c-loading-indicator`

`c-loading-indicator` (`freedom_ls/base/templates/cotton/loading-indicator.html`) is a *spinner*
block (`htmx-indicator` class, `c-icon name="loading" class="animate-spin"`, a message line) — this
is a "loading" state, not a "skeleton" (shape-matching placeholder blocks) as spec 3
("Filling the quick-view and modal blocks") and spec 4's own idea.md item both name separately
("Skeleton blocks for loading states used by spec 3"). No skeleton/placeholder-shape component exists
anywhere in the repo (`grep` for "skeleton" in templates turns up nothing outside this idea.md).
**Build new**, `panel-skeleton` (or a small family — text-line, tile, row skeletons) — this is not a
wrap of `c-loading-indicator`, it is a different visual language (shape placeholders vs a spinner),
though both should probably share the same `htmx-indicator`-class convention so htmx's automatic
show/hide on request-in-flight still works without extra JS.

### `c-page` / breadcrumbs vs page header

Already covered under "Page header" above: `c-page` is layout-only (width/padding), not a header;
`c-breadcrumbs` is a separate, already-working component (`base/templates/cotton/breadcrumbs.html`)
consumed today by `panel_framework/partials/breadcrumbs.html` (which just forwards
`hx_target="#main-content"`, `id="breadcrumbs"`, `oob`). The idea's page header sits *below* the
breadcrumb region, not replacing it — no overlap to resolve there, breadcrumbs stay exactly as they
are.

## 2. Cotton name resolution, namespace, collision risk

Confirmed in `claude_plugins/fls-dev/resources/templates_and_cotton.md:19` and the spec-1
`research_template_contract.md` (§1, "Theme shadowing by template path"): cotton resolves **every**
component — regardless of which app's `templates/cotton/` it physically lives in — to the single flat
path `cotton/<name>.html`. The loader order is `django_cotton.cotton_loader.Loader` →
`filesystem.Loader` (project `TEMPLATES[0]["DIRS"]`, which is how a theme's `templates/` dir,
prepended by `configure_theme()`, wins) → `app_directories.Loader` (searches every `INSTALLED_APPS`
entry's own `templates/` in `INSTALLED_APPS` order). Because the cotton namespace has no app prefix,
**two apps shipping `cotton/chip.html` would silently collide** — whichever app's `templates/`
directory the `app_directories.Loader` reaches first (by `INSTALLED_APPS` order) wins, with no error.

Existing prefixing precedent in the repo: components already avoid generic collision-prone names by
prefixing with their domain — `course-progress-bar`, `course-card-shell`, `course-row-shell`,
`course-section-pagination`, `course-price` (all `learner_interface`), `content-link`, `pdf-embed`,
`file-download`, `image-grid` (all `content_engine`). `base`'s own components stay unprefixed because
`base` is the lowest/shared layer everything else builds on (`chip`, `button`, `callout`, `modal`,
`page`, `breadcrumbs`, `data-table`, `loading-indicator`, `media-card`, `dropdown-menu`, `pagination`,
`header-button`, `form-page-link`, `error-page`, `scroll-table-labels`, `markdown-container`).

`idea.md` already names the intended convention: prefix with `panel-` (its own example:
`panel-stat-tile`) "or a namespace decided in the spec". Given the domain-prefix precedent above,
`panel-` is consistent with how `course-`/`content-` are used elsewhere, and is the safest choice —
every planned name in this inventory (`panel-page-header`, `panel-stat-tile`, `panel-status-badge`,
`panel-avatar-chip`, `panel-attention-list`, `panel-progress-bar`, `panel-section-card`,
`panel-definition-list`, `panel-toolbar`, `panel-empty-state`, `panel-tab-bar`, `panel-skeleton`)
currently has **zero** collision against any existing `cotton/*.html` name across `base`,
`content_engine`, `learner_interface`, `icons` (checked via a full glob of
`freedom_ls/*/templates/cotton/*.html` — 34 files, none prefixed `panel-` or bare-named the same as
any item above).

`panel_framework/templates/cotton/` does not exist yet (no such directory found) — it will be a new
loader path, and since `@source "./freedom_ls/**/templates/**/*.html"` in `tailwind.input.css` already
globs every app's `templates/` tree (see §4), it needs no Tailwind config change to be picked up.

## 3. How spec 1's templates are styled today

`panel_framework` templates (both the `panels/*` and `views/*` pairs) use **inline Tailwind utility
classes directly in the markup** — there is no `<style>`/`@layer components` block anywhere in
`freedom_ls/panel_framework/templates/`. Examples: `_panel_base.html`'s `class="surface"` (a single
utility-like class defined as an `@layer base` element rule — see below), `_tab_set_base.html`'s long
`aria-[current=page]:*` utility chains, `sidebar_nav.html`'s `aria-[current=page]:bg-surface-2
aria-[current=page]:border-l-2 ...`. None of this reaches `tailwind.components.css` — that file is
reserved (per `frontend_styling.md:20-27`) for `@layer base` element rules, the classes a theme
reopens (`.btn*`, `.chip*`, `.alert*`, `.surface`, `.signup-panel`, `.header`, `.course-card`,
`.course-accent-*`, `.course-progress-*`, `.modal-backdrop*`), and markdown-renderer-only classes
(`.task-list*`). `.surface` (used bare on `_panel_base.html`'s `<section>`) is exactly one of those
pre-existing themable-primitive classes, not something the framework defines itself.

So spec 1's panel templates are *already* following the "utilities on the markup, nothing in
`tailwind.components.css`" rule idea.md restates for spec 4 — the one exception being their reliance
on the pre-existing `.surface`/`.chip*`/`.btn*` themable primitives, which spec 4's new components
will also want to reuse (e.g. `panel-status-badge` wrapping `c-chip`'s `.chip-{variant}` classes,
`panel-section-card` potentially building on `.surface`) rather than reinventing token-level colour
rules.

Where the new components get consumed: every `panel_framework/panels/_*_base.html` and
`panel_framework/views/_*_base.html` file is a plausible call site — `_panel_base.html`'s three named
blocks (`panel_header`, `panel_body`, `panel_actions`) are the natural insertion points for
`panel-section-card`/`panel-page-header`-equivalent structure; `_instance_details_base.html` for
`panel-definition-list`; `_tab_set_base.html` for `panel-tab-bar`; `_data_table_region_base.html`
(currently a one-line `<c-data-table .../>` wrapper) for a future toolbar swap-in; and
`views/_instance_view_base.html` for `panel-page-header` around its `<h1 id="instance-title">` +
actions block.

## 4. Tailwind content globs — panel_framework/templates/cotton picked up automatically

No `tailwind.config.js`/`.ts`/`.cjs` exists in the repo — this is Tailwind v4's CSS-native
configuration. The content globs live in `tailwind.input.css` (`@source` directives, Tailwind v4
syntax):

```css
@source "./freedom_ls/**/templates/**/*.html";        /* every FLS app's templates tree */
@source "./freedom_ls/themes/*/templates/**/*.html";  /* theme overrides — Tier 3 */
```

`./freedom_ls/**/templates/**/*.html` already matches any file under
`freedom_ls/panel_framework/templates/cotton/*.html` (a not-yet-existing but perfectly ordinary
subtree of `freedom_ls/panel_framework/templates/`) with no change needed. Confirmed by the comment
at `tailwind.input.css:3-8`: paths are hardcoded (Tailwind's CLI runs in Node, can't read Django
settings) and mirror `FLS_THEMES_DIRS` from `config/settings_base.py` — nothing app-specific is
enumerated, it's a blanket recursive glob. The one manual step every new/changed template triggers is
`npm run tailwind_build` (and `requires_tailwind_rebuild: true` in upgrade notes, per the CLAUDE.md
command list and spec 1's own upgrade-notes precedent).

## 5. Dev-only/DEBUG-gated pages and test template dirs (for the idea's "reference page")

**Precedent for a DEBUG-gated reference/QA page already exists and is a good model:**
`freedom_ls/qa_helpers/` is mounted only under `if settings.DEBUG:` in `config/urls.py:73-80`
(`path("qa/", include("freedom_ls.qa_helpers.urls"))`, alongside `debug_toolbar`/
`django_browser_reload`). Inside it, `freedom_ls/qa_helpers/toast_views.py` +
`freedom_ls/qa_helpers/urls.py` (marked `# QA-TEMP: URL routing for toast QA playground. DEBUG-only.`)
+ `freedom_ls/qa_helpers/templates/qa_helpers/toast_playground.html` is exactly "a dev-only page
rendering every component in every state" for toasts — four routes (`toasts/full/`,
`toasts/htmx-success/`, `toasts/htmx-error/`, `toasts/playground/`), each a plain Django view/
template, no auth, gated purely by the app only being URL-wired under `DEBUG`. This is a directly
reusable pattern for spec 4's reference page: a `panel_framework`-owned (or new small app's) view +
template mounted the same way, not necessarily inside `qa_helpers` itself (that app's own `urls.py`
comment flags it as QA-TEMP, i.e. someone else's temporary scaffolding, not a place to add permanent
framework-kit infrastructure) but following its exact DEBUG-gating shape.

**`freedom_ls/dev_tools/`** is a different thing — it's `management/commands/` only
(`danger_content_delete`, `danger_clear_all_course_progress`, `create_demo_data`), gated by
`require_dev_tools_enabled()` (`DEBUG` or `DEV_TOOLS_ENABLED` setting) in `guard.py`, no views/URLs at
all. Not directly relevant to a *page*, but shows the same "on unless explicitly enabled outside dev"
gating idiom idea.md wants ("A dev-only page (behind `DEBUG`, or in the framework's test templates)").

**Framework test templates:** `freedom_ls/panel_framework/tests/templates/panel_framework/` holds
five fixture templates (`test_extra_oob_fragment.html`, `test_interface.html`,
`test_stub_details.html`, `test_second_extra_oob_fragment.html`, `test_action_url.html`) — these are
override-mechanism test fixtures (proving leaf/`_base` extension and template-path shadowing, per
spec 1 requirement 18's "Both extension routes are proved in Testing"), not a rendered gallery of every
component state. If spec 4's reference page instead lives "in the framework's test templates" per the
idea's alternative, it would be a new template here (or a new `tests/` fixture module) rather than
reusing any of the five existing ones, which are narrowly single-purpose.

status: ok
