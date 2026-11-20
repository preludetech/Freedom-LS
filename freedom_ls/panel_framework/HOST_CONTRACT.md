# Host contract

What a project must provide before the panel framework renders correctly in it. Each system check
that fails on a missing piece points at a section here. `templates/panel_framework/minimal_shell.html`
is a working host shell, and the blocks below are taken from it.

## Shell ids

The host's base template renders `#interface-main` around the page content. `quick_view_host` and
`modal_host` are included outside it, so an overlay survives an htmx swap of `#main-content`. The
framework JavaScript and the fragments address these elements by id.

Every other id comes from a framework fragment. Do not reuse one in the host's markup:
`#main-content`, `#instance-header`, `#sidebar-nav`, `#breadcrumbs`, `#page-title`, `#app-modal`,
`#app-modal-body`, `#quick-view*`, `#scope-announcer`.

The host's base template also renders four things the shell supplies:

- Empty `#toast-region-polite` (`role="status"`, `aria-live="polite"`) and `#toast-region-assertive`
  (`role="alert"`, `aria-live="assertive"`) elements. A response carries a toast as an out-of-band
  fragment that appends to one of them.
- A place where Django's `messages` render. A request without scripting shows its outcome there.
- An htmx listener for `htmx:beforeSwap` (see [Scripts and order](#scripts-and-order)).
- Base element styles for `table`, `th`, `td`, `h1` and `h2`. Framework templates style their own
  markup with utilities and leave cell padding and colour, and heading size and weight, to the
  page. The rules are in `css/minimal_shell.css`, under `@layer base`.

## Fragments

The host includes these from `panel_framework/partials/`:

| Fragment | Where | Notes |
| --- | --- | --- |
| `modal_host.html` | outside `#interface-main` | the one `<dialog>` every action fragment loads into |
| `quick_view_host.html` | outside `#interface-main` | the row quick-view drawer |
| `announcer_host.html` | outside `#interface-main` | the `#scope-announcer` live region |
| `sidebar_nav.html` | in the navigation panel | needs `menu_groups` and `request` |
| `breadcrumbs.html` | top of `#interface-main` | a back link, or an empty `#breadcrumbs` |
| `document_title.html#document-title` | inside the host's `<title>` | the one source of the title string |
| `page_title.html` | below the breadcrumbs | needs `page_title`, optionally `page_subtitle` |

The shell's own copy to start from:

```django
<title>{% include "panel_framework/partials/document_title.html#document-title" %}</title>
...
<div id="interface-main">
    {% include "panel_framework/partials/breadcrumbs.html" %}
    {% include "panel_framework/partials/page_title.html" %}
    {% block content %}{% endblock content %}
</div>
{% include "panel_framework/partials/quick_view_host.html" %}
{% include "panel_framework/partials/modal_host.html" %}
{% include "panel_framework/partials/announcer_host.html" %}
```

The navigation panel needs a `<dialog>` driven by `x-data="sidePanel"`. Copy it from
`minimal_shell.html` and keep the `side-panel-dialog` class, which `shell-components.js` selects.

## Context

- `site_name` is optional. Without it the document title has no suffix and no trailing dash.
- `request.panel_scope_name` is optional. A host whose interface is scoped sets it, and the title
  names the scope. Without it the segment is dropped.
- `request.panel_url_kwargs` is optional. A host whose panel URLs carry a scope kwarg (an
  organisation slug, say) sets it to a dict of those kwargs, and the framework adds them whenever it
  reverses a panel URL.

## Scripts and order

Each step names the failure it prevents.

1. htmx 2.x, loaded globally. Without it no panel link, filter or action fragment works.
2. `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>`. Without it every htmx POST answers 403.
3. An `htmx:beforeSwap` listener that swaps three kinds of response: any 422, a 403 or 404 whose body
   contains `data-htmx-swap-error`, and any error status whose body carries an out-of-band toast
   (`hx-swap-oob="beforeend:#toast-region-`). Without it a validation error, a vanished object or a
   rejected role change never reaches the page, because htmx swaps no 4xx response by default. The
   listener in `minimal_shell.html` is a complete copy. FLS's is in
   `freedom_ls/base/static/base/js/alpine-components.js`.
4. The host's own Alpine component scripts.
5. `panel_framework/js/shell-components.js`, then `panel_framework/js/alpine-components.js`, both
   `defer`red. Alpine starts the moment its script loads. A component it meets before registration is
   an unregistered `x-data` name, and the element stays inert.
6. The Alpine CSP build (`@alpinejs/csp` 3.x), last.

## Tailwind

Tailwind 4.1.16 or later. The framework's classes only exist in the host's stylesheet if the host's
Tailwind build reads the framework's templates and stylesheet.

1. Run `uv run manage.py write_panel_framework_css` before every Tailwind build. It writes
   `tailwind.panel_framework.css` into `BASE_DIR`, holding a `@source` of the framework's templates and
   an `@import` of `css/panel_framework.css`. The paths are machine-specific, so rerun it after
   installing or upgrading the framework.
2. In the input CSS, add `@import "./tailwind.panel_framework.css";` after `@import "tailwindcss"`
   and the host's theme tokens, and before the host's theme overrides. A theme that reopens
   `.panel-surface` wins only if it comes later.
3. Commit neither `tailwind.panel_framework.css` nor the compiled output.

## Tokens

The framework's templates and stylesheet use these colour roles as utilities (`bg-primary`,
`text-muted`, `border-border`) and read some as raw variables. The host defines every one of them under
the same `--color-<role>` names. `css/reference_theme.css` is the source of truth, with neutral working
values. A test keeps this block equal to that file. `on-*` is the foreground to put on the matching
background.

```
--color-primary
--color-on-primary
--color-secondary
--color-accent
--color-on-accent
--color-success
--color-on-success
--color-warning
--color-error
--color-on-error
--color-info
--color-success-light
--color-warning-light
--color-error-light
--color-info-light
--color-on-success-light
--color-on-warning-light
--color-on-error-light
--color-on-info-light
--color-primary-hover
--color-accent-hover
--color-success-hover
--color-error-hover
--color-surface
--color-surface-2
--color-on-surface
--color-border
--color-muted
--color-focus-ring
--color-sidepanel
```

`--panel-table-head`, `--sidebar-top` and the `--modal-*` variables are internal to the framework.

## Icons

The host provides a `c-icon` component taking `name`, `class` and `aria_label`. It must draw every name
in this block. The block equals `REQUIRED_ICON_NAMES` in `checks.py`.

```
add
boolean_false
boolean_true
check
close
download
dropdown
error
filter
info
loading
menu
more_options
next
open_page
previous
quick_view
retry
search
settings
sort_asc
sort_desc
sort_neutral
success
trend_down
trend_up
user
warning
```

`manage.py check` renders each name through the host's `c-icon`. A name that raises is error
`freedom_ls_panel_framework.E010`. A name that renders nothing is warning
`freedom_ls_panel_framework.W003`.

Names that host data supplies (a sidebar item's `icon`, an empty state's `icon`) belong to the host.

## Primitives

Each primitive is a Cotton component in `templates/cotton/`. A host overrides one by putting a template
of the same name earlier in template precedence: a `DIRS` entry beats every app, and apps resolve in
`INSTALLED_APPS` order. The usual override is a thin wrapper that forwards every prop, slot and
`{{ attrs }}` to the host's own component. An override keeps the hooks in its row, because the
framework's JavaScript and stylesheet select on them.

| Primitive | Props | Slots | Hooks an override keeps | Thin wrapper |
| --- | --- | --- | --- | --- |
| `panel-button` (`panel-button.html`) | `variant` `type` `href` `form` `id` `name` `value` `disabled` `autofocus` `aria_label` `aria_describedby` `dropdown` `class` `tone` `size` `icon_left` `icon_right` `loading` `loading_text` | default | classes `panel-btn`, `panel-btn-<variant>`, `panel-btn-sm`; `data-variant`; `data-loading-label` on the loading span | `<c-button :variant="variant" :href="href" :attrs="attrs">{{ slot }}</c-button>` |
| `panel-button-group` (`panel-button-group.html`) | `variant` `class` | default | none | `<c-button-group :variant="variant" :class="class">{{ slot }}</c-button-group>` |
| `panel-chip` (`panel-chip.html`) | `variant` `size` `icon` `class` | default | classes `panel-chip`, `panel-chip-<variant>`, `panel-chip-<size>` | `<c-chip :variant="variant" :size="size" :icon="icon" :attrs="attrs">{{ slot }}</c-chip>` |
| `panel-callout` (`panel-callout.html`) | `level` `title` `class` | default | none | `<c-callout :level="level" :title="title" :class="class">{{ slot }}</c-callout>` |
| `panel-back-link` (`panel-back-link.html`) | `href` `class` | default | the anchor passes `hx-*` attributes through `{{ attrs }}`; `breadcrumbs.html` relies on it | `<c-back-link :href="href" :attrs="attrs">{{ slot }}</c-back-link>` |
| `panel-pagination` (`panel-pagination.html`) | `page_obj` `base_url` `table_id` `sort_by` `sort_order` `search_query` `extra_params` `page_param_name` `push_url` `links` `page_url` `class` | none | the `hx-get`, `hx-target` and `hx-push-url` attributes on each page control; class `panel-pagination` | `<c-pagination :page_obj="page_obj" :base_url="base_url" :table_id="table_id" :links="links" />` |
| `panel-dropdown-menu` (`panel-dropdown-menu.html`) | `trigger` `class` `aria_label` `menu_label` `trigger_variant` `trigger_size` `panel_class` | default; `trigger` as a named slot | `x-data="panelDropdownMenu"`; `x-ref` `menuButton` and `menuPanel`; the `role="menu"` wrapper | `<c-dropdown-menu :aria_label="aria_label" :class="class">{{ slot }}</c-dropdown-menu>` |
| `panel-dropdown-menu-separator` (`panel-dropdown-menu-separator.html`) | none | none | `role="separator"`, which keeps it out of the arrow-key order | `<c-dropdown-menu-separator />` |
| `panel-page` (`panel-page.html`) | `width` `flush` `class` | default | none | `<c-page :width="width" :flush="flush" :class="class">{{ slot }}</c-page>` |
| `panel-date` (`panel-date.html`) | `value` `short` | none | `<time datetime>` | `<c-date :value="value" :short="short" />` |
| `panel-datetime` (`panel-datetime.html`) | `value` | none | `<time datetime>` and the two `whitespace-nowrap` spans | `<c-datetime :value="value" />` |

Notes that do not fit a row:

- `panel-dropdown-menu`: `trigger_variant` and `trigger_size` are the trigger button's `variant` and
  `size`. A wrapper maps them to whatever its own button takes. The framework passes `size="small"` to
  get the small button.
- `panel-callout` is for pages. Inside a panel or a dialog the framework uses `panel-notice`.
- `panel-date` with `short` always renders the day and month ("3 Nov") and no year. `panel-date` and
  `panel-datetime` format with Django's `date` filter (`j M Y`, and `H:i` for the time) in the current
  time zone.

## Reference page

`PANEL_REFERENCE_BASE_TEMPLATE` names the template the DEBUG-only component reference page extends. The
default is `panel_framework/minimal_shell.html`. A host sets its own in settings, as FLS does with
`panel_reference_base.html`.

A template named by the setting defines two blocks:

- `head_title`, the page's `<title>` text.
- `content`, where the reference page renders.

It also loads `panel_framework/js/alpine-components.js` if it is not already part of the host's
scripts. The reference page fills only these two blocks.

Error `freedom_ls_panel_framework.E009` means the setting names a template that does not exist.

The default shell links `panel_framework/css/reference.css`, a compiled file that is gitignored. Build
it with `npm run panel_framework_css`. A fresh checkout's `collectstatic` omits it, and only the
reference page under the minimal shell links it.
