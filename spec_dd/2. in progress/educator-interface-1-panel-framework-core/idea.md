# Panel framework core

Spec 1 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Rework the `freedom_ls/panel_framework` API so it can carry everything the rebuilt educator interface needs and can be handed to a downstream project as a documented, reusable thing. Singular "panel framework". A `Panel` is one class inside it, so don't use the word loosely.

The educator interface is the framework's only consumer today and nothing in it is sacred. This spec cuts it down to a skeleton that exercises the new API: the cohorts, learners and courses sections re-expressed on the new classes, the organisation switcher kept, the cohort course-progress matrix deleted along with its template, its test module and the two `qa_helpers` commands that seed it. Later specs rebuild the sections properly. This one only has to prove the framework works and keep the app booting.

## Why

The framework has real design debt, all of it verified against the current code (see `research_current_structure.md` for the snapshot and `research_panel_framework_surface.md` for the consumer's view):

- A delete action returned from a panel is a guaranteed 500, because `DeleteAction.render` demands a model instance and the panel call site hands it the panel.
- Panels have no permission hook of their own. Visibility is all-or-nothing per instance, so a "history" or "personal details" panel cannot narrow itself to a role.
- A panel's filters have no access to the request, so organisation scoping is split ad hoc between `get_queryset(request)` and `get_filters()`. Three tables today are scoped only by the latter.
- Panels return HTML strings. `InstanceView` and the out-of-band bundle concatenate them in Python, with two `escape()` calls and a live semgrep TODO, and templates re-inject them through six `|safe` sites. A downstream project can replace a panel template by path but cannot wrap or extend one.
- A tab is not a panel, so panels do not compose, a tab set cannot be reused, and tabs have no permission hook.
- Every panel needs an instance, so there is no list-level or dashboard panel.
- The "refresh just this target" idiom is copy-pasted three times, once with a hard-coded target id in consumer code.
- `InstanceDetailsPanel._resolve_field` mangles acronyms with `.title()`, ignores choices, shows no placeholder for empty values, and raises a 500 for a property, a method or an annotation.
- Nothing validates a panel's declared fields until a request hits it.
- On a history-cache miss, htmx sends a request with no target header. The tab dispatch path answers any htmx request with a bare fragment, which htmx then swaps into `<body>`. No response sets `Vary`. Tab switching calls `history.pushState` itself and runs its own `popstate` handler alongside htmx's, so Back can show one tab's content under another tab's URL.

## What is settled

**Framework stays bespoke.** No new dependency, no `INSTALLED_APPS` change. The path dispatcher (`__panels/`, `__tabs/`, `__actions/`), the out-of-band navigation bundle and the fail-closed `check_access` and `authorise_instance` contract stay. They are the reason the framework exists. Wagtail's panel API is the prior art to read, not a dependency to install (`research_wagtail_panel_binding.md`; `research_django_crud_package_landscape.md` covers the other packages and why none fits).

**Bound panels.** Split class-definition-time binding (which model, which fields, which children) from render-time binding (request, instance, base URL). The bound object is built fresh per request from the declared class. Don't copy Wagtail's `clone()`/`clone_kwargs()` chain. A subclass that adds a constructor argument and forgets `clone_kwargs` silently loses it. One typed render signature for panels and actions replaces the positional `(request, base_url, panel_name)` that every override repeats today. Adding render-time context later must not break consumers.

**Composition.** A tab set is a container panel with children. A plain panel stack is too. Children bind through the same call the leaves use, and a container with no visible children is itself hidden. Instance-free panels exist, so a list view and a dashboard can hold panels. A panel bound to a model at class definition is validated at `manage.py check` time by actually binding it, in the style of `admin.E108`, with messages following the precedent `base/app_settings.py` sets with its `E001`.

**One scoping seam.** `get_queryset(request)` is where a table is scoped and the filters dict goes. There is exactly one place to get organisation scoping wrong.

**Permission hook on panels and tabs.** `has_permission(request)` on a panel, mirroring the one on actions. Spec 5 decides what the educator interface puts in it. This spec provides the hook, defaults it to visible, and documents it.

**Template contract.** A panel declares `template_name` as a class attribute and provides context from a method. This is the split Django's `Widget` and Wagtail's `laces` component already use. Containers render their children as templates. Nothing in the framework returns an HTML string or calls `escape()`, and the out-of-band bundle is one rendered template, which closes the semgrep TODO. The `|safe` re-injection sites go with it. Includes pass their context explicitly with `only`. A downstream extends a panel's look in one of two ways, and neither needs a loader trick:
- The default templates every panel renders through come in pairs on the Django admin pattern: a thin leaf, the name a downstream overrides, which extends a differently named base that carries the markup.
- A single panel subclass points `template_name` at its own file, which can `{% extends %}` the framework's template.

The dead near-copies of `panel_container.html`, `instance_details_panel.html` and `list_view.html` under `educator_interface/templates/educator_interface/partials/` go. Nothing references them. Detail in `research_template_contract.md`.

**One targeted-refresh mechanism**, built on Django 6's built-in template partials. A panel template marks its refreshable region with `{% partialdef %}`. A targeted htmx refresh renders `template_name#partial`, and a full render renders the whole template. The table panel, the list view and any consumer use it, and consumer code never hard-codes a target id.

**Field resolution.** Vendor `label_for_field`, `lookup_field`, `display_for_field` and `display_for_value` from `django.contrib.admin.utils`, with the private helpers they call, into the framework rather than import them, so a distributable framework does not depend on `contrib.admin`. The vendored module carries Django's BSD-3-Clause notice. The adaptations:
- The `model_admin` and `form` parameters go.
- Booleans come back as values, and the template renders them with `c-icon` in place of admin's `_boolean_icon` images.
- The `URLField`/`FileField` link rendering stays out. The framework then has no URL-validation code of its own to keep patched when Django ships a security fix there.

Field paths use Django's `__` separator, as querysets do, in place of today's dots. Choices render their display value, empty values show a placeholder honouring the field's `empty_values`, and properties, methods and annotations all resolve. `capfirst` is applied once, at display time, never `.title()`. A test compares the vendored functions against Django's own on a fixed set of inputs and lists the intended divergences, so a Django upgrade that changes `admin/utils.py` shows up. Detail in `research_admin_field_helpers.md`.

**URL state.** View, instance and tab live in the path. Tabs switch through htmx with `hx-push-url`, and the Alpine tab component only shows and hides already-loaded panels. It no longer touches `history` or listens for `popstate`. Every pushed URL renders a full page on a plain GET. Every framework response, on every branch, carries `Vary: HX-Request, HX-Target`. The htmx history cache is turned off (`historyCacheSize: 0`, `historyRestoreAsHxRequest: false`, which htmx's own docs say to always disable). The server also treats `HX-History-Restore-Request` as a full-page load on the tab path as well as the generic one. This also keeps learner data out of session storage. Panel refresh endpoints are never pushed. The mechanics are in `../../1. next/educator-interface-full-polish/htmx-modal-drawer-url-state.md` section 3, extended by `research_tabs_and_history.md`.

**Tab markup.** A tab set is marked up as navigation, not as an ARIA tab widget: `<nav>` with links and `aria-current="page"` on the active one, matching `sidebar_nav.html` and the MOJ sub-navigation component. A tab pushes a URL that renders its own page, which makes it navigation, and a plain nav needs no ARIA keyboard model. Focus stays on the activated link after the swap. A tab switch announces through the existing `announcer.html` live region, which today only the sidebar navigation branch reaches.

**Navigation.** Sidebar links group into sections with headings and optional counts, the "Teaching" and "Administration" shape in `Sidebar.dc.html`. The current-instance disclosure under a section stays. A section can link to a table view, an instance view of a single object (the organisation), or a base view that is just a stack or tab set of panels with no instance. The base view is what spec 10 builds the dashboard on. The host slots its own content above the nav, as the organisation switcher does now.

**Shell.** `_base_interface.html` gains two empty blocks, one for the quick view and one for the modal host. Both sit outside `#main-content` so that navigation never destroys them. Spec 3 fills them. No other shell or `sidePanel` change. The learner course player extends the same shell, so it gets a smoke test. There is no mobile bottom tab bar, and the sidebar sheet stays. The sidebar has seven destinations and a bar holds three to five, and the mockup's "More" slot is the overflow tab Apple's HIG advises against. The mockup's sidebar footer (user, role, settings) goes inside the educator interface's own `sidebar_content` block. Evidence in `research_shell_and_navigation.md`.

**Reference consumer.** The educator interface after this spec has a dashboard placeholder, cohorts, learners and courses, each the smallest thing that proves the API. The delete action on a cohort works from a panel. The old progress matrix is gone. `docs/product/educator-interface.md` gets its "Course-progress matrix" section replaced by one line saying it was removed and reporting follows in a later spec.

**Design.** Match the shell and section layouts in `../../1. next/educator-interface-full-polish/Educator LMS Interface Design/` (`Sidebar.dc.html`, and the desktop and mobile dashboard screens), using FLS tokens and `c-icon`. The component library itself is spec 4. This spec only needs the shell to look right.

**Tests.** The framework's own tests stay green and grow to cover:
- the new API and the `manage.py check` validation;
- `Vary` on the plain, fragment and navigation branches of one URL;
- the history-restore request against a tab URL and a plain instance URL;
- a direct GET of a pushed tab URL.

Playwright proves tab navigation in a browser: Back and Forward through a tab switch keep the URL and the visible tab together, and one click adds one history entry. The "a swap never nests a `section` inside a panel" invariant, asserted today only in `test_data_table_panel_htmx.py`, extends to `test_list_view_refresh_htmx.py` and to a tab's first load.

**Downstream.** The URL shape stays. Any template or partial a downstream might have overridden and that this spec renames goes into upgrade notes with `requires_template_review`. So does the change from dotted to `__` field paths. Any markup change sets `requires_tailwind_rebuild`.

## Out of scope

- The table layer's per-table query state and filters (spec 2), though this spec should not make them harder.
- The modal and the quick view themselves (spec 3), beyond the two reserved blocks. The component library (spec 4). What the permission hook returns for each role (spec 5).
- Any section functionality beyond the skeleton.

## Resources

- `research_current_structure.md`: a dated description of the framework and interface before this spec. Line numbers will drift.
- `research_panel_framework_surface.md`: the framework concern by concern, and the scoping trap.
- `research_django_crud_package_landscape.md`: build versus buy.
- `research_wagtail_panel_binding.md`: Wagtail's `Panel`/`BoundPanel`, visibility, checks, and what to copy or avoid.
- `research_template_contract.md`: where HTML is built in Python today, prior art, and the same-name-extends problem.
- `research_admin_field_helpers.md`: the helpers function by function, licence, drift, and label pitfalls.
- `research_tabs_and_history.md`: how tabs work today, htmx 2 history facts, and the accessibility argument for nav links.
- `research_shell_and_navigation.md`: the shell, the mockups, a gap table, and the bottom-bar evidence.
- `../../1. next/educator-interface-full-polish/htmx-modal-drawer-url-state.md`, section 3 and the pitfalls list.
- Skills: `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`, `fls-dev:multi-tenant`, `fls-dev:testing`, `code-comments`.
