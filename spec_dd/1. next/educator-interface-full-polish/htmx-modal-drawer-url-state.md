# Research: quick-view drawer, modal and URL-state patterns for HTMX 2 + Alpine (CSP) + Django

Question: what are the current best-practice patterns, with HTMX 2.x, Alpine.js and Django, for a non-modal quick-view drawer, a modal dialog, and URL state in a nested admin UI? Answered for specs 1, 2 and 3 of the educator interface rebuild (see the "Educator interface rebuild" section of `spec_dd/1. next/roadmap.md`).

This extends `../educator-interface-3-panel-framework-dialogs/research_ux_patterns.md` and `research_ux_pitfalls.md`. Those cover the UX survey and the ARIA model (disclosure-style triggers, live region, no focus trap on desktop, modal flip on mobile, RTL, print). None of that is repeated here. This note covers the mechanics: which elements, which htmx attributes and headers, which browser APIs, and where the current FLS code will break.

Researched 2026-09-24 against htmx 2.0.8 (the version `_base.html` loads), Alpine 3.15.8 CSP build, Django 6.0.

## Facts about the current codebase that shape the answer

- htmx `2.0.8` from jsDelivr; Alpine is the **CSP build** (`.claude/ds/config.md`: `CSP build: enabled`), so every behaviour lives in an `Alpine.data()` component. Only `@alpinejs/collapse` is loaded; there is no Focus plugin, so no `x-trap`.
- `SECURE_CSP_REPORT_ONLY` in `config/settings_base.py` has no `'unsafe-eval'`. htmx features that need eval (`hx-on:*`, trigger filters like `keyup[key=='Enter']`, `js:` in `hx-vals`/`hx-headers`) would be reported now and blocked once the policy is enforced ([htmx docs, Security](https://htmx.org/docs/#security): "Setting `htmx.config.allowEval` to `false` disables … Event filters, `hx-on:` attributes, `hx-vals` with `js:` prefix").
- `panel_framework_view` branches on `HX-Request` **and** `HX-Target` (`main-content` gets the navigation bundle, `data-table-container` gets the bare table, anything else gets a fragment). No response sets `Vary`.
- Tables (`cotton/data-table.html`, `cotton/pagination.html`) swap `#data-table-container` without `hx-push-url`, so sort, search and page are lost on reload and Back. Param names are unprefixed (`sort`, `order`, `search`, `page`) and one table id is hard-coded (`DEFAULT_TABLE_ID`), so two tables on a page collide. Sort links interpolate `search_query` into the URL without URL-encoding.
- `tabContainer` pushes tab URLs itself with `history.pushState({}, …)` and handles `popstate` itself, alongside htmx's own history.
- `cotton/modal.html` is an Alpine `div role="dialog" aria-modal="true"`: no focus move on open, no focus trap, no `inert` background, no focus return. Every action's form is rendered eagerly with the page. A 422 swaps the whole modal (`hx-target="closest div[x-data]" hx-swap="outerHTML"`), which destroys the focused field. A global `htmx:beforeSwap` handler in `base/js/alpine-components.js` already lets 422 swap.
- `sidePanel` (`base/js/alpine-components.js`) is a working precedent for "one `<dialog>`, `show()` on desktop, `showModal()` on mobile, push one history entry so Back closes it". Its comments document hard-won interplay with htmx history.
- htmx 4.0.0 shipped on npm on 2026-08-28 under the `next` tag; `latest` is still 2.0.11 (npm registry, `dist-tags`). Relevant htmx 4 changes ([migration guide](https://four.htmx.org/migration-guide-htmx-4/)): no history cache ("When navigating back, htmx re-fetches the page"), 4xx/5xx swap by default, attribute inheritance must be explicit (`:inherited`), queueing only via `hx-sync`, new event names.

## Primary-source facts used below

htmx 2 (docs and the 2.0.8 source):

- `hx-sync` `replace`: "abort the current request, if any, and replace it with this request". The sync element can be any selector, so many triggers can share one queue ([hx-sync](https://htmx.org/attributes/hx-sync/)).
- `hx-push-url="true"` pushes the request path (or the post-redirect response path); `hx-replace-url` replaces the current entry instead; both are inherited in v2; the `HX-Push-Url` / `HX-Replace-Url` response headers override them ([hx-push-url](https://htmx.org/attributes/hx-push-url/), [hx-replace-url](https://htmx.org/attributes/hx-replace-url/), source `determineHistoryUpdates`).
- Before each push htmx snapshots the history element (default `body`) into **sessionStorage** in 2.0.8 (the docs still say localStorage), keyed by the path htmx *believes* is current, then `replaceState({htmx: true})`. Its `popstate` handler only acts on entries whose `state.htmx` is set (source `saveCurrentPageToHistory`, `window.onpopstate`).
- On a cache miss htmx GETs the URL with `HX-History-Restore-Request: true`, and with `HX-Request: true` too while `htmx.config.historyRestoreAsHxRequest` is `true` (the default). It then swaps the response into the history element ([reference, config](https://htmx.org/reference/#config); source `loadHistoryFromServer`). `refreshOnHistoryMiss: true` does a full reload instead. `historyCacheSize` defaults to 10.
- GET parameters from a form or `hx-include` are **appended** to the `hx-get` URL (`?` or `&`), not merged (source, `useUrlParams` branch).
- Caching: "if your server renders the full HTML when the HX-Request header is missing or false, and it renders a fragment … you need to add `Vary: HX-Request`" ([docs, Caching](https://htmx.org/docs/#caching)).
- Default `responseHandling` does not swap 4xx/5xx; 422 can be opted in ([docs](https://htmx.org/docs/#response-handling)).

Browser platform:

- `showModal()` makes the rest of the page inert, puts the dialog in the top layer, closes on Esc and implies `aria-modal="true"`; `show()` is non-modal ([MDN `<dialog>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog)).
- Both `show()` and `showModal()` record the previously focused element and run the dialog focusing steps, so **`show()` also moves focus into the dialog**. On close, focus returns to the previously focused element only if the dialog was modal or focus is still inside it ([HTML spec, `show()` and close steps](https://html.spec.whatwg.org/multipage/interactive-elements.html#dom-dialog-show)).
- `showModal()` on an open non-modal dialog throws `InvalidStateError`; `show()` on any open dialog other than an already-non-modal one throws ([HTML spec, `showModal()`](https://html.spec.whatwg.org/multipage/interactive-elements.html#dom-dialog-showmodal)). You cannot switch modality in place.
- `closedby` (`any` = light dismiss) is "Limited availability", not Baseline ([MDN closedBy](https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/closedBy)). Invoker commands (`command="show-modal" commandfor="id"`) are Baseline 2025, newly available since December 2025 ([MDN Invoker Commands](https://developer.mozilla.org/en-US/docs/Web/API/Invoker_Commands_API)).
- `<dialog>` is Baseline widely available since March 2022. Don't put `tabindex` on the dialog itself ([MDN `<dialog>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog)).
- APG modal dialog: focus moves in on open; for long or structured content focus a static element with `tabindex="-1"` at the top; for destructive confirmations focus the least destructive action; on close return focus to the invoker unless it no longer exists ([APG Dialog (Modal)](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)).
- Alpine `x-trap` needs `@alpinejs/focus` ([Alpine Focus plugin](https://alpinejs.dev/plugins/focus)). Native `showModal()` makes it unnecessary.

Django:

- `{% querystring %}` builds a query string from `request.GET` (or given mappings), setting keys, removing them with `None`, and always emits a leading `?`. Django 6.0 accepts several positional mappings ([Django 6.0 built-in tags](https://docs.djangoproject.com/en/6.0/ref/templates/builtins/#querystring)). Keyword names must be Python identifiers, so dynamic prefixed keys have to come in as a mapping.
- Multi-table precedent: django-tables2 prefixes `sort`/`page`/`per_page` per table (`prefix="1-"` gives `1-sort`, `1-page`) "to prevent links on one table interfere with those on another table" ([django-tables2 query string fields](https://django-tables2.readthedocs.io/en/latest/pages/query-string-fields.html)).

## 1. Quick-view drawer

### Recommended pattern

One `<dialog id="quick-view">` in the interface layout, a sibling of `#main-content` (outside anything that navigation swaps), driven by a `quickView` Alpine component. Model it on `sidePanel`; ideally extract the shared "non-modal on desktop, modal on mobile, Back closes on mobile" behaviour so both use it.

```html
<dialog id="quick-view" x-data="quickView" aria-labelledby="quick-view-heading"
        class="…inset-inline-end-0…">
  <header class="sticky top-0 …">
    <h2 id="quick-view-heading" tabindex="-1">…</h2>
    <button type="button" x-on:click="close" aria-label="Close quick view">…</button>
  </header>
  <div id="quick-view-body" aria-busy="false"><!-- fragment swapped here --></div>
</dialog>
```

Triggers, rendered by one cotton component so the attributes are never hand-written:

```html
<button type="button"
        hx-get="{{ quick_view_url }}"
        hx-target="#quick-view-body"
        hx-swap="innerHTML"
        hx-sync="#quick-view-body:replace"
        hx-push-url="false"
        aria-controls="quick-view" aria-expanded="false">…</button>
```

- **Cancel in flight**: `hx-sync="#quick-view-body:replace"` puts every trigger on one queue, so a new click aborts the previous request. Put it on each trigger, not on an ancestor: htmx 4 drops implicit inheritance.
- **Open immediately**: the component listens for `htmx:beforeRequest` where the target is `#quick-view-body`. It opens the dialog if closed, renders the skeleton and the header the trigger already knows (from `data-*` on the trigger), sets `aria-busy="true"`, records the trigger and flips `aria-expanded`. On `htmx:afterSwap` it clears `aria-busy` and writes the one-line live-region summary.
- **Open, not swap, the dialog**: call `show()`/`showModal()` only when closed. A swap into an already-open drawer only changes the body, so there is no second focusing step.
- **Focus on desktop**: `show()` moves focus into the drawer (HTML spec). If the design keeps focus on the cell (the prior research recommends this for rapid browsing), call `trigger.focus()` straight after `show()`. On close, focus is not inside the dialog, so the browser will not restore it; do it yourself, as `sidePanel` does.
- **Esc on desktop**: a non-modal dialog does not close on Esc (default `closedby` is `none`), so add a `keydown` handler while open. Ignore it when a modal is open on top.
- **Toggle and re-open without refetch**: handle `htmx:confirm` on triggers. If the trigger's URL is the one showing and the drawer is open, `preventDefault()` and close. If the drawer is closed and holding that URL and nothing has invalidated it, `preventDefault()` and reopen. Closing hides the drawer; it does not clear the body. That is the whole cache.
- **Invalidation**: mutations anywhere already send `HX-Trigger` events (`panelChanged`, created events). The component marks its content stale on those events and refetches if it is open. Don't use HTTP caching for this: responses go stale the moment an action inside the drawer succeeds, and it adds `Vary` bookkeeping for no gain.
- **Mobile flip**: `matchMedia("(max-width: …)")`. The dialog can't change modality while open (spec), so on a breakpoint change while open, `close()` and reopen with the other method, with a flag so the close handler doesn't unwind history or move focus. `showModal()` gives the modal version inert background, focus containment, Esc and top layer for free, so the manual `inert` bookkeeping in the prior research isn't needed. Light dismiss on the backdrop: handle `click` where `event.target === dialog` (as `sidePanel` does), since `closedby="any"` isn't Baseline.
- **Mobile Back closes**: push one entry on modal open and close on `popstate`, reusing `sidePanel`'s logic, including its `htmx:beforeRequest` rule for navigation started from inside.
- **Server side**: the quick-view endpoint returns a fragment only. A non-HTMX GET to it redirects to the entity's full page, so a quick-view URL never becomes a page someone lands on. Set `Vary: HX-Request`.
- **Errors**: on `htmx:responseError` or `htmx:sendError`, render an inline error with a retry button in the body; don't close. `htmx:sendAbort` (from `replace`) is not an error; ignore it.
- **Actions inside the drawer** open the shared modal (section 2). The modal is top-layer and modal, so the drawer is inert while it is open, which is correct.

### Pitfalls

- Putting the drawer inside `#main-content`: every sidebar navigation destroys it mid-open. Keep it in the layout and close it on `htmx:beforeRequest` for `main-content` navigations.
- The history snapshot serialises the dialog's `open` attribute. Restoring it gives an open *non-modal* dialog, and a later `showModal()` throws `InvalidStateError`. Close the drawer and modal in `htmx:beforeHistorySave`, or turn the history cache off (section 3).
- Swapping `outerHTML` on the dialog itself re-runs the Alpine component and loses `triggerEl`; swap the body only.
- `aria-busy` on a body that isn't in the DOM yet: keep the body element permanent and swap its inside.

## 2. Modal dialog

### Recommended pattern

Native `<dialog>` opened with `showModal()`, one shared host in the layout, content loaded over HTMX, controlled by a small Alpine CSP component (`appModal`). Don't use an Alpine-drawn `div`: it reimplements what `showModal()` gives natively (top layer, inert page, Esc) and the current one misses focus handling entirely. The Focus plugin isn't needed.

```html
<dialog id="app-modal" x-data="appModal" aria-labelledby="app-modal-title">
  <div id="app-modal-body"></div>
</dialog>
```

Trigger (any action button, via a cotton component):

```html
<button type="button" hx-get="{{ action_url }}" hx-target="#app-modal-body"
        hx-swap="innerHTML" hx-push-url="false">Add learner</button>
```

- **Open**: `appModal` listens for `htmx:afterSwap` on `#app-modal-body` and calls `showModal()` if closed. The fragment carries its own `<h2 id="app-modal-title">`. Load-then-open avoids an empty modal flash; for slow endpoints, open on `htmx:beforeRequest` with a skeleton, as the drawer does.
- **Initial focus**: `autofocus` on the first field for forms; on the Cancel button for destructive confirmations; on the heading (`tabindex="-1"`) for long read-only content (APG). Not on the dialog.
- **The form**: `hx-post="{{ action_url }}" hx-target="this" hx-swap="outerHTML"`. The form replaces only itself.
- **422**: the server re-renders the form with errors and status 422 (the existing global `beforeSwap` handler allows the swap, and htmx 4 swaps 4xx by default, so this survives an upgrade). The swap destroys the focused element, so on `htmx:afterSwap` with status 422 the component focuses the error summary, or the first `[aria-invalid="true"]` field. Render errors with `aria-invalid` and `aria-describedby` on the fields.
- **Success**: respond 204, or 200 with OOB toasts, and `HX-Trigger: {"closeModal": true, "<domainEvent>": {...}}`. `appModal` listens for `closeModal` on `body` and calls `close()`; tables, tabs and the drawer listen for the domain event and refresh themselves. If the next step is navigation, use `HX-Location` with `{"path": …, "target": "#main-content"}` rather than `HX-Redirect`, so it stays an htmx navigation with history.
- **Close and focus return**: native close restores focus to the previously focused element for modal dialogs. If a success refresh has replaced that element (a table row re-rendered), fall back to a stable anchor such as the table's heading. Clear `#app-modal-body` on `close` so stale forms and errors don't reappear. The current `form.reset()` on show doesn't clear server-rendered errors.
- **Backdrop click**: `click` with `event.target === dialog` closes, the same as the drawer. For forms, consider not closing on backdrop click, since a stray click loses typed input.
- **Scroll lock**: `showModal()` doesn't lock page scroll. `html:has(dialog:modal) { overflow: hidden; }` does it in CSS.
- **No nesting**: a confirmation inside a modal replaces the modal body (a step), not a second modal.
- **Heavy flows** (CSV import, bulk review): make them pages, not modals. They need their own URL, Back, and reload survival.
- Cancel/close buttons inside the fragment can use `command="close" commandfor="app-modal"` (Baseline 2025) or an Alpine handler. Pick one; the Alpine handler also works on browsers older than December 2025.

### Pitfalls

- Eagerly rendering every action's form into the page: N forms per page, duplicate ids when the same action appears twice, stale CSRF-bound state. Load on demand.
- Swapping `outerHTML` on the component root (as `modal_form.html` does) re-initialises Alpine and drops focus.
- `hx-on::after-request` and trigger filters for close logic: they need eval, which the CSP will block. Use `HX-Trigger` events handled in `Alpine.data`.
- Opening a modal while the host dialog is non-modal-open throws (spec); the modal host is only ever `showModal()`ed, so keep it separate from the drawer.

## 3. URL state

### What goes where

| State | Where | How it changes |
|---|---|---|
| View (list, instance, base/dashboard) | path | `hx-push-url`, via sidebar and breadcrumbs (already done) |
| Instance | path segment | push |
| Tab | path (`…/__tabs/<name>`, as now) | push, **through htmx** |
| Panel within a tab | not in the URL; at most a `#fragment` to scroll to | none |
| Table sort, page, filters | query string, prefixed per table | push |
| Table search-as-you-type | query string, prefixed | replace |
| Quick view open | not in the URL (mobile: one pushed entry so Back closes) | none |
| Modal open | never in the URL | none |

`__panels/<name>` stays an HTMX fetch endpoint for refreshing one panel. It is never pushed.

### Query-string prefixing

- Each table gets a stable key from its declaration (`learners`, `registrations`), never a position. Its params are `<key>-sort`, `<key>-page`, `<key>-q`, and `<key>-<filter name>` for filters. Fold order into sort (`learners-sort=-created`) to save a parameter, as django-tables2 does with `order_by`. The table's DOM id derives from the same key, replacing `DEFAULT_TABLE_ID`.
- The table code reads only its own prefixed keys and builds every link from `request.GET.copy()` with its own keys changed. That preserves the other tables' state and the rest of the query string. Build these in Python (`DataTable` hands the template ready-made URLs) or pass a mapping to `{% querystring %}`; Django 6's tag can't take dynamic keyword names. This replaces `pagination_suffix`/`join_query` and fixes the unencoded `search_query` in sort links.
- Changing sort, a filter or search resets that table's page (`<key>-page` set to `None`).
- Search forms: htmx appends form values to the `hx-get` URL, so a form whose URL already contains `learners-q=old` produces a duplicate key. Render the form's `hx-get` as the current URL minus that table's own keys, and let the inputs supply them.

### Requests and responses

- Table controls `hx-get` the page URL with the new query string, target the table's container, and `hx-push-url="true"`. The pushed URL is then the real page URL with every table's state in it, so reload and share both work.
- Search: `hx-trigger="input changed delay:300ms, search"`, `hx-sync="this:replace"`, `hx-replace-url="true"`, so typing doesn't add one history entry per keystroke.
- **Every URL that can be pushed must render the full page on a normal GET.** The panel-framework dispatch already does this; keep it that way for tables (the full page renders each table from its prefixed params).
- Add `Vary: HX-Request, HX-Target` to every panel-framework response (`django.utils.cache.patch_vary_headers`), because the same URL returns different bodies by both headers. Without it the browser can serve a cached fragment on Back or on reopening a tab.
- **History restore needs its own branch.** On a cache miss htmx 2.0.8 sends `HX-Request: true` with no `HX-Target`, and today's dispatch answers that with a bare fragment. htmx then swaps that into `<body>` and the chrome disappears. Either set `historyRestoreAsHxRequest: false` so restore requests look like plain page loads, or treat `HX-History-Restore-Request: true` as a full-page request in `panel_framework_view`. Do one of them, and test Back after a cache miss.
- **Turn the history cache off**: `<meta name="htmx-config" content='{"historyCacheSize": 0, "historyRestoreAsHxRequest": false}'>`. Back then always refetches, which is what htmx 4 does anyway. It removes the snapshot bugs: Alpine state serialised into the DOM, open dialogs restored non-modal, and snapshots stored under the wrong key (below). It also keeps learner data out of sessionStorage. The cost is one request per Back, which is acceptable for an admin UI. (`_base.html` already has this meta commented out.) Setting `refreshOnHistoryMiss: true` as well trades that request for a full reload. Only do that if Alpine re-init after a body swap proves flaky.
- **Tabs through htmx**: `tabContainer` pushes with `history.pushState({}, …)`, which htmx doesn't track. htmx then snapshots under the path it last knew (without `__tabs/x`) and stamps the tab entry as its own, so Back can show one tab's content under another tab's URL. Give tab buttons `hx-get` to the tab URL, `hx-target` on the tab panel, and `hx-push-url` to the tab's page URL. Keep Alpine for show/hide of already-loaded panels only. With the history cache off, restore always refetches the right tab from the server.

### Should an open drawer or modal be in the URL?

- **Quick view: no**, as the prior research decided. The quick view's header has an "Open" link to the entity's full page; that URL is the shareable one. If deep-linking is wanted later, add `?peek=<type>:<id>` with `hx-replace-url` (not push, so Back doesn't walk through peeks) and have the full-page render open the drawer. The table design doesn't need to change for that.
- **Modal: no.** Forms in modals are short-lived; after a reload the typed input is gone anyway, so reopening an empty form from the URL gains nothing. Anything that needs a URL should be a page.

## Dependencies

None needed. `<dialog>`, `showModal()`, `inert`, `:modal` and `:has()` cover the drawer and modal; htmx 2 covers cancellation and history; Django 6's `{% querystring %}` covers link building. Not needed:

- `@alpinejs/focus`: native modal dialogs contain focus; the non-modal drawer must not trap.
- htmx `response-targets` extension: 422 swapping already works and htmx 4 makes it the default.
- htmx `head-support`/`preload`: nothing here needs them.
- django-tables2: its prefix convention is worth copying, the dependency isn't (the panel-framework draft keeps tables bespoke).

htmx 4: don't upgrade as part of this work (2.x is still npm `latest`), but write for it. Put `hx-target`/`hx-sync` on each element rather than relying on inheritance, route queueing through `hx-sync`, and make every pushed URL server-renderable. The event-name changes are then confined to the few `Alpine.data` components.

## Sources

- htmx docs: https://htmx.org/docs/ (History, Caching, Response handling, Security)
- htmx reference (config, request/response headers): https://htmx.org/reference/
- hx-sync: https://htmx.org/attributes/hx-sync/
- hx-push-url: https://htmx.org/attributes/hx-push-url/
- hx-replace-url: https://htmx.org/attributes/hx-replace-url/
- htmx custom modal example: https://htmx.org/examples/modal-custom/
- htmx 2.0.8 source: https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.js (`saveCurrentPageToHistory`, `loadHistoryFromServer`, `window.onpopstate`, `determineHistoryUpdates`, GET param handling)
- htmx 4 migration guide: https://four.htmx.org/migration-guide-htmx-4/
- npm registry for htmx.org dist-tags and release dates: https://registry.npmjs.org/htmx.org
- MDN `<dialog>`: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog
- MDN `HTMLDialogElement.closedBy`: https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/closedBy
- MDN Invoker Commands API: https://developer.mozilla.org/en-US/docs/Web/API/Invoker_Commands_API
- HTML Standard, dialog `show()`/`showModal()`/close: https://html.spec.whatwg.org/multipage/interactive-elements.html#the-dialog-element
- WAI-ARIA APG, Dialog (Modal): https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- Alpine Focus plugin: https://alpinejs.dev/plugins/focus
- Django 6.0 `querystring` tag: https://docs.djangoproject.com/en/6.0/ref/templates/builtins/#querystring
- django-tables2 query string fields: https://django-tables2.readthedocs.io/en/latest/pages/query-string-fields.html
