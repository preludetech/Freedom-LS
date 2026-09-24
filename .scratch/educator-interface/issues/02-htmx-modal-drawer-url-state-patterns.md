# Modal, drawer and URL-state patterns for HTMX

Type: research
Status: resolved

## Question

What are the current best-practice patterns, with HTMX 2.x + Alpine.js + Django, for:

1. a **non-modal right-hand quick-view drawer** that doesn't block the page, gets its content swapped in place over HTMX, cancels in-flight requests, caches re-opens, and flips to a modal on mobile;
2. a **modal dialog** (native `<dialog>` vs Alpine vs HTMX-loaded), including focus management, nested forms returning 422, and closing on success;
3. **URL state** for a nested admin UI: which view, tab and panel is open, plus per-table filter, sort, search and page, with several tables on one page. Cover `hx-push-url` vs `hx-replace-url`, querystring prefixing, back/forward and full-page-load fallback, and whether an open drawer or modal should be in the URL.

For each, give the recommended pattern, notable pitfalls, and any small library worth depending on (FLS avoids new deps and `INSTALLED_APPS` changes, see the panel-framework draft's Notes).

Prior material to extend, not redo: `spec_dd/1. next/educator-interface-full-polish/educator-interface-quick-view-panel/research_ux_patterns.md` and `research_ux_pitfalls.md`, and `structure/idea.md`.

## Answer

Checked against htmx 2.0.8 (what `_base.html` loads, source read directly), Alpine 3.15.8 CSP build, and Django 6.0. The UX and ARIA decisions in the prior research still stand; this adds the mechanics.

**1. Quick-view drawer.** One `<dialog id="quick-view">` in the interface layout, outside `#main-content`, run by a `quickView` `Alpine.data` component modelled on the existing `sidePanel` (ideally sharing its code). Open it with `show()` on desktop and `showModal()` on mobile. `showModal()` gives inert background, focus containment, Esc and top layer natively, so no manual `inert` handling. A dialog can't change modality while open (it throws `InvalidStateError`), so on a breakpoint change, close and reopen. Triggers come from one cotton component: `hx-get` the fragment, `hx-target="#quick-view-body"`, `hx-swap="innerHTML"`, `hx-sync="#quick-view-body:replace"` (a new click aborts the one in flight), `hx-push-url="false"`. The component opens the drawer and shows the skeleton on `htmx:beforeRequest`, and uses `htmx:confirm` to toggle (same trigger closes) and to reopen without refetching (closing hides the drawer without clearing it). It refetches on the `HX-Trigger` domain events that mutations already send. No HTTP caching. Note that `show()` moves focus into the dialog (HTML spec), so if focus should stay on the cell, refocus the trigger straight after `show()`. Restore focus on close yourself. Esc needs a keydown handler on desktop. The endpoint returns a fragment; a non-HTMX GET redirects to the entity's full page.

**2. Modal.** One shared native `<dialog id="app-modal">` in the layout, opened with `showModal()`, content loaded on demand (`hx-get` into `#app-modal-body`, `showModal()` on `htmx:afterSwap`), run by an `appModal` component. This replaces `cotton/modal.html`, which has no focus move, trap or return, and stops forms being rendered eagerly into the page. The form uses `hx-target="this" hx-swap="outerHTML"`. On 422 (already allowed by the global `beforeSwap` handler, and htmx 4's default) focus the error summary or the first `aria-invalid` field, because the swap drops focus. On success, return 204 or 200 plus `HX-Trigger: {"closeModal": …, "<domainEvent>": …}`. Use `HX-Location` targeting `#main-content`, not `HX-Redirect`, when the next step is navigation. Initial focus follows APG: `autofocus` on the first field, the Cancel button for destructive actions, the heading for long content. Clear the body on close, lock scroll with `html:has(dialog:modal)`, and don't nest modals. Heavy flows such as CSV import are pages. No `@alpinejs/focus` needed.

**3. URL state.** View, instance and tab go in the path. Panel doesn't go in the URL (`__panels/` stays a fetch endpoint). Table state goes in the query string, prefixed with a stable per-table key: `<key>-sort` (with `-` for descending), `<key>-page`, `<key>-q`, `<key>-<filter>`. The table's DOM id comes from the same key. Links are built in Python from `request.GET.copy()`, or with a mapping passed to Django 6's `{% querystring %}`, so other tables' state survives. This replaces `pagination_suffix`/`join_query` and fixes the unencoded search in sort links. Sort, filter and page use `hx-push-url="true"`. Debounced search uses `hx-replace-url="true"` plus `hx-sync="this:replace"`. Every pushed URL must render the full page on a normal GET. Add `Vary: HX-Request, HX-Target` to panel-framework responses. Set `<meta name="htmx-config" content='{"historyCacheSize": 0, "historyRestoreAsHxRequest": false}'>`: Back then always refetches a full page, which is what htmx 4 does anyway, and learner data stays out of sessionStorage. Move tab switching onto htmx (`hx-get` plus `hx-push-url`) instead of `tabContainer`'s own `pushState`. Neither the drawer nor the modal goes in the URL. The drawer's "Open" link is the shareable URL. A `?peek=` param with `hx-replace-url` can be added later without redesign. On mobile, the drawer pushes one entry so Back closes it, reusing `sidePanel`.

**Key pitfalls (current code).**
- On a history cache miss, htmx 2.0.8 sends `HX-Request: true` with no `HX-Target`. `panel_framework_view` answers that with a bare fragment, which htmx swaps into `<body>`, wiping the chrome.
- No `Vary` header, so Back or a reopened tab can show a cached fragment.
- `tabContainer`'s `pushState({})` confuses htmx's snapshot keying, so a tab URL can show another tab's content.
- Snapshots serialise an open dialog, so a later `showModal()` throws.
- Tables don't push URL state and all share one id and unprefixed params.
- `hx-on` and trigger filters need eval, which the CSP (no `'unsafe-eval'`) will block. Keep all behaviour in `Alpine.data` components driven by htmx events.
- Don't put the drawer or modal inside a swapped region.

**Dependencies.** None. Native `<dialog>`, htmx 2 and Django 6's `{% querystring %}` cover everything. Skip `@alpinejs/focus`, `response-targets` and django-tables2 (copy its prefix convention only). htmx 4.0.0 is out (npm `next`, 2026-08-28; 2.0.11 is still `latest`). Don't upgrade yet, but write for it: put `hx-target`/`hx-sync` on each element rather than relying on inheritance, queue only via `hx-sync`, and make every URL server-renderable.

**Context.** [research/htmx-modal-drawer-url-state.md](../research/htmx-modal-drawer-url-state.md), with sources and the full reasoning.
