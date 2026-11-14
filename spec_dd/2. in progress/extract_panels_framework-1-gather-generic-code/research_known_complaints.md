# Research: known complaints about this kind of work

Topic: `known_complaints`. Question: what do users commonly complain about with reusable Django UI/table
frameworks and extractions from a monolith, and what should the spec do to avoid each?

Evidence grading: **[sourced]** = found in a fetched/searched source below. **[general]** = common pattern
from general knowledge of these projects, not verified in this pass (a search turned up no direct issue).
Treat [general] items as hypotheses to check, not citations.

## 1. Alpine component registration and load order [sourced]

Complaint: `Alpine is not defined`, `Alpine.data is not a function`, or `x-data` name "not defined".
Causes in the threads: `Alpine.data` called outside an `alpine:init` listener; the registering script loads
after Alpine, or a non-deferred inline script runs before Alpine exists; a missing `defer`; bundler setups
where `window.Alpine` is set too late; a registered callback that returns nothing (`() => {}` instead of
`() => ({})`).

Spec should:
- Require every framework component to register inside `document.addEventListener("alpine:init", ...)` in
  `alpine-components.js`, and state that the file loads (deferred) before the Alpine script. Document the
  order as part of the host contract (hand the load-order rule to spec 4, but test it here).
- Keep the planned check that every Alpine name used in a framework template is registered in the
  framework's `alpine-components.js`. Moving `sidePanel` and `refreshTimer` there removes the cross-app
  case (names registered in `base` or `comms` JS), which is exactly the failure a host sees when it
  installs the framework alone.
- Add a browser test that loads a stub page with the framework JS only and fails on any console error
  such as `Alpine Expression Error` or `... is not defined`.
- Moved components must return an object; assert in the browser tests that each initialises.

Sources:
- https://laracasts.com/discuss/channels/general-discussion/alpinejs-x-data-function-fails-to-load
- https://dev.to/tylerlwsmith/using-alpines-persist-plugin-in-a-separate-javascript-file-462n
- https://git.zegbsdukh.workers.dev/alpinejs/alpine/discussions/1705
- https://github.yxlr123.workers.dev/alpinejs/alpine/discussions/4494

## 2. Table frameworks: subclassing and inherited settings (django-tables2) [sourced, partly general]

Complaints recorded in its docs and changelog: a child table's `Meta` silently loses the parent's settings
unless it explicitly extends the parent `Meta`; explicitly defined column options not preserved over
inheritance (fixed in 1.2.2); pagination wrongly disabled depending on which mixin/view combination is
used (1.2.4, 2.1.1); `visible=False` columns suddenly appearing in exports (2.1.0) and needing a separate
`exclude_from_export`. Pattern: subclass-time behaviour that is implicit and changes across versions.

Spec should:
- Test subclassing of the framework table, panel and bulk-action classes from a host (educator-style
  subclass that overrides `permitted` / `perform`) with no `Meta`-style inheritance traps; prefer plain
  class attributes and documented hooks over nested `Meta`.
- State in the spec which attributes a subclass may override (the hook list) and put that in the
  public-surface docs.
- Cover export/visibility and pagination in the framework's own tests, not only via the educator interface.

Sources:
- https://github.com/jieter/django-tables2/blob/v2.2.1/CHANGELOG.md
- https://django-tables2.readthedocs.io/en/stable/pages/CHANGELOG.html
- https://github.com/bradleyayers/django-tables2/blob/966a41c25e242652bae982e71fc3cdd9ed4a66bf/docs/pages/api-reference.rst

## 3. Filters whose URL state breaks (django-filter, django-tables2) [general]

No specific issue was surfaced by search. Recurring pattern from these libraries: filter changes drop the
other querystring params (sort, page, search), page number survives a filter change and shows an empty page,
toggling a filter off leaves `?param=` junk or `False` strings, and bookmarked URLs break when a param is
renamed.

Spec should:
- Test URL toggling in the filter tests (already in scope): turning a toggle on/off adds/removes exactly its
  own param and preserves `sort`, `search`, others; changing any filter resets `page`.
- Keep `ShowInactiveFilter` / `AuditPeriodFilter` param names and values unchanged (a renamed param is a
  breaking bookmark change); test the old URLs still resolve to the same state.
- Test an invalid or unknown param value (bad preset, bad date) renders a defined fallback rather than a 500.

## 4. Admin/UI frameworks: upgrade breakage and template overrides (django-unfold, Django admin) [sourced]

Complaints: custom templates, widgets and CSS break on upgrade; widget names changed between releases;
class names and template structure are de facto API; Django 5.2 moved admin object tools out of the
`content` block, breaking overrides (ticket 36331). Lesson: what hosts override is the real API, and it is
rarely declared.

Spec should:
- Declare which templates/blocks/partials a host may override (the moved `reason_field` partial, lazy-panel
  templates, `modal-trigger`/`quick-view-trigger`) versus private ones; list them with the public surface.
- Do not rename template paths, block names or cotton component names while moving code without a note;
  keep the list of moved template paths in the spec so spec 4/5 see them.
- Ship a changelog-style note of every moved symbol (old path to new path), since no aliases are kept.

Sources:
- https://www.mintlify.com/unfoldadmin/django-unfold/resources/migration-guide
- https://www.mintlify.com/unfoldadmin/django-unfold/resources/faq
- https://code.djangoproject.com/ticket/36331?format=tab
- https://www.mintlify.com/unfoldadmin/django-unfold/concepts/architecture

## 5. Unclear public API and breaking imports [general, supported by 2 and 4]

Complaint: hosts import from deep internal modules (here `views.py` with about 25 helpers), then a refactor
breaks them; no one knows what is promised.

Spec should:
- Follow the settled answer: `__all__` per public module, underscore-prefix or exclude `views.py` helpers,
  and a test that every name a host imports is listed. Make that test also run the reverse: import every
  `__all__` name, so a stale entry fails.
- Because no aliases are kept, grep the whole repo (including templates, `INSTALLED_APPS` strings, dotted
  paths in settings, migrations, and string-based registries) for old paths, not just `import` lines.
  Migrations that reference moved classes by dotted path are the usual miss.

## 6. Overly coupled base classes that are hard to subclass [general, supported by 2]

Complaint: a generic base that still knows about the host (organisation scoping, notifications, `request.user`
shape) forces hosts to override large methods or monkeypatch.

Spec should:
- Keep the generic `BulkAction` free of organisation scoping, `can_on_any` and notification calls; expose
  them as narrow overridable hooks (`permitted`, `skip_reason`, `perform`, `sentence`, `consequences`) with
  defaults that work with no host code.
- Prove it with a framework-only test: a stub subclass in the framework tests that uses no FLS models, plus
  the educator subclass as the cross-check.
- Registry: test duplicate registration, unknown table key, and registration order, since global registries
  are a classic source of import-order bugs. Avoid registration as an import side effect that depends on
  which app imported first; test that it works when the host module is imported last and first.
- The framework error type replacing `ReportTooLargeError` should be a plain exception carrying the
  message; do not make it require a host class.

## 7. HTMX lazy-load regions [general]

Recurring complaints: skeleton shows forever when the request fails or returns an error status (HTMX
does not swap 4xx/5xx by default); the loading region flashes or never reappears after a swap; CSRF header
missing on lazily loaded fragments; the lazy trigger fires before Alpine has initialised; errors swallowed
silently.

Spec should:
- For the moved `LazyBodyPanel` / `render_region`, specify and test the failure path: the framework error
  type produces a visible message in the region (with the status code the HTMX config swaps, per the
  project's 422 rule), and a generic server error shows a retry or error state, not a permanent skeleton.
- Test the region both on first load and after a refresh (`listRefresh`, `headerRefresh`).

## 8. Stuck background-job rows never reaped [general]

Recurring complaint for any app that tracks job state in a table: a worker dies, the row stays `running`
forever, counts and UI lock up, and the host does not know a sweeper exists or must be scheduled.

Spec should:
- Make the housekeeping callable's contract explicit: what it reaps (unpicked, orphaned, stale previews,
  retention), the age thresholds as parameters with documented defaults, that it is idempotent and safe to
  run concurrently, and that it returns a summary (counts) so the host can log it.
- Test with frozen time at each threshold boundary (just under, just over), a run in each status, and a
  second call doing nothing.
- Say in the public docs that a host must schedule it (the idea says no management command), and add a
  loud pointer in the framework README/install section, since "never scheduled" is the realistic failure.
- Keep `LearnerImport` going through the `RunRecord` protocol; test the protocol with a stub record type.

## 9. Bulk actions (Wagtail) [general]

Complaints about Wagtail bulk actions seen in the wild: actions that act on a different set than the one
selected when the list is filtered or paginated; permission checks that differ between the confirm page and
the execution; hosts unable to add actions without touching core registries.

Spec should:
- Test that `permitted` is evaluated at confirm time and again at perform time (the idea keeps behaviour
  unchanged; assert it rather than assume).
- Keep selection scope explicit (`tableSelection` tests with selected rows across a filter change).

## 10. Cotton component libraries [general]

Complaints: components not found when the library is installed as an app (template dirs and cotton
autodiscovery depend on `APP_DIRS` and app order); attribute passing and slot differences between cotton
versions; undocumented required attributes; components that silently render nothing when a required attr is
missing.

Spec should:
- Directly test every cotton component rendered with its minimal required attrs and with a missing
  required attr, so behaviour is defined and documented. Moving `modal-trigger` and `quick-view-trigger`
  from `base` to the framework changes where cotton finds them; test they resolve from the framework app
  (and confirm there is no same-name component left in `base` that shadows them).
- Leave the "resolves with only the package installed" test to spec 4 as the idea says, but list in this
  spec's handoff every FLS primitive and include the moved templates still depend on.

## 11. Extracting code from a monolith [general]

Complaints from comparable extractions: hidden imports surface late; tests that only passed because the
host app was installed; moved tests left behind duplicating coverage; behaviour drift during "just a move".

Spec should:
- Make it two-step per piece: move unchanged, then generalise (filters), with the existing tests passing
  after the move before any change.
- Move tests with the code and keep in `educator_interface` only what it still owns, as the idea says;
  record any new `freedom_ls` import the moved code needs (the idea requires listing them for spec 3).
- Grep checks for leftovers: no remaining reference to old paths, no `comms`/`educator` event or class name
  inside the framework (`conversationChanged`, `refreshTimer` from `comms`).

## Summary of the spec actions most likely to matter

1. Alpine registration inside `alpine:init`, one registry file, a template-vs-registry check, a
   console-error browser test.
2. Declared public surface with a forward and reverse `__all__` test, plus a whole-repo grep for old paths
   including dotted strings and migrations.
3. A housekeeping callable with parameterised thresholds, boundary tests, idempotency and a scheduling note.
4. A framework-only stub subclass test for the generic bulk action and registry.
5. Failure-path tests for lazy regions.
6. URL-state tests for filters (preserve other params, reset page, unchanged param names).

status: ok
