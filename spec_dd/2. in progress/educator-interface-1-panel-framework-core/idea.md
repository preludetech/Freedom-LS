# Panel framework core

Spec 1 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Rework the `freedom_ls/panel_framework` API so it can carry everything the rebuilt educator interface needs and can be handed to a downstream project as a documented, reusable thing. Singular "panel framework". A `Panel` is one class inside it, so don't use the word loosely.

The educator interface is the framework's only consumer today and nothing in it is sacred. This spec cuts it down to a skeleton that exercises the new API: the cohorts, learners and courses sections re-expressed on the new classes, the organisation switcher kept, the cohort course-progress matrix deleted along with its template, its test module and the two `qa_helpers` commands that seed it. Later specs rebuild the sections properly. This one only has to prove the framework works and keep the app booting.

## Why

The framework has real design debt, all of it verified against the current code before this idea was written (see `research_current_structure.md` for the snapshot and `research_panel_framework_surface.md` for the consumer's view):

- A delete action returned from a panel is a guaranteed 500, because `DeleteAction.render` demands a model instance and the panel call site hands it the panel.
- Panels have no permission hook of their own. Visibility is all-or-nothing per instance, so a "history" or "personal details" panel cannot narrow itself to a role.
- A panel's filters have no access to the request, so organisation scoping is split ad hoc between `get_queryset(request)` and `get_filters()`. Three tables today are scoped only by the latter.
- Panels return HTML strings. A downstream project can replace a panel template but cannot wrap or extend one, and the view hand-assembles markup in Python behind a live semgrep TODO.
- A tab is not a panel, so panels do not compose, a tab set cannot be reused, and tabs have no permission hook.
- Every panel needs an instance, so there is no list-level or dashboard panel.
- The "refresh just this target" idiom is copy-pasted three times, once with a hard-coded target id in consumer code.
- Field labels come from a home-grown resolver that mangles acronyms and raises a 500 for a property, a method or an annotation.
- Nothing validates a panel's declared fields until a request hits it.
- On a history-cache miss, htmx sends a request with no target header and the view answers with a bare fragment, which htmx then swaps into `<body>`. No response sets `Vary`. Tab switching pushes its own history entries outside htmx, so Back can show one tab's content under another tab's URL.

Wagtail's panel API is the right prior art and the wrong dependency. Read it, do not install it. `research_django_crud_package_landscape.md` covers the alternatives and why none fits.

## What is settled

**Framework stays bespoke.** No new dependency, no `INSTALLED_APPS` change. The path dispatcher (`__panels/`, `__tabs/`, `__actions/`), the out-of-band navigation bundle and the fail-closed `check_access` and `authorise_instance` contract stay. They are the reason the framework exists.

**Bound panels.** Split class-definition-time binding (which model, which fields, which children) from render-time binding (request, instance, base URL). One typed render signature for panels and actions replaces the positional `(request, base_url, panel_name)` that every override repeats today. Adding render-time context later must not break consumers.

**Composition.** A tab set is a container panel with children. A plain panel stack is too. Instance-free panels exist, so a list view and a dashboard can hold panels. A panel bound to a model at class definition is validated at `manage.py check` time, following the precedent `base/app_settings.py` sets with its `E001` messages.

**One scoping seam.** `get_queryset(request)` is where a table is scoped and the filters dict goes. There is exactly one place to get organisation scoping wrong.

**Permission hook on panels and tabs.** `has_permission(request)` on a panel, mirroring the one on actions. Spec 5 decides what the educator interface puts in it. This spec provides the hook, defaults it to visible, and documents it.

**Template contract.** Panels declare a template name and provide context. The panel container renders them. No `get_content() -> str`, no string concatenation in views, no `escape()` in Python. The semgrep TODO is closed or consciously recorded as accepted.

**Field resolution.** Vendor the label and display helpers from `django.contrib.admin.utils` into the framework rather than import them, so a distributable framework does not depend on `contrib.admin`. Choices render their display value, empty values show a placeholder, properties and methods work.

**One targeted-refresh primitive**, used by the table panel, the list view and any consumer. No hard-coded target ids in consumer code.

**URL state.** View, instance and tab live in the path. Tabs switch through htmx with a pushed URL, and the Alpine tab component only shows and hides already-loaded panels. Every pushed URL renders a full page on a plain GET. Every framework response carries `Vary: HX-Request, HX-Target`. The htmx history cache is turned off and history restore requests are treated as full-page loads, which also keeps learner data out of session storage. Panel refresh endpoints are never pushed. The mechanics, with sources, are in `../educator-interface-full-polish/htmx-modal-drawer-url-state.md`, section 3.

**Navigation.** Sidebar links group into sections with headings and optional counts. A section can link to a table view, an instance view of a single object (the organisation), or a base view that is just a stack or tab set of panels with no instance. The base view is what spec 10 builds the dashboard on. The host slots its own content above the nav, as the organisation switcher does now.

**Reference consumer.** The educator interface after this spec has a dashboard placeholder, cohorts, learners and courses, each the smallest thing that proves the API. The delete action on a cohort works from a panel. The old progress matrix is gone. `docs/product/educator-interface.md` gets its "Course-progress matrix" section replaced by one line saying it was removed and reporting follows in a later spec.

**Design.** Match the shell and section layouts in `../educator-interface-full-polish/Educator LMS Interface Design/` (`Sidebar.dc.html`, and the desktop and mobile dashboard screens), using FLS tokens and `c-icon`. The component library itself is spec 4; this spec only needs the shell to look right.

**Tests.** The framework's own tests stay green and grow to cover the new API, the `Vary` header, the history-restore branch and tab navigation through htmx. The two Playwright modules keep their invariant that a swap never nests a `section` inside a panel.

**Downstream.** The URL shape stays. Any template or partial a downstream might have overridden and that this spec renames goes into upgrade notes with `requires_template_review`. Any markup change sets `requires_tailwind_rebuild`.

## Open until the spec

- Whether `_base_interface.html` and `sidePanel` in `base` need to change. The learner course player extends the same shell, so a change there is a change to both. If the answer is yes, keep it minimal and test the course player.
- The mobile bottom tab bar the mockups show. Default no; the sidebar sheet stays. If yes, it is a shell change and belongs here, not in a later spec.
- Whether the quick view and modal hosts (spec 3) need slots in the layout that this spec should reserve now. Probably one block each in the interface template. Cheap to add here, awkward to retrofit.

## Out of scope

- The table layer's per-table query state and filters (spec 2), though this spec should not make them harder.
- The modal and the quick view (spec 3), the component library (spec 4), what the permission hook returns for each role (spec 5).
- Any section functionality beyond the skeleton.

## Resources

- `research_current_structure.md`, a dated description of the framework and interface as they stood before this spec. Paths in it have been corrected; line numbers will drift.
- `research_panel_framework_surface.md`, the framework concern by concern and the scoping trap.
- `research_django_crud_package_landscape.md`, build versus buy.
- `../educator-interface-full-polish/htmx-modal-drawer-url-state.md`, section 3 and the pitfalls list.
- Skills: `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`, `fls-dev:multi-tenant`, `fls-dev:testing`, `code-comments`.
