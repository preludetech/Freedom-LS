# Research: best practices for a small editable list panel (`EditableListPanel`)

Question: established practice for a short editable list of child records in server-rendered Django + HTMX: dialog add/edit, confirmed remove, parent-scoped per-entry URLs, server-side cap, accessibility, empty state, event-driven refresh of other panels.

Scope note: general web practice, not a read of the panel framework code. The spec author must reconcile these with `fls-dev:panel-framework` (the source of truth for FLS).

## 1. Parent-scoped per-entry URLs (IDOR, 404)

- OWASP: check object-level authorization on every read/create/update/delete, and scope the lookup to the owner (query within the parent's data, not by global id). A UUID is defense in depth only, never a substitute for the check.
- OWASP on 404 vs 403: a fetch-then-check-owner flow leaks existence (403 vs 404). When existence is sensitive, do the scoped query and return the same response for "missing" and "not yours": 404.
- Django form: resolve the entry with `get_object_or_404(entries_queryset_for(parent), pk=pk)`. The consumer's entries query, filtered by the parent, is the single scope. Never `get_object_or_404(Model, pk=pk)` followed by a check.
- Apply the same scoped lookup to GET (form dialog), POST (save) and the delete confirmation GET and POST. Every verb needs it, not only the mutating ones.
- Do not accept the parent id or an entry id from the POST body. Take the parent from the URL/panel context, and bind the new entry to it server-side (set the FK in the save step, exclude it from the form fields).
- Test with two parents: a user cannot GET/POST/DELETE an entry of the other parent (expect 404), and a non-entry pk gives 404.
- Use the same 404 for a wrong-parent pk and a nonexistent pk. Do not distinguish them.

## 2. Add/edit in a dialog

- Use the native `<dialog>` with `showModal()`: it provides focus trapping, Escape to close, inert background and top-layer stacking. Prefer one dialog form template for add and edit (same form, title differs: "Add X" / "Edit X").
- Dialog content is fetched by HTMX (GET returns the form), submitted by HTMX (POST). On validation failure return the form re-rendered with errors and HTTP 422 (also the project rule), swapping only the dialog body so it stays open and keeps user input. On success, close the dialog and refresh the list.
- Success pattern: respond with `HX-Trigger` carrying the list's event (and `HX-Trigger-After-Swap` if something must run after the swap). Events fire on the target and bubble to `body`, so listeners elsewhere can use `hx-trigger="eventName from:body"`. The JSON form carries a payload (e.g. which entry id changed, used for focus). Headers are ignored on 3xx responses, so do not redirect on success.
- Redisplay of a form with errors: move focus to an error summary or the first invalid field, with `aria-invalid` and `aria-describedby` linking errors (standard form-error practice).

## 3. Remove with confirmation

- Prefer a server-rendered confirmation dialog (GET returns "Remove <entry title>?" with Cancel/Remove, POST/DELETE performs it) over `hx-confirm` / `window.confirm`. It is stylable, testable, accessible and can name the entry.
- Destructive confirm: WAI-ARIA APG says to put initial focus on the least destructive action (Cancel) when the step is not easily reversible, and suggests the Alert Dialog pattern (`role="alertdialog"`) for this.
- Use POST or DELETE with CSRF (project sets `X-CSRFToken` globally); never a GET that deletes.
- Removing an already-removed entry (double submit): the scoped lookup gives 404. Consider treating it as a no-op that still refreshes the list, since a stale second tab otherwise sees a bare error. A spec decision.
- Cheap undo is not needed for a list of five; confirmation is the safeguard.

## 4. Optional max count, enforced server-side

- The UI hiding the Add button is a convenience only. The add GET (dialog) and the add POST must both refuse at the cap (e.g. 409 or 422 with the "limit reached" message, or 403), because a stale page or a crafted request can still reach the endpoint.
- Count inside a transaction to limit races: lock the parent row (`select_for_update()` on the parent) then count and insert, so two concurrent adds cannot both pass. For a small personal list a simple check is often accepted, but the lock is cheap. The edit path must not be blocked at the cap (the cap is for adds only), and remove must re-enable Add.
- At the cap, replace Add with a short text line (answers.md decision) rather than a disabled button: disabled buttons are skipped by keyboard focus and give no reason to screen reader users. Put the line where the button was.
- If the cap is lowered after data exists (more entries than the cap), existing entries stay editable and removable and only Add is blocked. State this.

## 5. Accessibility

Buttons naming their entry:
- Every per-entry button needs a unique accessible name, e.g. visible text "Edit" with `aria-label="Edit <title>"` or visually hidden text `Edit <span class="sr-only">Acme, Engineer</span>`. Prefer visually hidden text or `aria-labelledby` pointing at the entry title plus the button, so the visible label is contained in the accessible name (WCAG 2.5.3 Label in Name). Icon-only buttons need an `aria-label`.
- The list is a real `<ul>`/`<li>` so screen readers announce "list, N items". Each entry may be an `<li>` with title (heading or strong) and detail.
- The entry title must be escaped (autoescape) inside any `aria-label`.

Dialog:
- APG: on open, focus moves inside the dialog (first field for forms; Cancel for destructive confirms). Tab cycles inside, Escape closes, a visible Cancel/Close button exists. Dialog has an accessible name via `aria-labelledby` pointing at its heading.
- On close, focus returns to the invoker by default. Exception per APG: if the invoker no longer exists, move to a logical element.

Focus management after each action (HTMX has no built-in focus helpers; handle in a swap/settle listener, because the swapped-out element's focus is lost):
- Cancel add/edit: focus returns to the Add or the entry's Edit button (default `showModal()`/`close()` behaviour, provided the invoker survives).
- Add success: the list is re-rendered, so the original invoker (Add button) is replaced. APG allows moving to a more logical element: focus the new entry (give the new `<li>` `tabindex="-1"` and focus it) or return to the Add button. Pick one and make it consistent.
- Edit success: the entry is re-rendered; focus the entry's Edit button again (stable ids like `entry-<pk>-edit`) or the entry `<li>`.
- Remove success: invoker is gone. Move focus to the next entry's heading/button, else the previous, else the empty state or Add button (`tabindex="-1"` on the list heading/container as a fallback). Never let focus fall to `<body>`.
- Reliable technique: re-render the list with `hx-swap` and a stable id, then in an `htmx:afterSettle` listener (or the HX-Trigger payload) focus the element by id.
- Optionally use htmx's own preserving of focus for elements with an `id` that survive a swap (htmx restores focus to an element with the same id after a swap). It does not help for removed elements.

Live announcements:
- A visually hidden `role="status"` (polite, `aria-atomic="true"`) region that exists in the DOM before it is updated, with text such as "Work experience added" / "removed". A live message informs; it does not replace moving focus when focus is lost. Do not use `role="alert"` for routine success. If focus is moved to an element whose name says what happened, the announcement may be redundant, so avoid doubling.
- Changing live region content must be injected after load (an element inserted with content already in it is often not announced). Keep the region outside the swapped fragment, or swap its inner text.
- The limit-reached line may be a static line; announce changes via the status region.

## 6. Empty state

- Show a real empty state (text such as "No entries yet" plus the Add button) instead of an empty list, and do not render an empty `<ul>` (screen readers announce an empty list). Consumer may supply the wording. At the cap with zero entries is impossible (cap >= 1), so no conflict.
- Empty-state element becomes the focus fallback after the last entry is removed.

## 7. Refreshing other panels via events

- Server sends `HX-Trigger: {"<list-event>": {...}}` on a successful add/edit/remove. Other panels declare `hx-trigger="<list-event> from:body"` and re-fetch their own content (panel framework `success_events` / `refresh_events`). Fire the event after the change is committed (use `transaction.on_commit` if the HX-Trigger is emitted before commit in an atomic request).
- The list itself should also refresh by that mechanism (or by direct response swap), not both, to avoid a double fetch. One refresh path is easier to reason about.
- Include enough payload (e.g. the affected pk) for the focus handler, but keep panels' refresh not dependent on the payload.
- Events fired with `HX-Trigger` fire on the requesting element; if that element is swapped away before the listener, the event may still bubble to `body`, but a listener using `from:body` is the reliable form.

## 8. Other practice

- Order and summaries come from the consumer's query and callable (answers.md). Tie-break order (e.g. add `-pk`) in the consumer's query so re-render order is stable; mention in the spec as consumer guidance.
- N+1: the summary callable runs per entry, so the consumer's query should use `select_related`/`prefetch_related`. The framework can document this.
- Idempotency: double-clicking Save creates two entries. Disable the submit button during the request (`hx-disabled-elt="this"`) as cheap protection.
- Framework invariant tests worth writing: wrong-parent pk gives 404 for each verb; cap refused on both GET and POST; invalid POST returns 422 with dialog kept; each per-entry button has a unique accessible name; empty state renders; success sends the configured events; remove needs a POST not a GET.

## Sources

- OWASP IDOR Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- W3C WAI-ARIA APG, Dialog (Modal) pattern: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- HTMX HX-Trigger response headers: https://htmx.org/headers/hx-trigger/
- Flavio Copes, HTMX focus after a swap: https://flaviocopes.com/courses/htmx/focus-after-a-swap/
- Hypermedia Components, confirm-action recipe (native dialog): https://hypermedia-components.ichimura-12c.workers.dev/hypermedia-components/recipes/confirm-action/
- Drupal HTMX migration, accessibility (no built-in focus helpers, live regions with aria-atomic): https://camoa.github.io/dev-guides/drupal/ajax-htmx-migration/accessibility-migration
- Announcing dynamic updates with ARIA live regions (Kavanagh): https://johnkavanagh.co.uk/articles/announcing-dynamic-updates-with-aria-live-regions/
- Minnesota state accessibility guide, focus management (confirm modal focus on Cancel, return to trigger): https://accessibilityuniversity.dhs.state.mn.us/FocusManageP2

Caveat: the Section 4 row-locking advice, the "Label in Name" reference, the htmx id-based focus preservation and the `transaction.on_commit` point come from general knowledge, not a fetched page. Verify them before relying on them in the spec.

status: ok
