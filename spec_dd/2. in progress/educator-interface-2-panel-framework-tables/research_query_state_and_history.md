# Research: per-table query-string state and htmx URL/history mechanics

Verifies idea.md's "Per-table key", "Pushing state" and "Invariants kept" against htmx 2.0.8 (the
version pinned in `freedom_ls/base/templates/_base.html:54`, unchanged since spec 1's research),
Django 6.0's `{% querystring %}`, and the code as spec 1 actually left it (not as the older,
pre-spec-1 research described it). Read alongside `../educator-interface-full-polish/htmx-modal-drawer-url-state.md`
section 3 and `../../3. done/2026-09-26_16:41_educator-interface-1-panel-framework-core/research_tabs_and_history.md`,
which this note extends rather than repeats.

**Headline finding**: idea.md's "Pushing state" paragraph — "Table controls `hx-get` the page URL
with the new query string... `hx-push-url='true'`... The pushed URL is then the real page URL"
(copied near-verbatim from the parent research's section 3) — is correct only for a table that
*is* a whole list page's root panel. For the case this spec exists to fix (two or more
`DataTablePanel`s nested under a `PanelStack`/`TabSet`, e.g. the Cohort "details" tab's two
tables, or `CourseInstanceView`'s three), it does not work against the dispatch code as written,
and neither idea.md nor either research file names the mechanism that actually makes it work
(`HX-Push-Url` response header) or the missing plumbing (`PanelContext` carries no page-level
URL). See §3 below — this is the load-bearing correction in this note.

## 1. Building links: `request.GET`, `{% querystring %}`, and where URL-building code lives

Fetched Django 6.0's `{% querystring %}` docs and the `django.template.defaulttags.querystring`
implementation directly (it is a `@register.simple_tag(takes_context=True)`, not a node class).
Three facts the idea and the parent research leave incomplete:

- **No args → `request.GET`, as a base to merge from.** `{% querystring %}` alone reads
  `request.GET` (needs `django.template.context_processors.request`, which is enabled —
  `config/settings_base.py:192`). It walks `request.GET.lists()`, so multi-value keys round-trip.
- **A positional dict/QueryDict *replaces* `request.GET`, it does not merge with it, unless you
  pass `request.GET` explicitly as an earlier positional argument.** The implementation is `for d
  in [*args, kwargs]: ...`; when `args` is non-empty, the implicit "use `request.GET`" branch
  never runs. The docs say this directly: "You can pass custom `QueryDict` or `dict` instances as
  positional arguments **to replace** `request.GET`," and separately, "When multiple arguments
  are provided, key-value pairs from later arguments take precedence over earlier ones." So a
  template that wants "`request.GET` with only this table's keys changed" must write
  `{% querystring request.GET table_changes %}` (two positional args, later wins), not
  `{% querystring table_changes %}`. The latter throws away every other table's state and any
  other query param on the page — precisely the bug this spec exists to fix, reintroduced through
  the new mechanism if this is missed. Neither idea.md nor the parent research says this
  explicitly; the parent research's summary line ("pass a mapping to `{% querystring %}`") reads
  as if that alone is sufficient.
- **Dashed keys are fine as dict keys, just not as template `kwarg=` names.** The parent
  research's open question — "prefixed keys with a dash as kwargs — they can't be template
  kwargs, so how?" — is answered by the source: `kwarg=value` syntax needs a Python identifier,
  but a positional `dict`/`QueryDict` argument's keys are read via `.items()`/`.lists()` with no
  identifier constraint at all. `{"learners-sort": "-name", "learners-page": None}` works as a
  positional argument. `None` as a value pops the key (`params.pop(key, None)`); an iterable
  (non-`str`) value calls `setlist`, so a multi-value declared filter (`learners-status=active&
  learners-status=pending`) is expressible the same way. This resolves the "does it handle
  multi-value keys" question directly: yes, both on read (via `request.GET.lists()`) and on write
  (via a list value in the changes dict).
- **Where URL-building code lives**: recommend a **small Python method per table**, not a
  template tag of its own and not hand-built strings in the template. `DataTable`/`DataTablePanel`
  computes one `changes` dict per link kind (`{"<key>-sort": new_value, "<key>-page": None}` for a
  sort header; `{"<key>-page": n}` for a page link; `{"<key>-<filter>": value, "<key>-page":
  None}` for a filter chip) and the template does the merge and encoding in one place:
  `{% querystring request.GET column.changes as qs %}`, then `href="{{ qs }}"` for the no-JS
  fallback and `hx-get="{{ base_url }}{{ qs }}"` for the htmx one. This fixes the tables2-viability
  research's §2(a) complaint about needing two URLs per control (relative-only querystrings) for
  free, and fixes the unencoded `search_query` interpolation bug idea.md calls out in its "Why"
  (`{% querystring %}` URL-encodes every value it emits). Building the *merge* in the template
  keeps one code path responsible for "start from `request.GET`, don't lose other tables' state,"
  rather than every table subclass reimplementing `request.GET.copy()` by hand.
- **`c-pagination`'s existing `page_param_name`/`extra_params` inputs are a hand-rolled, partial
  version of this**, as `research_tables2_viability.md` §2 already notes for the two-axis progress
  matrix. `pagination_tags.py`'s `pagination_suffix`/`join_query` should stop being the DataTable
  path's mechanism (replaced by the `{% querystring %}` merge above); `cotton/pagination.html`
  itself stays in `base` per idea.md's "settled" location note, since the progress matrix isn't a
  `DataTable` and keeps calling it with its own `page_param_name`/`extra_params`.

## 2. Key collision rules

- **Charset**: idea.md never states one. Nothing in Django or htmx constrains query-param-name
  characters, and because every table reads only its own fully-qualified keys by exact string
  match (`request.GET.get(f"{key}-sort")`), a dash *inside* a table's own `key` does not break
  parsing — the table never splits on `-`. The risk is pure collision, not parsing. Recommend the
  spec still restrict `key` to something identifier-like (lowercase, `[a-z0-9_]+`, no dash), for
  two reasons this note surfaces that idea.md doesn't: it keeps `<key>-sort` unambiguous to a
  *human* reading a URL, and it rules out the pathological case where one table's `key` (say,
  `"learners-sort"`) collides with another table's `key` (`"learners"`) plus its own `-sort`
  suffix.
- **Uniqueness enforcement — idea.md is silent, and there is a direct in-repo precedent to copy.**
  `views.py`'s `sections_by_url_name()` (`freedom_ls/panel_framework/views.py:185-195`) already
  raises `ImproperlyConfigured` at config-load time for two sections sharing a `url_name`. Nothing
  analogous exists, or is proposed, for table keys. Recommend the same shape: either a system
  check that walks each `NavGroup`'s panel trees (recursing through `children`) and raises on two
  `DataTablePanel`s under the same container sharing a `data_table` key, or an assertion at the
  point a container (`PanelStack`/`TabSet`) resolves its `_shown_children` (`panels.py:86-97`),
  mirroring how `Panel.child()` already raises on a missing name. Runtime silent collision (two
  tables both reading `learners-sort` and clobbering each other's rows) is the exact bug class the
  idea's "Why" section calls out for the *current* unprefixed code; the new design needs its own
  enforcement or it just moves the same bug one level up (key choice instead of no key at all).
- **Collision with tabs**: none, by construction — tabs live in the path (`__tabs/<name>`), never
  in the query string, confirmed by the actual code: `_tab_set_base.html` builds tab links from
  `tab.url` (a path), and `TabSet.get_active_child()` (`panels.py:164-173`) reads `request.path`,
  never `request.GET`. No overlap is possible.
- **Collision with the drawer/modal (spec 3)**: none today. Spec 3's idea.md is explicit that
  quick-view and modal state is **never** in the URL ("Out of scope: deep-linking an open quick
  view (`?peek=`)"), so there is nothing for a table's `<key>-*` params to collide with yet. If
  `?peek=` is ever added (spec 3 leaves room for it, unprefixed, top-level), it is safe only
  because no table will realistically be keyed `"peek"`; worth one sentence in this spec's
  settlement noting that a future top-level param must avoid colliding with any declared table's
  `<key>-*` prefix, since nothing enforces that automatically once `?peek=` exists outside any
  table's own key-uniqueness check.

## 3. `hx-push-url` vs `hx-replace-url`, debounce, `hx-sync`, and the search-URL claim

Confirmed against primary sources, several already cited in the parent research and re-verified
here plus one not previously pulled in:

- **`hx-sync="this:replace"` and the debounce trigger are both right, and correctly diverge from
  htmx's own canonical example for a real reason.** htmx's official Active Search example
  (https://htmx.org/examples/active-search/) uses `hx-trigger="input changed delay:500ms,
  keyup[key=='Enter'], load"` — no `hx-sync` at all, and a **trigger event filter**
  (`keyup[key=='Enter']`). Event filters need `eval` (already established by the parent research:
  "trigger filters like `keyup[key=='Enter']`... would be reported now and blocked once the
  policy is enforced," citing htmx's Security docs, https://htmx.org/docs/#security). Idea.md's
  chosen trigger, `hx-trigger="input changed delay:300ms, search"`, uses the native `search` event
  instead — this fires on Enter and on the input's native clear ("×") button for `type="search"`
  fields with no filter syntax, so it is CSP-safe where htmx's own documented example is not. This
  is a place the idea is *right* and worth stating explicitly as verified, since it silently
  diverges from the tool's own canonical pattern.
- **`hx-sync="this:replace"` matches `hx-sync`'s own docs** ("abort the current request, if any,
  and replace it with this request," https://htmx.org/attributes/hx-sync/), already quoted by the
  parent research. Confirmed correct for cancelling in-flight search requests.
- **The GET-params-append-not-merge fact holds** (parent research, citing the 2.0.8 source's
  `useUrlParams` branch): form values from `hx-include` are appended to whatever querystring is
  already on the `hx-get` URL, not merged key-by-key. This is real and the idea's instinct to
  avoid it is right, but **idea.md's stated fix is imprecise and, read literally, breaks something
  it doesn't mention.** Idea.md says: "The search form's request URL is the current URL minus the
  table's own keys, so htmx does not append a duplicate." Read literally — minus *all* of "the
  table's own keys" (sort, page, `q`, and every declared filter) — this strips the table's active
  sort and filter selections out of the base URL for the search request. Since the search form
  only supplies its own `<key>-q` input (and nothing to `hx-include` for sort or filters), a
  keystroke would silently reset sort and every filter along with the page, which idea.md's own
  "Invariants kept"/"Pushing state" language never states as intended ("Changing sort, a filter or
  the search resets that table's page" — page only, not each other). Two ways to make this
  consistent, either is fine but the spec must pick one explicitly:
  - Strip only `<key>-q` and `<key>-page` from the base URL (not sort/filters), so those two
    survive untouched in the `hx-get` target and the form supplies only the new `q`; page resets
    because it is simply absent. This is the minimal, behaviour-preserving reading.
  - Keep today's already-working pattern instead: `cotton/data-table.html`'s form already renders
    hidden `sort`/`order` inputs alongside the visible search field
    (`freedom_ls/base/templates/cotton/data-table.html:27-30`) and targets a **bare** `base_url`
    with no pre-existing querystring at all, so there is no duplicate-key risk in the first place
    — extend that same pattern with one hidden input per currently-set filter key. This needs no
    querystring-stripping logic, just more hidden inputs, mirroring what is already there.

  Either resolves the ambiguity; idea.md's current wording does neither and should be corrected to
  name which keys are stripped, not "the table's own keys" unqualified.

- **The real gap: for a nested table, "the page URL" the design wants pushed is not the URL the
  fetch goes to, and nothing threads it down.** Every htmx interaction inside a `DataTablePanel`
  necessarily `hx-get`s the panel's own sub-URL (`.../__panels/<key>`) — that is how
  `panel_framework_view`'s dispatch finds the specific panel to re-render at all
  (`_resolve_path`'s walk over `__panels`/`__tabs` segments, `views.py:302-349`; `_respond`'s
  `hx_target == panel.region_id` branch, `views.py:466-471`). If `hx-push-url="true"` is put on
  that same `hx-get`, htmx pushes **the request URL** — the panel sub-URL — per
  `hx-push-url`'s own docs (https://htmx.org/attributes/hx-push-url/: "pushes the request path...
  into the location bar"). That directly contradicts the parent research's own table: "`
  __panels/<name>` stays an HTMX fetch endpoint for refreshing one panel. It is **never** pushed."
  For a table that *is* a section's whole root panel (`ListViewPanel`, `_bind_root`'s
  `ListViewConfig` branch, `views.py:254-264`), `base_url` and the page URL happen to be the same
  string, so idea.md's wording works by accident — but that is exactly the single-table case the
  spec is *not* motivated by. For two `DataTablePanel`s under one `PanelStack`/`TabSet` — the
  motivating case in idea.md's own "Why" — the fix is the response header, not the request
  attribute: `HX-Push-Url` "overrides any behavior defined with attributes" and accepts an
  explicit URL, "relative or absolute, as per `history.pushState()`," or `false`
  (https://htmx.org/headers/hx-push-url/, https://htmx.org/attributes/hx-push-url/). The table's
  Python code should set `hx-push-url="false"` (or omit the attribute) on its own controls and
  instead have the server set `HX-Push-Url: <full page URL>?<merged querystring>` on the response,
  decoupling "what got fetched" (the panel sub-URL, needed for dispatch) from "what gets shown in
  the address bar and pushed to history" (the real page URL, needed for reload/share). The same
  applies to `hx-replace-url` for search — use `HX-Replace-Url`, not the attribute, for the same
  reason.

  This needs one more piece neither idea.md nor `PanelContext` (`panel_framework/context.py`)
  provides: **the page-level URL itself is not available to a nested panel today.**
  `PanelContext.base_url` (`context.py:11-26`) is "the URL of this panel's own path segment" —
  for a table nested two levels deep (`.../__tabs/details/__panels/learners`), that is the
  sub-URL, not the section's page URL. Nothing threads "the section's own top-level URL" down
  through `replace(ctx, base_url=..., name=...)` in `Panel._shown_children`
  (`panels.py:86-97`). The spec needs to either add a field for this (e.g. `page_url`, set once at
  `_bind_root` and carried unchanged through every `replace()` call, unlike `base_url` which
  changes per level) or compute it server-side by stripping every trailing `/__panels/<name>` and
  `/__tabs/<name>` segment off `base_url` when building the `HX-Push-Url` value — workable, but
  worth stating as a real decision the spec has to make, not something idea.md already answers.

## 4. History: htmx's cache, `historyCacheSize`, `refreshOnHistoryMiss`, back button, bfcache, Alpine state

**Spec 1 already landed the settlement the parent research recommended, contrary to what both
older research files describe as still-pending.** `freedom_ls/base/templates/_base.html:73-74`
now reads (not commented out): `<meta name="htmx-config" content='{"historyCacheSize": 0,
"historyRestoreAsHxRequest": false}' />`. This is confirmed live, not aspirational — spec 2
inherits it and does not need to reopen it. What this means concretely for tables, since neither
idea.md nor either research file spells out the *consequence* of the setting rather than the
setting itself:

- With `historyCacheSize: 0`, htmx's JS-managed sessionStorage snapshot/restore machinery never
  fires — no snapshot is ever written (so `htmx:historyItemCreated` never fires either, per the
  2.0.8 source cited in the tabs research), and every Back/Forward through a pushed table URL is a
  cache *miss* by construction, going through `loadHistoryFromServer`.
- With `historyRestoreAsHxRequest: false`, that miss-driven GET is sent **without** `HX-Request:
  true` (only `HX-History-Restore-Request: true`), so `panel_framework_view`'s `_respond` takes
  its `if not is_htmx or is_restore:` branch (`views.py:445-446`) and renders the **full page**
  template, not a bare fragment. This is exactly the behaviour idea.md's invariant ("every URL a
  table can push renders a full page on a normal GET") needs on Back specifically, and it already
  holds today for the general path — it is not something spec 2 has to build, only something it
  should rely on and, ideally, add one Playwright test for (a table sort/page click, a Back, and
  an assertion that the URL bar and the visible rows/sort-indicator agree), extending the same
  "no nested `section`" fixture idea.md already keeps.
- `refreshOnHistoryMiss` is moot at `historyCacheSize: 0` — there is nothing to be a "miss" of a
  cache that never populates; every restore already goes to the server. No action needed; idea.md
  doesn't mention this, correctly, since it is a non-issue given the settled config.
- **Row-selection Alpine state (idea.md's checkbox column / "n selected" bar) needs no special
  handling on Back, and this is worth stating as reassurance rather than a gap**: because
  `historyCacheSize: 0` means Back is always a fresh server round trip, no DOM (and no Alpine
  component state living inside it) survives a Back navigation to restore stale or mismatched —
  selection simply resets, which matches ordinary web-app expectation (Gmail, for one, does not
  restore selection across Back either) and requires no serialisation of selection into the URL or
  anywhere else.
- **bfcache is a distinct, still-open question, unchanged by anything in this spec** — confirmed
  by re-checking the same ground the tabs research already covered
  (https://developer.mozilla.org/en-US/docs/Web/API/Performance_API/Monitoring_bfcache_blocking_reasons):
  `panel_framework`/`educator_interface` set no `Cache-Control` header anywhere, so these pages
  remain bfcache-eligible in principle. Unlike htmx's own JS cache, bfcache freezes and restores
  the *whole* page atomically (DOM, address bar, JS heap together), so a table's displayed rows
  and its pushed URL cannot go out of sync via bfcache the way a stale htmx snapshot could — the
  practical risk bfcache poses here is not data staleness but whether authenticated pages holding
  learner PII should be bfcache-eligible at all on a shared machine after logout. That question was
  already flagged unresolved by spec 1's research and is not newly answered by anything in this
  topic; this spec should not treat it as its own to resolve, only note it is still open.

## 5. Page reset and invalid page values

- **Already correct, no change needed**: `DataTable.get_rows` (`tables.py:56-58`) calls
  `paginator.get_page(page_number)`, not `.page(...)`. Django's `Paginator.get_page` (unlike
  `.page()`, which raises `PageNotAnInteger`/`EmptyPage`) "returns a valid page, even if the page
  argument passed... is out of range... If the page is not a number, return the first page. If the
  page number is negative or exceeds the number of pages, return the last page." This already
  matches the tolerant behaviour a per-table `<key>-page` needs — an invalid or stale
  `learners-page=9999` after a filter removes rows doesn't 404, it clamps to the last page. Moving
  to a prefixed key changes nothing about this call; it stays `get_page`.
- **The actual new behaviour idea.md wants — "changing sort, a filter or the search resets that
  table's page" — does not exist in the current code today** (nothing resets `page` on a sort
  click now) **and needs building**, but it composes for free with the `{% querystring %}`
  mechanism in §1: every changes-dict for a sort/filter/search link simply includes
  `"<key>-page": None` alongside its own key's new value, and `{% querystring %}`'s `None`-removes
  behaviour drops it. No separate page-reset code path is needed once link-building goes through
  that mechanism; idea.md states the rule but not that this is how it falls out of the URL-building
  choice, worth making explicit in the spec so the two aren't designed independently.

## 6. Focus and announcement after a table swap

Idea.md's "Invariants kept" section says nothing about either, despite spec 1 having already built
exactly this machinery for a directly analogous case (tab switches) — this is a real, checkable
gap, not a stylistic omission:

- **Announcement**: `panel_framework/partials/announcer.html`, the persistent `#scope-announcer`
  live region, is already used for tab switches — `tab_response.html`
  (`freedom_ls/panel_framework/templates/panel_framework/tab_response.html`) renders
  `{% render_panel panel %}` **plus** an `announcer.html` OOB include with `message="Showing
  {panel.title}"`, on every htmx tab-panel swap. Nothing analogous exists for a `DataTablePanel`'s
  own region swap: `_respond`'s `hx_target == panel.region_id` branch
  (`views.py:466-471`) renders `panel.region_template_name or panel.template_name` with
  `panel.get_context_data()` directly — no announcer, no `panel_announcement` request attribute
  set anywhere in the table's own dispatch path. A sort, filter, page or search change on a table
  today (and, unaltered, tomorrow) is silent to a screen-reader user. Recommend the table's region
  template gain the same OOB `announcer.html` include the tab response already uses, with a
  message summarising the result (e.g. "Showing 1–20 of 143, sorted by Name" or "12 results
  found"), directly reusing the existing partial rather than inventing a second announcement
  mechanism.
- **Focus**: also unaddressed, and structurally different from the tab case in a way worth
  naming explicitly. `_tab_set_base.html`'s own comment explains why tabs don't lose focus on
  swap: "the nav sits outside that region so the focused link survives the swap." A table cannot
  do the same and keep idea.md's own invariant that "the table's fragment root stays `<div
  id='<key>'>` swapped with `outerHTML`" — every control that can trigger a table swap (the sort
  `<a>` in each `<th>`, every pagination `<a>`, the search `<input>`) lives **inside**
  `cotton/data-table.html`'s outer `<div id="{{ table_id }}">`
  (`freedom_ls/base/templates/cotton/data-table.html:13-112`), so an `outerHTML` swap destroys the
  element that was just focused on every single interaction, unlike tabs where the nav is
  deliberately external to the swapped region. Idea.md inherits this structure unchanged (its own
  "Invariants kept" reaffirms the same swap root) without naming the focus consequence. Recommend
  a document-level `htmx:afterSwap` listener, matching the shape `_tab_set_base.html`'s own
  comment describes for tabs ("A document-level `htmx:afterSwap` listener moves `aria-current` to
  the clicked link") but doing the equivalent for tables: after a swap whose target id matches a
  table's region id, move focus to a stable anchor inside the new fragment — a `tabindex="-1"`
  heading/caption at the top of the table, per the APG guidance already cited and applied
  elsewhere in this effort's research for "long or structured content" (see
  `htmx-modal-drawer-url-state.md` §2, "focus a static element with `tabindex='-1'` at the top").
  This is new work, not something to inherit for free; flagging it because idea.md's silence reads
  as though the tab precedent already covers it, and it structurally cannot.

## Sources

- Django 6.0 `{% querystring %}` docs: https://docs.djangoproject.com/en/6.0/ref/templates/builtins/#querystring
- Django `template.defaulttags.querystring` implementation (merge/`None`-removal/`.lists()` behaviour), fetched from https://raw.githubusercontent.com/django/django/stable/6.0.x/django/template/defaulttags.py
- Django `Paginator.get_page` vs `.page()`: https://docs.djangoproject.com/en/6.0/ref/paginator/#django.core.paginator.Paginator.get_page
- htmx `hx-sync`: https://htmx.org/attributes/hx-sync/
- htmx `hx-push-url` (attribute): https://htmx.org/attributes/hx-push-url/
- htmx `HX-Push-Url` response header: https://htmx.org/headers/hx-push-url/
- htmx Active Search example (canonical trigger/filter pattern, for contrast): https://htmx.org/examples/active-search/
- htmx Security docs (eval-requiring features under CSP): https://htmx.org/docs/#security
- htmx docs, History and Caching: https://htmx.org/docs/#history, https://htmx.org/docs/#caching
- MDN, Monitoring bfcache blocking reasons: https://developer.mozilla.org/en-US/docs/Web/API/Performance_API/Monitoring_bfcache_blocking_reasons
- In-repo: `freedom_ls/panel_framework/tables.py`, `panels.py`, `views.py`, `context.py`;
  `freedom_ls/base/templates/cotton/data-table.html`, `cotton/pagination.html`;
  `freedom_ls/base/templatetags/pagination_tags.py`;
  `freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_base.html`,
  `_data_table_region_base.html`, `_tab_set_base.html`;
  `freedom_ls/panel_framework/templates/panel_framework/tab_response.html`,
  `navigation_response.html`, `partials/announcer.html`; `freedom_ls/base/templates/_base.html`
  (htmx version pin and the now-live `historyCacheSize`/`historyRestoreAsHxRequest` meta tag).
- `spec_dd/1. next/educator-interface-2-panel-framework-tables/idea.md`,
  `research_tables2_viability.md`; `spec_dd/1. next/educator-interface-full-polish/htmx-modal-drawer-url-state.md`
  §3; `spec_dd/3. done/2026-09-26_16:41_educator-interface-1-panel-framework-core/research_tabs_and_history.md`;
  `spec_dd/1. next/educator-interface-3-panel-framework-dialogs/idea.md`; `spec_dd/1. next/roadmap.md`.

status: ok
