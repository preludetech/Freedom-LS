# Research: domain event names for successful mutations

For the open question in `idea.md`: "Exactly which domain events the modal emits on success,
named once and reused by specs 6 to 9." Scope is the DOM `HX-Trigger` event fired on a 204
response, not the server-to-server webhook registry (`base/webhook_event_types.py`), which is a
separate mechanism answering a separate question (spec 7's "which webhook events fire").

## 1. Mutations in specs 6-9 and what must refresh

| Spec | Mutation | Refreshes |
|---|---|---|
| 6 | Create `Cohort` | Cohorts table (new row). Plain "Save" navigates to the new cohort via `HX-Location`, so nothing else is on screen to refresh; "save and add another" keeps the modal open over the table. |
| 6 | Edit `Cohort` (name) | Cohorts table row, cohort detail header/overview, cohort quick view if open on that cohort, dashboard cohort list (spec 10, later). |
| 6 | Deactivate / reactivate `Cohort` | Cohorts table (status badge, drops out of the active-only default filter), cohort detail header and settings tab, cohort quick view, dashboard active-cohort stat tile. |
| 6 | Delete `Cohort` (empty only) | Cohorts table (row gone). Navigates away from the detail page via `HX-Location`, so the detail page itself needs no refresh. |
| 6 | Register / unregister `CohortCourseRegistration` | Cohort detail courses tab, cohort quick view's course list, the course's detail page listing its cohort registrations, learners' courses/progress columns and quick views for every member (access changes for the whole cohort). |
| 7 | Add a `Learner` (new or existing account) to the organisation | Learners table (new/changed row), dashboard learner-count and pending-count stat tiles; if a cohort was given in the same step, also everything membership touches below. |
| 7 | Deactivate / reactivate `Learner` | Learners table (status), learner detail header, learner quick view, cohort learners-tab rows for every cohort they belong to (status shown per row), dashboard stat tiles. |
| 7 | Resend account setup email | No structural change, but the row/quick view's "pending since" / rate-limit state should refresh so a second click is correctly disabled. |
| 7 | `CohortMembership` add / remove | Learners table (cohort column), cohort learners tab (row added/removed, member-count), learner detail overview tab and quick view (cohorts list), the affected cohort's course access columns everywhere (a membership grants/revokes every course the cohort is registered for). |
| 7 | `CohortMembership` move (remove from A, add to B, one transaction) | Both A's and B's learners tabs and member counts, the learner's cohorts list and quick view, and the learner's per-course progress record the move mints (courses tab). |
| 7 | `LearnerCourseRegistration` register / unregister | Learner detail courses tab and quick view, the course's individual-registrations list (spec 6's course detail), learners table's courses/progress column. |
| 8 | CSV import commit | Learners table (many rows), the target cohort's learners tab and member count if a cohort was given, dashboard stat tiles. Runs as a background task above a threshold, so the result page polls rather than listening for a single `HX-Trigger`. |
| 8 | Bulk add/remove cohort membership, bulk register/unregister course, bulk deactivate/reactivate, bulk resend | Same targets as the equivalent single action, once per affected row; the calling table refetches wholesale rather than per row. |
| 9 | Grant / remove an educator role (`ObjectRoleAssignment`, `SystemRoleAssignment`) | Educators table, and — only when the grant is cohort-scoped (`instructor`, `ta`) — the instructors block on that cohort's detail page. |
| 9 | Change an instructor's/TA's cohort scope | Educators table (scope column), the instructors block on every cohort added or removed from the scope. |

Two things fall out of this table. First, every mutation is owned by exactly one of four nouns
already in the domain vocabulary: `Cohort`, `Learner`, a course registration (`CohortCourseRegistration`
or `LearnerCourseRegistration` — the UI calls both "course registration"), and an educator role
grant. Second, several mutations (membership, registration) affect two entities of different types
at once and every consumer that cares about one of those types needs to hear about it, not just the
consumer that happens to be on screen for the other type.

## 2. Existing event names and style in the codebase

Grepped `freedom_ls` for `HX-Trigger`, `hx-trigger`, `from:body`, `dispatchEvent`, `$dispatch`,
`CustomEvent`. Findings, all in `freedom_ls/panel_framework/`:

- **`actions.py`**: `EditAction.form_valid` always fires the header as JSON —
  `response["HX-Trigger"] = json.dumps({"panelChanged": {"instanceTitle": str(form.instance)}})`
  — a single, generic, un-scoped event name used for every edited instance, anywhere in the
  framework. `CreateInstanceAction` fires whatever `get_created_event_name()` returns, as a bare
  string (`response["HX-Trigger"] = self.get_created_event_name()`), only on "save and add
  another" (a plain "Save" instead uses `HX-Redirect`, so nothing on screen needs telling).
  `freedom_ls/educator_interface/views.py:352` supplies `"cohortCreated"` for cohort creation;
  the framework's own tests use `"itemCreated"`.
- **`panels/_panel_base.html`**: every panel's frame carries `hx-trigger="panelChanged
  from:body" hx-target="#{{ region_id }}" hx-swap="outerHTML"`, so any panel on the current page
  refetches itself when the generic event fires anywhere in the DOM.
- **`partials/list_refresh.html`** / **`alpine-components.js`**: a list view's create actions are
  space-separated into a `data-refresh-events` attribute; the `listRefresh` `Alpine.data`
  component's `init()` calls `document.body.addEventListener(eventName, handler)` per name (plain
  JS, not an `@`-attribute binding) and re-`htmx.ajax`s the table region on receipt, ignoring
  whatever detail the event carries.
- **`views.py:402-417`**: the created-event names collected per list view are literally
  `action.get_created_event_name()` for each `CreateInstanceAction`, joined with spaces into that
  `data-refresh-events` attribute — a per-action, per-list contract, not a fixed vocabulary.
- Elsewhere (`base/templates/cotton/data-table.html`, `form_engine/inputs/file_upload.html`),
  `hx-trigger` is used only for plain DOM events (`submit`, `change`, `input delay:300ms
  from:#id`), nothing domain-specific.

**Style**: every custom event name in the codebase is **camelCase**, **verb-suffixed with
"Changed"/"Created"** (`panelChanged`, `cohortCreated`, `itemCreated`), **no dots, no colons, no
namespacing**. `hx-trigger="X from:body"` is already the house pattern for cross-panel refresh.
Nothing in the codebase uses Alpine `@event.window`-style bindings for these; every listener is
registered with `addEventListener` inside an `Alpine.data` component's `init()`, matching what
spec 3's idea already commits to ("Behaviour lives in `Alpine.data` components driven by htmx
events. No `hx-on`, no trigger filters").

## 3. htmx and Alpine constraints on event names

- **`HX-Trigger` response header** ([htmx docs](https://htmx.org/headers/hx-trigger/)) takes
  either a bare event name (`HX-Trigger: myEvent`) or a JSON object whose top-level keys are event
  names and whose values become `event.detail`: `HX-Trigger: {"showMessage":{"level":"info"}}`.
  Multiple keys fire multiple events from one header. The docs state no naming restriction, but
  the dispatch is a real `CustomEvent`, so case is preserved end to end.
- **`hx-trigger` attribute** ([htmx docs](https://htmx.org/attributes/hx-trigger/)) parses
  modifiers after the event name using a colon: `from:<selector>`, `delay:<time>`,
  `throttle:<time>`, `once`. An event name that itself contains a colon (e.g. a
  `namespace:verb` style) risks being misparsed as `<name> <modifier>:<value>` by the trigger
  grammar; the existing code avoids this entirely by never using colons in a custom event name.
  Dots are not reserved by htmx's own attribute-value grammar, but see below for why they still
  matter.
- **Alpine's `@`/`x-on` directive** ([Alpine docs](https://alpinejs.dev/directives/on)) reserves
  the dot for modifiers (`@click.away`, `@input.debounce.500ms`), and documents the workaround
  for a custom event whose name legitimately contains a dot: rewrite dashes and add `.dot`
  (`@custom-event.dot` to listen for `custom.event`). A domain event named with a dot
  (`cohort.changed`) would therefore need that workaround anywhere it is bound with `@`, and would
  silently fail to match if someone wrote `@cohort.changed.window` expecting Alpine to treat the
  whole thing as one event name.
- **Alpine's `x-on`/`@` also lower-cases event names**, because it is implemented through an HTML
  attribute *name*, and attribute names are case-insensitive in the DOM; Alpine's own docs give
  `.camel` as the escape hatch for a camelCase custom event bound this way. This is real for an
  `@panelChanged.window="..."` binding but **does not affect** an event name that only ever
  appears as an attribute *value* (`hx-trigger="panelChanged from:body"`) or as a JS string
  literal (`addEventListener("panelChanged", ...)`), because only attribute names are lowered by
  the browser, not values. The codebase's existing camelCase events (`panelChanged`,
  `cohortCreated`) work today precisely because every current listener is one of those two forms,
  never an `@` binding. This is a real pitfall for whoever wires the quick view's Alpine component:
  registering the listener with `document.addEventListener`/`this.$el.addEventListener` inside
  `init()` (as `listRefresh` already does) sidesteps both the dot and the case problem; writing
  `@cohortChanged.window` directly on a dialog element would not.
- **The Alpine CSP build** ([Alpine CSP docs](https://alpinejs.dev/advanced/csp), summarised via
  web search) disallows arbitrary JS expressions and method calls in attribute values — no
  `eval`-style expression evaluation at all, including expressions containing a `.` or a `()` in
  most contexts. This is the same constraint the idea already names ("No `hx-on`, no trigger
  filters, nothing that needs eval"), and it is the reason the framework's existing pattern for
  cross-component refresh is a named `Alpine.data` component with real JS in a `<script>` file,
  not inline attribute expressions. It reinforces, rather than changes, the event-naming
  conclusion above.

**Conclusion**: keep camelCase, no dots, no colons, matching the existing `panelChanged` /
`cohortCreated` style exactly. This also keeps domain UI events visually and mechanically distinct
from the webhook registry's dotted names (`course.registered`, `course.completed`,
`user.registered` in `base/webhook_event_types.py`) — different transport (DOM `CustomEvent` vs.
an outbound HTTP payload built by `fire_webhook_event`), different casing convention already in
place for each, so there is no realistic collision even though both mechanisms describe
overlapping mutations.

## 4. Granularity: per entity type versus per verb

Two shapes were weighed:

- **Per verb** (`cohortCreated`, `cohortDeactivated`, `cohortReactivated`, `cohortDeleted`,
  `membershipAdded`, `membershipRemoved`, `membershipMoved`, `registrationRegistered`,
  `registrationUnregistered`, ...): precise, self-documenting, but specs 6-9 between them have
  north of twenty verbs, and every table/panel/quick view that cares about "something about this
  cohort changed" has to enumerate all the verbs that could affect it, drifting out of sync as
  specs 7-9 add more.
- **Per entity type** (`cohortChanged`, `learnerChanged`, `registrationChanged`,
  `educatorChanged`), with the affected id(s) in the detail: a table registers once for the one
  name that matches what it lists and refetches wholesale on any mutation of that type, exactly
  the way `listRefresh` already refetches wholesale on any of its registered names today. A quick
  view registers once per entity type it can display and additionally checks the id(s) in the
  detail against the entity it currently shows, so a mutation on a different row never marks it
  stale — this is the mechanism the idea already asks for ("Domain events from mutations mark the
  content stale and refetch if the drawer is open").

Per entity type is the smaller, more stable surface and matches the granularity the framework
already chose for `panelChanged` (page-scoped, not verb-scoped). The remaining design question is
only how to carry an id when one mutation touches two entities of different types (membership,
course registration): the recommendation below fires one JSON object with one key per affected
entity type, each carrying that type's own id(s), rather than inventing a fifth "membership" or
"registration-of-a-cohort" event name.

## 5. Recommendation

Four event names, reused verbatim by specs 6 to 9, replacing both the ad hoc
`get_created_event_name()` string and the un-scoped `panelChanged`:

| Event | Detail shape | Fired by |
|---|---|---|
| `cohortChanged` | `{"cohort_id": ["<uuid>", ...]}` | Spec 6: create (save-and-add-another only), edit, deactivate, reactivate, delete, course registration/unregistration. Spec 7: either side of a membership add/remove/move (source and destination cohort ids). Spec 8: bulk cohort actions. Spec 9: a cohort-scoped role grant/remove/scope change, alongside `educatorChanged`. |
| `learnerChanged` | `{"learner_id": ["<uuid>", ...]}` | Spec 7: add, deactivate, reactivate, resend setup email, either side of a membership add/remove/move, individual course registration/unregistration. Spec 8: bulk learner actions and CSV import commit. |
| `registrationChanged` | `{"course_id": "<uuid>", "learner_id": ["<uuid>", ...] or null, "cohort_id": ["<uuid>", ...] or null}` | Spec 6: cohort course registration/unregistration (`cohort_id` set, `learner_id` null), fired alongside `cohortChanged`. Spec 7: individual course registration/unregistration (`learner_id` set, `cohort_id` null), fired alongside `learnerChanged`. Spec 8: bulk register/unregister. |
| `educatorChanged` | `{"organisation_id": "<uuid>"}` | Spec 9: role grant, removal, scope change. Always fired; `cohortChanged` fires alongside it only when the grant is cohort-scoped (`instructor`, `ta`). |

The id fields are always an array, even for a single id, so a `CohortMembership` move (which
touches two cohorts) needs no special case: `{"cohortChanged": {"cohort_id": ["<source>",
"<dest>"]}}`. A mutation that spans two entity types fires both keys in one `HX-Trigger` JSON
object, one HTTP response, one header — e.g. registering a cohort for a course returns
`HX-Trigger: {"cohortChanged": {"cohort_id": ["<cohort>"]}, "registrationChanged":
{"course_id": "<course>", "cohort_id": ["<cohort>"], "learner_id": null}}`.

Who listens to what:

- **Tables** (cohorts, learners, educators, a cohort's course-registration or learner-membership
  sub-tables) register for the one event name matching their row type via the existing
  `data-refresh-events` / `listRefresh` mechanism, and ignore the detail, exactly as today —
  wholesale refetch on any matching event, no id comparison needed.
- **Panels on an instance's own detail page** (cohort overview/settings, learner overview) switch
  their `hx-trigger` from the generic `panelChanged from:body` to the entity-specific event,
  e.g. `hx-trigger="cohortChanged from:body"` on every panel of the cohort detail page,
  `learnerChanged from:body` on the learner detail page. A page is already scoped to one instance,
  so, as today, it does not need to compare ids; an edit to a different cohort firing the same
  event name while this page happens to be open is a harmless extra refetch, matching the current
  `panelChanged` behaviour.
- **The quick view** registers for whichever entity events match what it can display
  (`cohortChanged`, `learnerChanged`) and, uniquely among consumers, reads the detail: it marks
  itself stale and refetches only when its currently-shown entity's id is in the event's id array;
  otherwise it does nothing, per the idea's "content is stale and refetches if the drawer is open"
  and "marks the quick view stale only when its entity is affected". A cohort quick view also
  listens for `registrationChanged` where `cohort_id` includes its own id, and a learner quick
  view for `registrationChanged` where `learner_id` includes its own id, since both surfaces show
  a course list.
- **`educatorChanged`** has one listener today (the educators table); no quick view is planned for
  an educator, so it never needs id comparison.

This keeps the set at four, all camelCase and dot/colon-free like the existing `panelChanged` /
`cohortCreated`, deliberately distinct in style from the dotted webhook registry names so the two
mechanisms are never mistaken for one another, and gives specs 6 to 9 one fixed vocabulary instead
of each inventing its own `get_created_event_name()` string per action.

---
status: ok
