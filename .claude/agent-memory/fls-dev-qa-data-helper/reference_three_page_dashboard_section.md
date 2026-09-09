---
name: Making a dashboard category section span THREE pages (focus-management QA)
description: qa_extend_start_here_section; why 2 pages cannot exercise courseSectionPagination's primary branch; why the new courses must NOT join PAGINATION_LETTERS; the pager's real arrow markup
metadata:
  type: reference
---

Written Sep 2026 on `better-learner-dashboard-course-display` (DemoDev, site pk 3).
Follows [[reference_dashboard_catchall_courses_command]] and
[[reference_dashboard_paging_fixture_teardown]].

## Why "it pages" is not the same as "it is testable"

`courseSectionPagination` in
`freedom_ls/learner_interface/static/learner_interface/js/alpine-components.js`
does, on `htmx:afterSwap`:

```js
const control = this.$el.querySelector(`[data-direction="${this.pressed}"]`);
const target = control && control.getAttribute("aria-disabled") !== "true"
    ? control : this.$el.querySelector("h2");
target?.focus({ preventScroll: true });
```

With **two** pages every paging action lands on a boundary page, so the arrow
just pressed is always `aria-disabled` afterwards and **only the `h2` fallback
branch can run**. The primary branch (focus returns to the live arrow) needs a
*middle* page, i.e. **three** pages minimum — `2 * SECTION_PAGE_SIZE + 1` items.

Generalise: whenever a QA plan asks to exercise "focus goes back to the control",
count pages, not rows. Two pages is the classic under-seed.

`SECTION_PAGE_SIZE = 3`, in `freedom_ls/learner_interface/dashboard_sections.py`
(not `views.py` — grep the whole app).

## The command

`freedom_ls/qa_helpers/management/commands/qa_extend_start_here_section.py`

```
uv run python manage.py qa_extend_start_here_section [DemoDev] \
    [--category-slug start-here] [--letters E,F,G]
```

Imports `_get_site` / `_get_category` / `_ensure_pagination_course` from
`qa_create_dashboard_paging_fixtures` (the established `qa_helpers`
cross-command import convention), so `Pagination E/F/G` are byte-for-byte the
same shape as `A`-`D`. Prints per-course registration and recommendation counts
as an assertion that they stayed discovery-only.

**Do NOT just append to `PAGINATION_LETTERS`** in
`qa_create_dashboard_paging_fixtures`. Seed B registers `demodev_paging` on
every letter in that list and indexes `PAGING_REGISTERED_DAYS_AGO[slug]`, so
extra letters would (a) `KeyError` and (b) hand the new courses the
registrations the brief excluded. Registered courses also drop out of the
persona's own category section, so it would not even have produced 9.

Start here on DemoDev after the run: 9 courses = 3 pages.

## The pager's actual arrow markup

Verified anonymously (`Client(SERVER_NAME="127.0.0.1")`, `HTTP_HOST=127.0.0.1:8000`,
`ALLOWED_HOSTS` topped up, dashboard at `/`, section param `?page_start-here=N`,
swap id `section-page-start-here`):

| page | previous | next | status |
|---|---|---|---|
| 1 | `<a aria-disabled="true">`, no href | live, `/?page_start-here=2` | `1 to 3 of 9` |
| 2 | live, `/` | live, `/?page_start-here=3` | `4 to 6 of 9` |
| 3 | live, `/?page_start-here=2` | `<a aria-disabled="true">`, no href | `7 to 9 of 9` |

Two things that break naive selectors:

- the value is **`data-direction="previous"`**, not `"prev"`;
- a **live** arrow has **no `aria-disabled` attribute at all** — the component
  tests `!== "true"`, so absent passes, but a regex looking for
  `aria-disabled="false"` finds nothing and wrongly reports the arrow disabled.

Both arrows are `<a>` in every state; the disabled one simply drops its `href`.
