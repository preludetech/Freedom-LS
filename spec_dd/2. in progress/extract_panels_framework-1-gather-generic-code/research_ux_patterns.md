# Research: UX patterns for the pieces being moved

Topic `ux_patterns`. Spec 1 is a refactor: educators must see no change, host developers get a clear
public surface. Rules below come from `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` (the
source of truth for how a panel looks). Web references were recalled, not fetched this run; treat them as
background, not as evidence.

## 1. Behaviours the framework's tests should pin

Each item is a behaviour that moves with the code, so the framework test (not the educator test) owns it.

**Optional-reason confirm dialog (`ReasonMixin`, `ReasonForm`, `reason_field`)**
- Reason is optional: submitting blank succeeds and records an empty reason (spec 2 owns "required").
- The dialog is a modal in `#app-modal` ending in `<c-modal-footer>`: Cancel left, confirm last, full size.
- Without JavaScript the confirmation URL renders the originating page with the modal chrome open over it,
  Cancel a link back.
- Body text is one size; the dialog states what is true now, what the action changes and names the records.
- Validation errors return HTTP 422 for HTMX posts.

**Skeleton-first lazy panels (`LazyBodyPanel`, `render_region`)**
- First response renders `panel-skeleton` at once; the body is fetched afterwards (HTMX) into the same slot.
- Error state: a failed body fetch shows an in-place message, not a blank or a full-page error; the rest
  of the page stays usable.
- Too-large state: the host raises the framework error type; the region shows the message the error
  carries, with no framework import of `reports`. Test with a stub host error, plus one `reports` test that
  its error translates to it.
- No `as_of` value yet (spec 2). Test that the skeleton region has no stamp so spec 2's change is visible.
- Skeleton is the same height class as the loaded body where practical, to avoid layout shift
  (NN/g: https://www.nngroup.com/articles/skeleton-screens/).

**Bulk-action confirmation (generic `BulkAction`/registry, selection bar)**
- Confirm dialog shows the selected count, the action's `sentence`, and `consequences`; a destructive
  action is last in the "More" menu in error text and never takes a button.
- Rows failing `permitted` are skipped with their `skip_reason`; the result is "N changed" then one line
  per skip reason, naming only failed rows, never skipped ones.
- Registry: `bulk_actions_for_table` returns actions in registration order for that table key only;
  unknown table returns an empty list; duplicate registration behaviour is pinned (error or documented).
- First 4 permitted non-destructive actions are promoted to buttons; the rest go under More.
- Changing page, sort or filters clears the selection (Alpine `tableSelection`, browser test on a stub).
- "Select all N" flips to "Deselect all"; "Clear" empties the selection.

**"Show inactive" toggle and preset period filters**
- Toggle: off by default, the default state is not written to the URL; on adds one parameter; the widget
  checked state reflects the URL; toggling back drops the parameter; other tables' parameters are untouched
  (each table has its own `TableQuery` slice).
- Period filter: presets (7/30/90 days etc.) apply a window on the named field; the active preset is
  shown as an applied chip (`panel-applied-filter`); choosing it again or "Clear all" removes it;
  an unknown or tampered value in the URL is ignored, not a 500; an empty page after filtering shows the
  empty state.
- Filters survive search, sort and paging in the URL, so a page can be bookmarked and back/forward work
  (htmx `hx-push-url`: https://htmx.org/attributes/hx-push-url/). A filter change resets page to 1.
- Boundary: the preset window is computed against the clock; use a frozen time in the test.
- Constructor shape (open question): whichever is chosen, a parity test should build every FLS table's
  current filter and assert the same queryset and URL output.

**Side panels / quick views (`sidePanel`, `quick-view-trigger`, `modal-trigger`)**
- `#quick-view` opens with `show()`, never `showModal()`: no scrim, page behind stays tappable.
- Header with a title and close control (`aria-label="Close"`); closes on Escape and on the close control;
  focus returns to the trigger. On phones it rises from the bottom. No horizontal overflow at 375px.
- Triggers are `size="small"`; `modal-trigger` targets `#app-modal`, `quick-view-trigger` targets the drawer.
- Moving `sidePanel` into the framework JS: test it by name from the framework's registration check.

**Menu badge counts that refresh on events (`refreshTimer`, `sidebar_nav`)**
- Count renders in the server response, so it is correct without JavaScript.
- It refreshes on a timer and on each event name the nav item carries (e.g. a host-supplied event on
  `body`); a stub nav item with a made-up event name proves the framework names no host event.
- A zero count hides the badge (or shows none) consistently; a failed refresh keeps the last count
  rather than blanking it; the timer stops when the tab is hidden if the current code does this (pin
  what it does today, do not add).
- Badge has an accessible name ("3 unread"), not only a number.

## 2. Developer-experience patterns for the public surface

- **`__all__` per public module** (decided in answers.md) plus a test that every name a host imports is
  listed; underscore the `views.py` helpers. Keep `__all__` sorted into groups with a comment so the
  promise is readable. Reference: https://docs.python.org/3/tutorial/modules.html#importing-from-a-package
- **One import path per name**: the moved names exist only at the new location (no aliases, per settled
  decision), so a stale import fails at import time, not at runtime.
- **Fail loudly at startup, not at render**: Django system checks
  (https://docs.djangoproject.com/en/stable/topics/checks/) are the idiom for "host forgot to register
  something" (a bulk action registered for an unknown table, a nav item with no event list where a count
  is declared, the housekeeping callable never scheduled can only be documented, not checked).
  Within scope, prefer `ImproperlyConfigured`/`ValueError` with a message naming the class, the missing
  attribute and the fix.
- **Error messages say what to do**: e.g. "LazyBodyPanel 'X' has no template; set `template_name`".
  Test the message text by key phrase.
- **Template failures**: a missing cotton component or Alpine name must surface in tests, not as a silent
  empty element. The planned "every Alpine name used is registered in `alpine-components.js`" test is the
  right shape; extend the failure message to name the template and the missing component.
- **Subclass contract is small and documented**: the generic bulk action has four hooks
  (`permitted`, `skip_reason`, `perform`, `sentence`/`consequences`). A docstring on each says when it is
  called, what it may return, and that it must not raise for a normal skip. A minimal stub subclass in the
  framework tests doubles as the worked example.
- **Callable not command for housekeeping**: document the signature, idempotence (safe to run twice) and
  suggested cadence in the docstring; test idempotence and that a run in `running` past the threshold is
  reaped.
- **Discoverability**: a single documented module or the package `__init__` docstring listing the
  groups (tables, panels, actions, filters, bulk, lazy, reasons, housekeeping). Pairs with
  the skill's "What it is" list, which needs the new modules added.

## 3. Risks and cheap mitigations

- Behaviour drift in a move: keep the educator Playwright tests that cover end-to-end flows as the
  cross-check, and move (not rewrite) unit tests so assertions are unchanged.
- Skill text must be updated: SKILL.md lists modules and components and will be stale on the new files.
- New `freedom_ls` imports added to the framework by the moved code must be listed for spec 3.

Sources (not fetched this run):
- https://www.nngroup.com/articles/skeleton-screens/
- https://htmx.org/attributes/hx-push-url/
- https://docs.djangoproject.com/en/stable/topics/checks/
- https://docs.python.org/3/tutorial/modules.html#importing-from-a-package
- Repo: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`

status: ok · reason: complete; web references recalled not fetched
