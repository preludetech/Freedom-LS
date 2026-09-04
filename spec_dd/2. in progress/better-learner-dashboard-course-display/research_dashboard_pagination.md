# Research — paginating several independent card grids on one dashboard

Topic: how several independently paginated groups coexist on the learner dashboard. Scope is the
dashboard only. Working assumption under test: minimal next/prev controls, In Progress paginated the
same way as every other group.

Vocabulary note: the idea's word for a division of the dashboard is **group** (featured group,
category group, coming-soon). This document keeps it. "Section" is used only for the HTML/landmark
sense (`<nav>`, heading structure). Django's own nouns — **page**, **page number**, **page size**,
**paginator** — are used for the pagination concepts; `item`, `collection` and `slot` are taken words
in FLS and are not reused here.

---

## Conclusions, up front

1. **This codebase already has the multi-paginator pattern and it should be reused.** The educator
   cohort course-progress panel runs two independent paginators on one URL, namespaced by query
   parameter, each swapping one HTMX target. That is the pattern; the dashboard is the same problem
   with N groups instead of 2.
2. **Page state belongs in namespaced query parameters, derived from a group slug behind a fixed
   prefix, with non-default page numbers only.** Not session state, not server-held state, not OOB
   swaps carrying position.
3. **Swap the group's grid, not the page** — and specifically swap a wrapper *below* the group's
   `<h2>`, so the heading survives as a stable focus target and heading order cannot break.
4. **The existing `extra_params` mechanism does not scale past ~2 paginators.** It makes every
   control carry every other group's page number. With 6 groups that is 5 extra params per link,
   hand-built per call site. The idea must acknowledge that a different "carry the rest of the query
   string" mechanism is needed.
5. **Pagination here cannot reach the database.** Both dashboard sequences are Python lists assembled
   in the view after per-learner work. `Paginator` will page a list that was already fully
   materialised. The saving is per-card render work, not query work, and there is an O(all courses)
   floor per render that pagination does not remove.
6. **Next/prev-only is the right call for a dashboard** — but only with a stated count and a per-group
   escape hatch into `/courses/`. Three specific places where it argues against the working
   assumption are listed in their own section.
7. **Accessibility is the part that will be got wrong**, and the single biggest trap is that
   `hx-swap="outerHTML"` destroys the control the user just pressed, dropping focus to `<body>`.

---

## 1. Prior art in this repo — this is the pattern to reuse

### `<c-pagination>` — the shared component

`freedom_ls/base/templates/cotton/pagination.html`. Inputs: `page_obj`, `base_url`, `table_id`,
`sort_by`, `sort_order`, `search_query`, `extra_params`, `page_param_name`. Two supporting template
tags live in `freedom_ls/base/templatetags/pagination_tags.py`:

- `join_query(**kwargs)` — URL-encodes arbitrary key/values into an `a=b&c=d` fragment.
- `pagination_suffix(...)` — assembles the trailing `&sort=…&order=…&search=…<extra_params>` suffix.

Each control is an `<a>` with **both** a relative `href="?page=N…"` fallback and an
`hx-get="{{ base_url }}?page=N…"`, `hx-target="#{{ table_id }}"`, `hx-swap="outerHTML"`. Progressive
enhancement is already built in — a no-JS visitor and a crawler both get a working link. Preserve
that.

The component renders **two layouts**: mobile (`flex sm:hidden`) is Previous / "Page X of Y" / Next;
desktop (`hidden sm:flex`) is First / Previous / numbered buttons with ellipsis / Next / Last. See
the tension in §7.

Tests: `freedom_ls/base/tests/test_pagination_component.py` covers param preservation and the HTMX
target. It asserts **nothing** about `<nav>`, `aria-label`, `aria-current` or a live region — because
the component has none. Accessibility work here is net-new, not a regression fix.

### Two independent paginators on one URL — the existing precedent

`freedom_ls/educator_interface/views.py` `CohortCourseProgressPanel`:

- `_paginate_course_items(course, request.GET.get("col_page", 1))` — `Paginator` over a **Python
  list** of `ContentCollectionItem`, page size `COLUMN_PAGE_SIZE`.
- `_paginate_learners(cohort, selected_reg, request.GET.get("page", 1))` — `Paginator` over a
  queryset, page size `LEARNER_PAGE_SIZE`.

`freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html`
carries the design note verbatim:

> Pagination controls — both paginators live on the same URL, so each one passes the OTHER's current
> page (and the selected registration) through `extra_params` to keep them independent.

It builds `col_extra` and `learner_extra` with two `join_query` calls, renders `<c-pagination>` twice
with `page_param_name="col_page"` and the default `"page"`, and both target the single container
`#course-progress-content` with `hx-swap="outerHTML"`. It also renders the position in text next to
each control: `Items {{ col_page.start_index }}–{{ col_page.end_index }} of
{{ col_page.paginator.count }}`.

**Everything the dashboard needs already exists except (a) an N-way version of `extra_params`, (b) a
next/prev-only variant, and (c) the accessibility layer.**

### Other pagination in the tree

`freedom_ls/panel_framework/tables.py` `DataTable.get_rows` — `Paginator(queryset, cls.page_size)`,
`page_size = 5`, `page_number = request.GET.get("page", 1)`, `paginator.get_page(page_number)`. This
is the queryset-backed happy path the dashboard does *not* get (see §6).

`form_fill_page` in `freedom_ls/learner_interface/views.py` paginates form pages, but by URL path
segment and without `Paginator`. Different problem; not a precedent for this.

---

## 2. Per-group page state — recommendation and trade-offs

### Recommendation

**Namespaced query parameters, one per group, behind a fixed prefix, derived from a validated group
slug, emitted only when the page number is not 1.**

Shape: a single prefix such as `page_<group-slug>` (`?page_wellbeing=2`). A *prefix* rather than a
suffix matters: "is this a pagination parameter?" becomes a `startswith` test, which makes it trivial
to drop unknown ones and to build "the current query string minus my own page parameter" without
enumerating every group.

`<c-pagination>`'s `page_param_name` input already accepts an arbitrary name, so this needs no change
to the component's parameter handling.

### What "group identity is site-configurable" implies

The parameter *names* are data-derived. Three consequences the idea must carry:

- **Validation is on the name, not just the value.** A parameter name built from a free-text group
  title is a defect: it can contain `&`, `=`, spaces, or non-ASCII, and it changes when an
  administrator edits the title. Derive the name from a stable slug field with a validated charset,
  never from a display name. The set of legal parameter names on any given request is exactly "prefix
  + slug, for each group currently configured for this site" — everything else is ignored.
- **Unknown parameters must degrade silently, not error.** A bookmark taken before a group was
  renamed or removed must still render the dashboard at page 1 of everything. Do not 404 and do not
  422 (see the convention note in §8). `Paginator.get_page()` already clamps a too-high or
  non-integer page number, which is the right behaviour for a home page.
- **URL length is bounded by the "non-default only" rule, not by group count.** Worst case is one
  parameter per group; realistic case is one parameter total, because a learner pages one group at a
  time and every other group is on page 1 and contributes nothing. Without that rule, N groups means
  N parameters in every link on the page, N² parameters across the page, and log/URL noise that grows
  with site configuration. With it, the URL stays short and self-describing.

### The `extra_params` scaling problem — a real finding

The educator panel's approach (each control carries every *other* paginator's page explicitly, built
by hand with `join_query` at the call site) is fine for 2 and does not survive 6. It is O(N) params
per control, O(N²) across the page, and O(N) hand-written `join_query` calls per template. Combined
with "non-default only" the *URL* stays short, but the *mechanism* still has to be "take the incoming
query string, drop my own page parameter, add my new one" rather than "list the others explicitly".
The idea should say that this is required; the spec picks the shape.

### Alternatives, and why they lose

| Mechanism | Bookmark | Back button | Shared link | Verdict |
| --- | --- | --- | --- | --- |
| Namespaced query params | Yes | Works if URL is pushed; otherwise Back leaves the page | Yes, and reproduces exactly | **Recommended** |
| Session / server-held position | No — URL says nothing | Back shows stale or wrong content | No — recipient sees their own state | Reject. Also: two tabs fight over one position, and it makes the anonymous home page uncacheable per visitor. |
| OOB swaps carrying position in the DOM | No | No | No | Reject as the *state* mechanism. OOB has one legitimate use here — the live region (§4) — and that is all. |
| Path segments (`/page/2/`) | Yes | Yes | Yes | Reject: N groups cannot each own a path segment, and the dashboard is `/`. |

### `hx-push-url`: state the decision, don't leave it implicit

- **With** `hx-push-url`: Back steps through page changes, the address bar reflects the paged state,
  and the state is shareable *as visited*. Cost: paging four groups twice each leaves eight history
  entries between the learner and wherever they came from — on a **home page**, that is a bad Back
  button.
- **Without** it (what the educator panel does today): Back means "leave the dashboard", which is the
  ordinary expectation for a home page. The state is still expressible as a URL because the controls
  carry a real `href` — it is just not automatically recorded.

Recommendation: **do not push the URL per swap**, keep the real `href` on every control. The idea
should record this as a deliberate choice, because it is the kind of thing that gets raised as a bug
later.

---

## 3. What actually swaps

### Swap the group, not the page

`hx-target` the group's grid wrapper; `hx-swap="outerHTML"` per the house HTMX convention (always
specify both, prefer `outerHTML`).

**Specifically: put the swap boundary below the group's `<h2>`.** The current
`learner_interface/partials/course_list.html` gives each group a wrapper div with an id
(`#current-courses`, `#recommended-courses`, `#available-courses`, `#learning-history`) containing an
`<h2>` from the `section-heading` partialdef and then the `course-grid` partialdef. If the swap target
is the outer div, the fragment must re-render the `<h2>` — which is how heading order gets broken
(Lighthouse `heading-order` is one of the three checks Wagtail measured htmx-powered Django sites
failing more than average). If the target is an inner wrapper holding grid + position text + controls,
the `<h2>` is untouched, stays in the accessibility tree, and becomes the stable focus target that
§4 needs. That is the better shape and it costs nothing.

### Cost of re-rendering the page instead

Per dashboard render today (`dashboard` in `freedom_ls/learner_interface/views.py`), for an
authenticated learner:

- `get_current_courses` → `get_course_registrations` + `course_progress_by_course_for` over **all**
  registrations, then a Python pass stamping `progress_percentage`.
- `_annotate_registered_courses` → **per registered course**: `backend.get_access(...)` and
  `_annotate_next_up` → `get_course_index(...)`, which walks the course's children and their children
  and, for an authenticated learner with content access, reads progress and deadline state. This is
  by far the most expensive per-card work on the page.
- `_visible_recommendations` → a `filter_visible` pk query over the recommendation set.
- `_available_courses` → iterates `backend.filter_visible(user, get_all_courses())` calling
  `get_access_badge` and `is_coming_soon_for_display` **per course**, stamping three attributes each.
- `get_dashboard_contributions` → renders every backend panel to a string.

A full-page re-render to move one group forward one page pays all of that again, including rendering
every other group's cards. A group-scoped swap pays the group's own share plus whatever the grouping
resolution costs.

### The constraint this puts on the grouping design

A group-scoped endpoint must be able to build **one** group without building the others. If the
grouping is defined globally — "featured is the first N of a site-wide ordering, the rest fall into
categories" — then a request for one group still has to compute the whole ordering, and the
request-count saving is real but the compute saving mostly is not. If each group's membership is
independently resolvable (a relation or an explicit ordering per group), the swap is genuinely cheap.
**The idea should say which of these it is assuming**, because it changes what pagination buys.

Silver lining worth stating: paginating **In Progress** is a straightforward performance win, because
`_annotate_next_up` / `get_course_index` currently runs once per registered course and pagination caps
it at the page size.

---

## 4. Accessibility — the checklist the spec has to satisfy

### Landmark and naming

- Wrap each group's controls in `<nav>` with a **unique** `aria-label` naming the group — e.g.
  `aria-label="Wellbeing courses pagination"`. Multiple nav landmarks sharing one label is a
  landmark-navigation failure; GOV.UK, USWDS and Primer all say the label must be unique per instance
  on the page.
- **Five identical "Next" buttons is the specific problem here.** The `<nav>` label satisfies WCAG
  2.4.4 Link Purpose (In Context) on a technicality, but a screen-reader user listing all links on
  the page hears "Next, Next, Next, Next, Next". Give each control a name that includes its group:
  visible text "Next" plus visually-hidden group text, or an explicit `aria-label`. Do not rely on
  the landmark alone.
- `aria-current="page"` applies only to numbered controls. With next/prev only there is **no** current
  page link, so the textual position statement carries the entire burden of "where am I" — see below.

### Position must be stated in text

Yes, non-negotiable, and there is precedent: the educator panel already renders
`Items {{ page.start_index }}–{{ page.end_index }} of {{ page.paginator.count }}`. On the dashboard the
noun is courses: **"Showing 4–6 of 19 courses"**, optionally with "Page 2 of 4".

It does three jobs at once: it is the WCAG 2.4.8 Location aid, it is the announcement payload for the
live region, and it is the mitigation for the "how much is there?" downside of next/prev-only (§5).
Dropping it turns three separate problems back on.

### Boundary states: `aria-disabled`, not absent

`<c-pagination>` today **omits** Previous/Next at the boundaries (`{% if page_obj.has_previous %}`).
For a swapped-in-place grid that is actively harmful:

- The control the user pressed can disappear from the DOM as a result of pressing it, so there is
  nothing left to return focus to.
- The remaining control moves position between renders, so the tab order shifts under the user.

Render both controls always. Use `aria-disabled="true"` plus suppressed activation rather than the
`disabled` attribute or omission — a `disabled` button is removed from the tab order and cannot
receive focus, which reintroduces the same problem. This is the single most consequential difference
between this component's current behaviour and what a swapped grid needs.

### Focus after the swap — the trap

`hx-swap="outerHTML"` replaces the subtree including the pressed control. When the focused element is
removed, focus falls to `<body>` and a keyboard or screen-reader user is thrown to the top of the
document. htmx does **not** solve this for you: Wagtail's measurement of htmx accessibility gaps names
"lost UI state (particularly focus) during element replacement" as one of two headline gotchas, and
its recommendations are `hx-preserve`, a morphing swap extension, or explicit handling.

Note explicitly that the htmx `focus-scroll` swap modifier (default `false`) and the `show:top` /
`show:bottom` modifiers are about **scrolling**, not about setting focus. They do not solve this.

Required behaviour, in order of preference:
1. Return focus to the control that was pressed in the newly rendered group — possible **because**
   the control is always rendered (see above).
2. If that control is now at a boundary, move focus to the group's `<h2>` with `tabindex="-1"` —
   possible **because** the `<h2>` is outside the swap boundary (§3).
3. Never let focus fall to `<body>`.

Also: do not scroll the page after the swap. Leave `show:` off. If the last page is short the page
reflows under the user — accept that; do not pad the grid with empty cards to keep the height stable.

### Announcing the change — WCAG 4.1.3 Status Messages (AA)

A polite live region must announce the new position ("Wellbeing courses, showing 4 to 6 of 19"),
without moving focus. `role="status"` (implicitly `aria-live="polite"`) plus `aria-atomic="true"` so
the whole sentence is read rather than the changed characters.

**The caveat that matters and is usually missed:** a live region that is *itself inserted* by the swap
is frequently not announced, because screen readers watch live regions that already existed for
mutations. So either

- the element carrying `aria-live` sits **outside** the swapped fragment and only its contents are
  updated, or
- a single page-level `role="status"` region is updated **out of band** (`hx-swap-oob`) alongside the
  group swap.

This is the one legitimate use of OOB swaps in this feature. Note it, so it does not get quietly
dropped.

Do **not** put `role="status"` on a heading — that is the exact `aria-allowed-role` anti-pattern
Wagtail found in htmx's own documentation examples.

### Remaining checklist

- Controls stay `<a href>` with an HTMX enhancement (existing component shape) — keyboard, no-JS and
  crawler support all fall out of that. Do not convert them to `<button>`.
- Visible focus indicator on both controls.
- Touch targets: the existing component uses `px-4 py-3` on the mobile layout; keep that scale.
- Page size should be a multiple of the grid's column counts. The dashboard grid is
  `md:grid-cols-2 lg:grid-cols-3` (1 / 2 / 3 columns), so a page size divisible by 6 — practically, 6
  — gives a full final row at every breakpoint on every page but the last.
- Heading structure survives the swap (see §3).
- CSRF: pagination is GET; CSRF is already set globally on `<body>`. Nothing to add.

---

## 5. Next/prev without page numbers — the honest downsides, and the verdict

### What the research actually says

- **Baymard** (large-scale e-commerce product-list study): test subjects "explicitly complained about
  pagination", generally "perceived pagination to be slow", and where only 15 items load per page,
  "getting an overview of a reasonable number of products necessitates loading 4 or 5 pages", which
  "consistently slowed down users' product scanning process". Their preferred pattern is a "Load
  more" button combined with lazy-loading.
- **NN/g**: infinite scroll is wrong when users need to "find something specific" or "compare items in
  a long list", and "in an infinite list of items, it is hard to remember the location of any specific
  item and return to it". A load-more button "reduces cognitive load by chunking content while still
  keeping the user in control", at the cost of increased interaction cost. Traditional pages are "a
  great option for products that don't have a lot of content".
- **GOV.UK**: use previous/next-only for content split in a specific order; use numbered links plus
  previous/next "for lists of similar items". By that rule, a grid of courses is a list of similar
  items and *should* have numbers.

### The honest downsides of next/prev-only

- Reaching page 5 is five round trips and five swaps. Deep positions are effectively unreachable.
- Without numbers there is no at-a-glance "how much is there" and no sense of depth — the user cannot
  see that there are 4 pages, only that there is a Next.
- No stable landmark to return to: "the one I saw two pages back" requires two Previous clicks.
- Mitigations: the "Showing 4–6 of 19" count and a "Page 2 of 4" label restore the *sense of scale*
  but not the *reachability*. They are necessary and not sufficient.

### Verdict: yes for this dashboard, with conditions

The Baymard and NN/g findings are drawn from **e-commerce product lists and search results**, where
the task is "scan many candidates to find one". A learner dashboard group is not that task. The
dashboard is a launchpad; the catalogue already exists at `/courses/`, renders every course flat with
schema.org `ItemList` JSON-LD, and is already linked from the dashboard ("Browse all courses" in the
`available-courses` partial). Deep browsing has a better home than a home-page group.

Two further points in next/prev's favour, specific to this page:

- Numbered controls × N groups is a lot of chrome competing with the cards. This is why the educator
  progress panel — the other multi-paginator surface in this codebase — reads as prev/next with a
  range indicator.
- With ~6 cards per group, most groups will have 1–3 pages, where numbers buy little.

Conditions for the verdict to hold:

1. The count is always stated ("Showing 4–6 of 19 courses"). Without it, no.
2. Each group has a one-click escape into the full catalogue for that group. If a group's page 5 is
   only reachable by clicking Next five times, that group's real answer is a link, not pagination.
3. If a group routinely exceeds ~4 pages, the answer is not more pagination — it is that the group is
   the wrong shape for a dashboard and should be a link to a filtered catalogue.

---

## 6. Django and HTMX mechanics — the constraint the idea must acknowledge

### What `Paginator` gives you

It accepts any object with `count()` or `__len__()`, so a Python list works out of the box. It prefers
`count()` when available (which is how querysets get an efficient `COUNT(*)`). `get_page()` is the
view-safe entry point: it clamps out-of-range and non-integer page numbers instead of raising, which
is exactly what a public home page wants. `page()` raises `EmptyPage` and should not be used here.

### Where it hurts on this page

Both dashboard sequences are Python lists assembled in the view **after** per-learner work:

- `get_current_courses` (`freedom_ls/learner_interface/utils.py`) fetches **all** of the learner's
  registrations, resolves course progress records for all of them, then filters completed courses out
  in Python and stamps `progress_percentage` as an instance attribute. Both the filter and the
  percentage exist only after that full pass.
- `_available_courses` (`freedom_ls/learner_interface/views.py`) iterates
  `backend.filter_visible(user, get_all_courses())`, stamping `is_registered`, an access badge and a
  `listing_status` on each course, and breaks at 3. It is already a hand-rolled "first N".
- `get_course_listing` is the same shape at catalogue scale.

So: **pagination cannot be pushed into the database as things stand.** `Paginator(queryset, n)` would
give `COUNT(*)` + `LIMIT`/`OFFSET`. `Paginator(list, n)` gives neither — the list is fully materialised
before it is sliced. Per-learner annotation forces list-level paging.

### What that costs at ~200 courses

Paid on every dashboard render regardless of which page any group is on:

- one query for all site courses through `filter_visible`, plus one `get_access_badge` and one
  `is_coming_soon_for_display` per course — O(200);
- the grouping pass over all of them — O(200);
- for an authenticated learner, resolving every registration and every course progress record.

No longer paid, once paginated:

- per-card template rendering for cards not on the current page;
- for In Progress, the per-course `backend.get_access` + `_annotate_next_up` → `get_course_index`,
  which is the expensive one — capped at the page size instead of scaling with registration count.

The win is real but bounded by an O(all courses) floor. The idea must acknowledge one of:

- **(a)** accept the floor — fine at 200 courses, questionable at thousands; or
- **(b)** design group membership as a queryset (a real relation or ordering on the model) rather than
  a Python partition of "all courses", which is what would let `Paginator` reach the database.

That choice belongs in the spec, but the idea should state which it assumes.

### Ordering

`Paginator` raises `UnorderedObjectListWarning` for an unordered queryset. With a Python list there is
no warning and no safety net — the order is whatever the view built. **Each group must define a total,
stable order**, or cards will shuffle between page requests and a learner will see the same course
twice or never. This is a correctness requirement, not a nicety.

---

## 7. Where this argues against the working assumption

Three places. None of them is a silent substitution — flagging, not deciding.

### 7.1 "Minimal next/prev" is not what the shared component renders

`<c-pagination>` renders **numbered** controls with First/Last on desktop, and prev/next + "Page X of
Y" only on mobile. So "minimal next/prev buttons" is a **new variant**, not the existing pattern. The
project convention ("if the project already has a paginated list pattern, reuse it") and the user's
stated preference point in opposite directions. The options are:

- add a next/prev-only variant to the shared component — the dashboard then looks deliberately
  different from every educator table, and the component gains a mode that also changes a
  theme-override surface (`themes/<slug>/templates/cotton/pagination.html`); or
- accept the component as-is: numbered on desktop, prev/next on mobile.

Also relevant: the last consolidation effort in this repo
(`spec_dd/3. done/2026-05-05_10:10_educator-experience-bug-fix/`) existed specifically because the
project had **two** pagination styles and wanted one. Adding a third mode reopens that. Worth an
explicit decision in the spec rather than an implicit one.

### 7.2 In Progress is the weakest case for pagination

In Progress is the one group where the learner has a genuine **known-item** task: "get back into the
thing I was doing". That is precisely the task NN/g identifies as badly served by patterns that hide
items behind sequential navigation. A learner registered for 12 courses would need up to two Next
clicks to reach a course they can currently see immediately, with no way to view all twelve at once.

Cap-with-expand ("Show all 12") reaches the full set in one click with no round trip, and is the
pattern the task brief explicitly set aside.

Counterweight, and it is a real one: In Progress carries the most expensive per-card work on the page
(`get_course_index` per registered course), so paginating it is the biggest performance win available.

Verdict: pagination for In Progress is **defensible** if the page size is generous (6, not 3) and the
count is stated. At a page size of 3 it will annoy people, and the annoyance will be reported as a bug.

### 7.3 The anonymous dashboard has no reason to paginate aggressively

See §8. The performance argument for pagination is an authenticated-user argument; for an anonymous
visitor the dashboard is *only* discovery, and hiding most of the catalogue behind Next on the site's
home page is a marketing loss for no compute saving worth having.

---

## 8. Anonymous visitors and SEO

### What is already true

- The dashboard **is** `/` — `config/urls.py` includes `freedom_ls.learner_interface.urls` at the root
  and `learner_interface/urls.py` maps `""` to `views.dashboard`. It is public and shares one code
  path across auth states.
- Every course already has its own crawlable canonical URL (`/courses/<slug>/detail/`) and is in
  `CourseSitemap` (`config/sitemaps.py`). `/courses/` renders the full flat listing with schema.org
  `ItemList` JSON-LD.
- **No course is reachable only via a dashboard page 2.** That single fact removes most of the SEO
  risk.

### Crawlability

Google deprecated `rel="next"`/`rel="prev"` in 2019; current Search Central guidance is that each page
in a paginated sequence gets its own canonical URL, that paginated content should not be blocked from
crawling, and that the first page should not be used as the canonical for the rest. That guidance is
written for sequences where the paginated pages are the *only* route to the content — which is not the
case here.

Because the catalogue is the canonical discovery surface:

- keep the dashboard's canonical pointing at `/`;
- do not add paged variants of `/` to the sitemap;
- do not block them either — there is nothing to hide, and the query-parameter variants are
  near-duplicates of a page whose primary content is unchanged.

The one hard requirement: **the controls must be real `<a href>` with a resolvable URL**, not
JS-only buttons. That is what makes the paged content reachable by a crawler and by a no-JS visitor at
all. The existing component already does this; preserve it.

### Should the anonymous view paginate differently?

Arguments that it should paginate *less*:

- Anonymous visitors have no In Progress and no Learning History; the dashboard is purely discovery
  for them. Fewer courses visible on the home page is a direct conversion cost.
- The anonymous render is cheap — `_available_courses` does no per-learner progress work, only
  `get_access_badge` and `is_coming_soon_for_display` per course. The compute case for pagination is
  an authenticated-user case.
- An anonymous dashboard could plausibly be cached whole; per-visitor query strings work against that.

Argument that it should paginate the same: page weight and above-the-fold clarity apply to everyone,
and an un-paginated home page on a 200-course site is a bad home page.

Recommendation: **one mechanism, one code path** — the view already shares one and splitting it would
be a maintenance cost for no benefit — but allow **page size to vary**, and lean on the per-group
"See all" link into `/courses/` as the anonymous escape hatch. Do not design a second pagination
scheme for anonymous visitors.

---

## 9. Project conventions a paginated group must follow

From `claude_plugins/django-stack/skills/htmx/SKILL.md` and
`claude_plugins/fls-dev/resources/templates_and_cotton.md`:

- Always specify `hx-target` and `hx-swap` **together**; prefer `outerHTML`.
- Keep sort/search/pagination state in **query parameters, not request bodies** — the skill says this
  explicitly and gives the pagination example.
- CSRF is set globally via `hx-headers` on `<body>`. Never add a token to an individual request.
  Pagination is GET, so this is a non-issue — but do not "helpfully" add one.
- **422 is for HTMX validation errors on submitted data.** A bad or out-of-range page number in a URL
  is not a validation error. Clamp with `Paginator.get_page()` and return 200. (`form_fill_page` in
  `learner_interface/views.py` is the correct use of 422 in this app — a rejected submission.)
- View functions that return HTMX partials are prefixed `partial_`.
- Detect HTMX with `request.headers.get("HX-Request") == "true"`; serve the fragment for HTMX and the
  full page otherwise, so the `href` fallback works.
- Cotton components live at `freedom_ls/base/templates/cotton/<name>.html` and are theme-shadowable at
  `themes/<slug>/templates/cotton/<name>.html` — any change to `pagination.html` is a theme-override
  surface, and themes shipping their own copy would not inherit it.
- `app_name` in `urls.py`; URL names snake_case, URL paths kebab-case; type hints on all functions, no
  `Any`; `select_related`/`prefetch_related` for related-object queries.

Vocabulary (`.claude/skills/domain-glossary/SKILL.md`): use **group** for a dashboard division (the
idea's word), and Django's **page / page number / page size / paginator** for the pagination concepts.
Do not use `item`, `collection` or `slot` for anything here — all three are taken. Note that
`_paginate_course_items` in the educator interface already uses "course item" for positional content
in a course; do not extend that sense to dashboard cards. The user-visible string should name courses:
"Showing 4–6 of 19 courses".

---

## References

- Nielsen Norman Group — Infinite Scrolling: When to Use It, When to Avoid It:
  https://www.nngroup.com/articles/infinite-scrolling-tips/
- Nielsen Norman Group — 3 Alternatives to Infinite Scrolling (video):
  https://www.nngroup.com/videos/alternatives-to-infinite-scrolling/
- Baymard Institute — Product List UX: Number of Products to Load:
  https://baymard.com/blog/number-of-items-loaded-by-default
- Smashing Magazine (Baymard) — Infinite Scrolling, Pagination Or "Load More" Buttons? Usability
  Findings In eCommerce:
  https://www.smashingmagazine.com/2016/03/pagination-infinite-scrolling-load-more-buttons/
- W3C WAI — Understanding SC 4.1.3: Status Messages:
  https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- W3C WAI — F103: Failure of SC 4.1.3 (status messages not programmatically determinable):
  https://www.w3.org/WAI/WCAG21/Techniques/failures/F103
- GOV.UK Design System — Pagination:
  https://design-system.service.gov.uk/components/pagination/
- U.S. Web Design System — Pagination:
  https://designsystem.digital.gov/components/pagination/
- W3C Design System — Pagination:
  https://design-system.w3.org/components/pagination.html
- Primer — Pagination accessibility:
  https://primer.style/product/components/pagination/accessibility/
- MDN — `aria-current`:
  https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-current
- MDN — `aria-live`:
  https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live
- Wagtail — htmx accessibility gaps: data and recommendations:
  https://wagtail.org/blog/htmx-accessibility-gaps-data-and-recommendations/
- htmx documentation (swap modifiers `show` / `focus-scroll`, `hx-preserve`, `hx-push-url`,
  `hx-swap-oob`): https://htmx.org/docs/
- Django — Pagination topic guide: https://docs.djangoproject.com/en/6.0/topics/pagination/
- Django Endless Pagination — Multiple paginations in the same page (prior art for namespaced
  querystring keys): https://django-endless-pagination.readthedocs.io/en/latest/multiple_pagination.html
- Google Search Central — Pagination and incremental page loading:
  https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading
- Search Engine Land — Pagination and SEO: what you need to know (rel=next/prev deprecation):
  https://searchengineland.com/pagination-seo-what-you-need-to-know-453707

### In-repo references

- `freedom_ls/base/templates/cotton/pagination.html` — the shared component
- `freedom_ls/base/templatetags/pagination_tags.py` — `join_query`, `pagination_suffix`
- `freedom_ls/base/tests/test_pagination_component.py` — current test coverage (no a11y assertions)
- `freedom_ls/panel_framework/tables.py` — `DataTable.get_rows`, queryset-backed pagination
- `freedom_ls/educator_interface/views.py` — `CohortCourseProgressPanel._paginate_course_items`,
  `._paginate_learners`
- `freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html` —
  the existing two-paginators-on-one-URL call site
- `freedom_ls/learner_interface/views.py` — `dashboard`, `_available_courses`,
  `_annotate_registered_courses`, `all_courses`
- `freedom_ls/learner_interface/utils.py` — `get_current_courses`, `get_course_listing`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html` — the group
  partialdefs and grid
- `config/urls.py`, `config/sitemaps.py` — dashboard at `/`, course and static sitemaps
- `spec_dd/3. done/2026-05-05_10:10_educator-experience-bug-fix/research_pagination.md` — the earlier
  consolidation research that produced `<c-pagination>`

status: ok
