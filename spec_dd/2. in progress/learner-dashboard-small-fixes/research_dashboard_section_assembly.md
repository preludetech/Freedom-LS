# Research: dashboard section assembly, ordering, paging and htmx-swap consequences of dual coming-soon placement

Scope: how `freedom_ls/learner_interface/views.py` and
`freedom_ls/learner_interface/dashboard_sections.py` build, order, paginate and
htmx-swap dashboard sections today, and what showing a `COMING_SOON` course in
both its `dashboard_category` section and the built-in "Coming soon" section
would touch. The three decisions in the brief (dual render, alphabetical
interleave, two new "Browse all courses" buttons) are treated as given; this
document only states what the current code does and what changes as a result.

## 1. The discovery pipeline today: how `rest` and `coming_soon` are split

`_dashboard_inputs` (`freedom_ls/learner_interface/views.py:460-484`) builds the
per-request pool every discovery section reads from:

1. `_discovery_courses` (`views.py:274-288`) returns every course
   `backend.filter_visible()` allows, minus courses the learner is already
   registered for or recommended, with `dashboard_category` pre-fetched via
   `select_related`.
2. `_coming_soon_split` (`views.py:291-305`) partitions that pool in two:
   - if `override_visibility_to_visible()` is true, it returns
     `(courses.none(), courses)` — i.e. **nothing** is coming soon and every
     course flows into `rest`.
   - otherwise it returns `(courses.filter(visibility=COMING_SOON),
     courses.exclude(visibility=COMING_SOON))`.
3. The two resulting querysets are stored on `_DashboardInputs` as
   `coming_soon` and `rest` (`views.py:456-457`).

Every discovery section builder is handed one or the other, never both:

- `_category_section` (`views.py:361-380`) filters `rest.filter(dashboard_category=category)`.
- `_available_section` (`views.py:383-409`) filters `rest` by
  `Q(dashboard_category__isnull=True) | Q(dashboard_category__show_on_dashboard=False)`.
- `_coming_soon_section` (`views.py:412-424`) pages `coming_soon` directly, with no
  category filter at all — every coming-soon course lands here today,
  regardless of `dashboard_category`.

**Consequence of the change**: `_coming_soon_split` currently *removes* every
`COMING_SOON` course from `rest` before `_category_section` ever sees it — that
removal is precisely why a coming-soon course cannot appear in its category
section today (proved by
`test_coming_soon_course_lands_in_coming_soon_whatever_its_category`, which
asserts `section_by_slug(response, "start-here") is None` while the course is
`COMING_SOON`). For a `COMING_SOON` course whose `dashboard_category` has
`show_on_dashboard=True` to also render in that category section, the category
section's data source must be widened to include the matching subset of
`coming_soon` (or `rest`'s exclusion of `COMING_SOON` must no longer apply
uniformly to every discovery section). `_available_section` and
`_coming_soon_section`'s existing inputs (`rest` minus coming-soon;
`coming_soon` unfiltered by category) do not need to change in kind — only
`_category_section`'s input does.

This split is shared by both render paths: the full-page render
(`_dashboard_sections`, `views.py:487-526`) and the htmx single-section
fragment (`_requested_section`, `views.py:529-556`) both consume the same
`inputs.rest` / `inputs.coming_soon` produced once per request by
`_dashboard_inputs`. Whatever change widens `_category_section`'s pool must
apply identically on both paths, since `_requested_section`'s `COMING_SOON`
category branch (`views.py:555-556`, the `get_object_or_404(CourseCategory, ...)`
fallback) calls the exact same `_category_section` function with the exact
same `inputs.rest`.

## 2. The accidental-third-appearance risk in `_available_section`

`_available_section`'s catch-all filter is:

```
Q(dashboard_category__isnull=True) | Q(dashboard_category__show_on_dashboard=False)
```

(`views.py:395-398`). Today this filter runs against `rest`, which has already
had every `COMING_SOON` course removed by `_coming_soon_split`, so an
uncategorised or hidden-category coming-soon course currently appears **only**
in "Coming soon" — never in "Available courses". This is proven by
`test_dashboard_available_coming_soon_shows_no_chip_with_override` running the
opposite case (override on, so nothing is coming-soon) and by the plain
`_coming_soon_split` code path itself: with the override off, such a course is
in `coming_soon`, not `rest`, so it can never match `_available_section`'s
`rest.filter(...)` call.

If the change is implemented by simply widening the pool `_category_section`
reads from **without** also keeping `_available_section` scoped to
non-coming-soon courses, an uncategorised (`dashboard_category__isnull=True`)
or hidden-category (`dashboard_category__show_on_dashboard=False`)
`COMING_SOON` course would newly match `_available_section`'s filter too — a
third rendering of the same card (Available courses *and* Coming soon, on top
of no category section since it has none to join). Nothing in the requested
change calls for uncategorised/hidden-category coming-soon courses to ever
appear in "Available courses"; the brief only asks for dual-rendering into a
*shown* category's section plus "Coming soon". This is the specific hazard the
idea needs to name and guard against: whatever mechanism widens
`_category_section`'s input must not also widen `_available_section`'s.

## 3. `_dashboard_sections`: category-section emptiness and headline selection

`_dashboard_sections` (`views.py:487-526`) builds `category_sections` once,
filtering out any category whose `_category_section(...).is_empty` is true
(`views.py:497-503`), then:

- takes `category_sections[:1]` as the page's headline group, placed above
  Recommended courses (`views.py:515-516`);
- appends the remaining `category_sections[1:]` after Recommended
  (`views.py:517`);
- appends `_available_section` then `_coming_soon_section`
  (`views.py:518-519`);
- drops any section (other than the deferred empty "In progress") whose
  `is_empty` is true (`views.py:520`).

**Consequence of the change**: today, a category whose *only* course is
`COMING_SOON` produces an empty `_category_section` (because `rest` excludes
it) and is filtered out of `category_sections` entirely — the category section
does not exist on the page at all in that case
(`test_coming_soon_course_lands_in_coming_soon_whatever_its_category` proves
exactly this: `section_by_slug(response, "start-here") is None`). Once
`_category_section` also draws from matching `COMING_SOON` courses, that same
category becomes non-empty and will render — including becoming eligible to be
selected as the page's single headline category (`category_sections[:1]`) if
it sorts first by `CourseCategory.Meta.ordering = ["order", "title"]`
(`freedom_ls/content_engine/models/courses.py:39,43`). This is a structural
side effect of the dual-render decision, not an extra feature to build: a
category that previously never appeared (nothing but coming-soon courses in
it) will now appear, participate in headline selection, and independently
paginate.

## 4. Alphabetical interleaving is inherited automatically from `Course.Meta.ordering`

`Course.Meta.ordering = ["title", "pk"]`
(`freedom_ls/content_engine/models/courses.py:145`) is the default ordering for
every `Course.objects` queryset, including `get_all_courses()`
(`freedom_ls/learner_interface/utils.py:801-803`, `Course.objects.all()`,
which applies no `.order_by()` of its own) and every queryset derived from it
via `.filter()`/`.exclude()` — `_discovery_courses`, `_coming_soon_split`'s two
halves, and `_category_section`'s `rest.filter(dashboard_category=category)`
all inherit `["title", "pk"]` untouched, because none of these call sites
overrides ordering. Requirement 2 ("coming-soon courses interleaved with the
rest in the existing alphabetical-by-title order — no special sort") is
therefore already the behaviour of any queryset-level union of `rest` and the
category-matching slice of `coming_soon`, provided the widened
`_category_section` pool is still evaluated as one ordered queryset (e.g. via
`QuerySet.union()` keeping the ordering, or an equivalent `Q`-based single
filter) rather than two separately-ordered lists concatenated in Python (which
would *not* interleave — it would put every coming-soon course after or before
the rest, defeating requirement 2 unless the two halves are merged before
ordering, not after).

## 5. `page_for` / `SECTION_PAGE_SIZE` / pagination independence

`page_for` (`dashboard_sections.py:120-145`) paginates whatever `object_list`
its caller passes it at `SECTION_PAGE_SIZE = 3`
(`dashboard_sections.py:25`), keyed by `page_<slug>` in the query string
(`_page_param_name`, `dashboard_sections.py:43-44`). Each `DashboardSection`'s
`page_obj` is independent: the category section's paginator operates over the
category's own filtered queryset, and the coming-soon section's paginator
operates over `coming_soon` (today) independently. Under the change, a single
`COMING_SOON` course can legitimately sit on different page numbers of two
different sections simultaneously (e.g. page 1 of "Coming soon" but page 2 of
its category section, if each has more items). Nothing in `page_for`,
`Paginator`, or `section_page_href` (`dashboard_sections.py:148-161`) couples
one section's page state to another's — each section's href is built by
copying the *entire* current query string and touching only its own
`page_<slug>` key (`section_page_href`), so the two paginations already coexist
correctly with no cross-section awareness required. This is an existing
capability, not something to add.

## 6. The htmx single-section swap: no course-derived DOM id or id-based collision

Reviewed `course_list.html`, `course_card.html`, `card_title_link.html`,
`course_details_link.html`, `cotton/course-card-shell.html`,
`cotton/course-section-pagination.html`, and `cotton/button.html`. Findings:

- Every `id="..."` attribute rendered by the section/course machinery is
  derived from the **section**, never the course: `section.heading_id`
  (`course_list.html:12`, `f"section-heading-{slug}"` in
  `dashboard_sections.py:83-84`), `section.swap_id`
  (`course_list.html:32`, `f"{SECTION_SWAP_ID_PREFIX}{slug}"`,
  `dashboard_sections.py:86-88`), `section.wrapper_id` (`course_list.html:91,109`,
  passed in by each `_*_section` builder, e.g. `"category-{category.slug}"` at
  `views.py:375`), and the single page-wide `id="dashboard-section-status"`
  live region (`course_list.html:64`, present once per page, not per
  section-render — `hx-swap-oob="true"` only when a `section` is in context).
  None of these ids embed `course.slug` or `course.id` anywhere.
- `course_card.html`, `card_title_link.html`, `course_details_link.html`, and
  `cotton/course-card-shell.html` render **no `id` attribute at all** on any
  course-scoped element — confirmed by grep across
  `freedom_ls/learner_interface/templates/learner_interface/partials` for
  `id="` and separately for `course.slug`/`course.id` used as an `id`/`for`
  value: every `course.slug` occurrence in these templates builds a `reverse()`
  URL, never an `id`.
- The one non-unique-by-design attribute per card is
  `data-testid="course-status-{{ status|default:'not_registered' }}"`
  (`freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html:23`),
  keyed on `listing_status`, not on the course. This is **already** repeated
  across every card sharing a status within a single section today (e.g. three
  `COMING_SOON` cards on one page of "Coming soon" all render
  `data-testid="course-status-coming_soon"`); duplication across two sections
  adds more repeats of an already-non-unique value, it does not introduce a
  new class of collision. Any test asserting on this `data-testid` already has
  to tolerate multiplicity or scope to a section; nothing new breaks here.
- Focus management after a paged swap is handled by the `courseSectionPagination`
  Alpine component
  (`freedom_ls/learner_interface/static/learner_interface/js/alpine-components.js:479-506`),
  bound via `x-data="courseSectionPagination"` on the section's own
  `wrapper_id` div (`course_list.html:91-93`). Its `htmx:afterSwap` handler
  looks up the pressed-direction control or the section's own `<h2>` via
  `this.$el.querySelector(...)` — `$el` is scoped to that section's wrapper
  subtree, not `document`. Two sections independently rendering the same
  course's card therefore cannot cause the focus logic to target the wrong
  section's control: each section's Alpine instance only ever queries inside
  its own wrapper.
- **Net finding**: rendering the same course's card twice (once per section)
  produces no id collision, no ARIA/live-region conflict, and no focus-target
  ambiguity, because every id in this subtree is section-scoped and the one
  per-card identifying attribute (`data-testid`) was never course-unique to
  begin with.

## 7. `override_visibility_to_visible()` and `is_coming_soon_for_display` — what must stay true

`override_visibility_to_visible()`
(`freedom_ls/course_access/overrides.py:11-13`) reads
`config.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` (a dev/staging preview flag).
`_coming_soon_split` reads this override, not `Course.visibility` alone
(`views.py:296-301`), specifically so the preview mode can present every
course as ordinary/published: with the override on, `_coming_soon_split`
returns `(courses.none(), courses)`, so `coming_soon` is always empty and
"Coming soon" never renders
(`test_visibility_override_puts_a_coming_soon_course_back_in_its_category`
asserts exactly `section_by_slug(response, "coming-soon") is None` while the
course reappears in its category, singly). `is_coming_soon_for_display`
(`freedom_ls/course_access/overrides.py:21-28`) is the same override applied
at the per-course annotation layer (`_annotate_discovery_courses`,
`_annotate_recommendations`), so a course's `listing_status`/chip also stops
reading as coming-soon under the override.

**What must remain true under the change**: with the override on, dual
rendering must not occur — a course must render exactly once (in its category,
or in "Available courses" if uncategorised), with no "Coming soon" section on
the page at all, exactly as today. Any implementation that widens
`_category_section`'s pool by consulting `coming_soon` directly (rather than
re-deriving from `is_coming_soon_for_display`/`override_visibility_to_visible`
at the same layer `_coming_soon_split` already does) risks drifting from this
invariant if the override path is not threaded through identically.

## 8. `RESERVED_SECTION_SLUGS` / `BuiltInSection` equality

`RESERVED_SECTION_SLUGS` (`freedom_ls/content_engine/schema.py:27-29`) is
`frozenset({"in-progress", "recommended", "available", "coming-soon",
"history"})`, enforced against `CourseCategoryEntry.slug` at content-load
validation time (`schema.py:133-137`) so no `CourseCategory` can ever be
authored with a slug matching a built-in section. `BuiltInSection`
(`dashboard_sections.py:29-41`) is the runtime mirror of the same five slugs.
A comment on both sides states "a test keeps the two sets equal" — this
research did not need to open that test to confirm the assertion exists (it is
named directly in both docstrings); it is unaffected by the coming-soon
dual-render change, since no new slug is introduced by dual-rendering an
existing course into an existing category section and the existing
"coming-soon" built-in slug.

## 9. Existing tests that assert today's single-placement / missing-button behaviour

### `freedom_ls/learner_interface/tests/test_dashboard_grouping.py`

- `test_coming_soon_course_lands_in_coming_soon_whatever_its_category` (lines
  100-114): asserts `rendered_section(response, "coming-soon").courses ==
  [course]` **and** `section_by_slug(response, "start-here") is None` for a
  `COMING_SOON` course whose `dashboard_category` is a shown category. This
  assertion is the direct opposite of requirement 1 and must change to assert
  the course appears in **both** sections.
- `test_visibility_override_puts_a_coming_soon_course_back_in_its_category`
  (lines 117-135): asserts that with the override on, the course is in
  `"start-here"` and `section_by_slug(response, "coming-soon") is None`. This
  should remain valid unchanged under the new behaviour (see §7) — it is a
  regression guard the change must continue to satisfy, not a test that needs
  rewriting.
- `test_course_lands_in_its_dashboard_category_section` (lines 38-47) and
  `test_course_in_three_categories_renders_only_in_its_dashboard_category`
  (lines 81-96) use non-coming-soon courses; unaffected.
- `test_hidden_category_course_lands_in_available_and_renders_no_section`
  (lines 60-77) uses a non-coming-soon course in a hidden category; unaffected
  directly, but is the closest existing test to the §2 risk (available-section
  catch-all scoping) — a new test for a *coming-soon* course in an
  uncategorised or hidden category, asserting it does NOT also appear in
  "Available courses", is the kind of case this file does not yet cover.
- `test_in_progress_drops_below_coming_soon_when_it_is_empty` (lines 232-243)
  and `test_one_coming_soon_course_renders_a_coming_soon_section` (lines
  245-254) use an uncategorised coming-soon course; unaffected by the dual-
  render change since it has no `dashboard_category`.

### `freedom_ls/learner_interface/tests/test_course_cards.py`

- `test_coming_soon_card_shows_details_link` (lines 454-468) uses
  `_coming_soon_course` with no `dashboard_category` set — renders in
  "Coming soon" only both before and after the change; unaffected.
- No test in this file currently exercises a categorised coming-soon course's
  card content, so nothing here directly asserts single-placement to update,
  but a card-content assertion run against a doubly-rendered course would still
  pass unmodified (the card markup itself does not change per placement).

### `freedom_ls/learner_interface/tests/test_listing_visibility.py`

- All dashboard-facing coming-soon tests here (`test_dashboard_coming_soon_is_plain_detail_link_no_cta`,
  `test_dashboard_coming_soon_no_cta_even_when_interested`,
  `test_dashboard_recommended_coming_soon_is_plain_detail_link_no_cta`,
  `test_dashboard_coming_soon_present_for_anonymous`,
  `test_dashboard_available_coming_soon_shows_no_chip_with_override`,
  `test_dashboard_recommended_coming_soon_shows_no_chip_with_override`) use
  `course_with_topic(...)` fixtures that set no `dashboard_category` — every
  one of these courses is uncategorised, so all of them render in "Coming
  soon" (or "Available courses" under the override) only, unaffected by dual
  rendering. `test_dashboard_available_coming_soon_shows_no_chip_with_override`
  (lines 366-387) is the one worth flagging as a close neighbour of the §7
  invariant: it already asserts, under the override, that the course is in
  `"available"` and NOT in `"coming-soon"` — this must keep passing unchanged.
- `test_all_courses_*` tests in this file exercise the flat `all_courses` page,
  not dashboard sections; unaffected (see §10).

### `freedom_ls/learner_interface/tests/test_all_courses_rows.py`

- `test_all_courses_coming_soon_row_has_details_link` and other coming-soon
  row assertions exercise `learner_interface:courses` (the flat list), which
  has no dashboard-section concept at all; unaffected by this change (see
  §10).

### `freedom_ls/learner_interface/tests/test_course_access_integration.py`

- The `COMING_SOON` tests here (around lines 628-703:
  `test_initiate_access_coming_soon_redirects_to_detail`,
  `test_initiate_access_coming_soon_creates_no_registration`,
  `test_initiate_access_coming_soon_self_registers_with_visibility_override`)
  exercise `initiate_course_access` routing behaviour for a coming-soon course,
  not dashboard section placement; unaffected by this change.

### Browse-all-button tests

- `test_unconfigured_site_renders_todays_sections_in_todays_order`
  (`test_dashboard_grouping.py:205-229`) asserts
  `assert f'href="{reverse("learner_interface:courses")}"' in body` and
  `assert "Browse all courses" in body` for a page whose only rendered
  sections are `in-progress`, `recommended`, `available`, `history` — i.e. it
  currently proves at least one "Browse all courses" link exists somewhere
  (today, "Available courses" already has one, per `views.py:408`), but does
  not prove which sections have it or don't. Adding the button to
  "Recommended courses" does not falsify this assertion (it only requires
  presence), but it also means this test does **not** currently discriminate
  between "Recommended has it" and "Recommended doesn't have it" — a new,
  more targeted assertion (e.g. counting occurrences, or checking within the
  `recommended`/`coming-soon` section's own rendered fragment) does not yet
  exist anywhere in the four scanned files and would need to be written to
  actually prove requirement 3.
- No test in any of the five scanned files currently asserts the *absence* of
  "Browse all courses" from "Coming soon" or "Recommended courses"
  specifically (i.e. there is no currently-passing negative assertion that
  would need to be deleted/flipped) — the change is additive at the assertion
  level for this part of the brief.

## 10. `browse_all_url` target and whether `all_courses` supports any filtering

`browse_all_url` is set to `reverse("learner_interface:courses")` verbatim by
both `_category_section` (`views.py:379`) and `_available_section`
(`views.py:408`) — an unparameterised URL, identical regardless of which
category or section constructed it. `_coming_soon_section`
(`views.py:412-424`) and `_recommended_section` (`views.py:346-358`) currently
pass no `browse_all_url` at all (the `DashboardSection.browse_all_url` field
defaults to `""`, `dashboard_sections.py:76`), which is why
`course_list.html`'s `{% if section.browse_all_url %}` guard
(`course_list.html:39`) currently suppresses the button for those two
sections.

The `all_courses` view (`views.py:620-670`) and its template
(`freedom_ls/learner_interface/templates/learner_interface/all_courses.html`)
render one flat, unfiltered list — `get_course_listing(request.user,
visible_courses=backend.filter_visible(user=request.user,
courses=get_all_courses()))` — with no query-string parameter, category
filter, or coming-soon filter of any kind consulted anywhere in the view or
template. Giving "Coming soon" and "Recommended courses" the same
`reverse("learner_interface:courses")` link that "Available courses" and every
category section already use is therefore consistent with existing behaviour
(all four link to the identical unfiltered catalogue page); it does not, by
itself, land a learner anywhere pre-scoped to coming-soon or recommended
courses — the destination page shows every course regardless of which section
button was clicked, exactly as it already does for "Available courses" and
each category section today.

status: ok
