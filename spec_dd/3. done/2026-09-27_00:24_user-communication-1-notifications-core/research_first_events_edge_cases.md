# Research: first-events edge cases (course registration, course completion)

Scope: precisely which code paths create a `LearnerCourseRegistration` and whether each would
raise a notification if the hook sits where `course.registered` fires today; the idempotency of
`course_finish`'s completion branch; whether either path runs outside a request; whether educators
ever see these two events; and the UX question of notifying a learner who is already looking at
the completion page. Builds on `spec_dd/1. next/user-communication/research_notification_sources_and_delivery.md`
(the event-hook and delivery-stack survey) — that file is not repeated here.

## 1. Every code path that creates a `LearnerCourseRegistration`

The model (`freedom_ls/learner_management/models.py:109-130`) is a `SiteAwareModel` with
`is_active` (default `True`), `registered_at` (`auto_now_add`), and a
`UniqueConstraint(fields=["site", "learner", "course"], name="unique_learner_course_registration")`
(`:121-127`). There is **one row per (site, learner, course) ever** — there is no way to get a
second row for the same pair; "re-registering" is always an update of the existing row, never a
new insert. That fact drives everything below.

The only receiver that mints a `CourseProgress` record and fires `course.registered` is
`ensure_course_progress_on_learner_registration`, a `post_save` receiver on
`LearnerCourseRegistration` itself (`freedom_ls/learner_progress/signals.py:180-198`), deferred via
`transaction.on_commit`. It:
- returns on `raw=True` (a fixture `loaddata`, `:189-191`),
- returns if the saved instance is not currently active (`:193-197`) — a deactivating save fires
  nothing, and creating an already-inactive row (e.g. an import of a past, withdrawn enrolment)
  announces nothing either,
- otherwise calls `_ensure_and_announce(instance, announce=created)` (`:198`), which always mints
  the `CourseProgress` record but only calls `fire_webhook_event("course.registered", ...)`
  when `announce` is `True`, i.e. when this `post_save` had `created=True` (`:122-154`).

So **the existing hook is already a model `post_save` signal, not code inlined in one view** — the
question "would a model signal (post_save, created) be better or worse than sitting the call
inline where the view fires the webhook" is really "should the notification join `_ensure_and_announce`
at the same signal, or attach its own receiver" — either way it rides `post_save` +
`created=True` + `is_active=True`, and every current call site below goes through this same
receiver because none of them bypass `.save()`.

| # | Call site | Mechanism | `created` when first registering | Fires today (`course.registered`) | Would fire an in-app notification if the hook sits at the same place |
|---|---|---|---|---|---|
| 1 | Learner self-registration, `freedom_ls/learner_interface/views.py:897-901` (the free-course "register" view) | `LearnerCourseRegistration.objects.update_or_create(learner=..., course=..., defaults={"is_active": True})` | `True` on first registration | Yes | Yes — this is the canonical path the idea.md's "the point where `course.registered` fires today" means |
| 2 | Same view, **re-registration after an admin had deactivated it** | Same `update_or_create` | `False` — the row already exists, only `is_active` flips back to `True` | No (`announce=created=False`) | No, by the same existing logic — see §1a |
| 3 | Django admin add, `LearnerCourseRegistrationAdmin` (`freedom_ls/learner_management/admin.py:368-395`, form `LearnerCourseRegistrationAdminForm`, `freedom_ls/learner_management/forms.py:47-57`) | Plain `ModelForm.save()` → `instance.save()`, `is_active` defaults `True` | `True` for a new row | Yes | Yes — an admin adding a registration for a learner fires exactly the same signal as the learner registering themself |
| 4 | Django admin edit, flipping `is_active` False→True on an existing row | `ModelForm.save()` on an existing instance | `False` | No | No |
| 5 | `qa_helpers` management commands — e.g. `_register()` in `qa_create_dashboard_paging_fixtures.py:354-366` (`get_or_create` then conditionally `.save(update_fields=["is_active"])`), `qa_create_application_docs_scenario.py:263`, and others found via the factory | `get_or_create(..., site=site, defaults={"is_active": True})` — note `site` passed explicitly, because these run as management commands with no ambient request | `True` on first run for a given fixture | No (see §3 — `fire_webhook_event` silently no-ops with no request) | **Yes, if the notification call does not copy `fire_webhook_event`'s "no request → no-op" behaviour** — the signal fires (`post_save`, `created=True`) regardless of request context; only the webhook's own site-lookup silently swallows it today |
| 6 | Factories in tests, `LearnerCourseRegistrationFactory` (`freedom_ls/learner_management/factories.py:91-95`) | `factory.django.DjangoModelFactory` → `.create()` → `.save()` | `True` | No (test settings/no request) | Signal still fires in-process the same way; a test asserting on notification counts must account for this the way `test_registration_webhook_events.py` already does for the webhook |
| 7 | Data migrations | None exist — `freedom_ls/learner_management/migrations/0001_initial.py` is schema-only (confirmed by grep; no other migration in the app touches this model) | n/a | n/a | If one is ever added with `apps.get_model(...)` (a *historical* model class), it would **not** fire — Django's `post_save` dispatch matches on the exact sender class, and a historical model is a distinct class object from `freedom_ls.learner_management.models.LearnerCourseRegistration`. This is a pre-existing gap shared by the webhook and would be shared by a notification with no extra work needed to preserve it, but no extra work to fix it either |
| 8 | `course_applications` approval | **Does not exist yet.** `course_applications/models.py` has no `LearnerCourseRegistration` reference outside its own tests/factories; the docstring NOTE at `course_applications/models.py:24-29` confirms `CourseApplication` has no state field and no approve/reject transition today. "Approved → registered" is blocked on the application-review-ui effort landing a state machine, exactly as the sources-and-delivery research already found for the webhook side | — | — | — |
| 9 | `course_access` backends | Grep of `freedom_ls/course_access/*.py` (excluding tests) finds **no** `LearnerCourseRegistration.objects.create/get_or_create/update_or_create` call. Backends (`course_access/loader.py`, `backends.py`) decide *access*, they do not mint registrations | — | — | — |
| 10 | Educator-interface individual registration (future) | **Not built yet.** Today's `educator_interface/views.py` only reads `LearnerCourseRegistration` (`select_related` at `:1083`) for display; there is no create path. `educator-interface-7-learner-administration/idea.md` scopes "individual course registration and unregistration" as new work | — | — | Whatever spec 7 builds will go through `.save()`/`.create()` on the same model, so it will land on the same `post_save` receiver automatically — **this is the strongest argument for keeping the hook on the model signal rather than duplicating a notification call into each view**: a future creation path needs no separate wiring |
| 11 | CSV/bulk import | **Not built yet** — no `csv`/bulk-import code exists anywhere in `learner_management` today (grep found nothing); scoped to `educator-interface-8-bulk-operations` | — | — | Same as #10: automatically covered once it lands, if the hook stays on the signal |

### 1a. Should a learner be notified when an educator (or admin) registered them?

Mechanically, **yes, the same as self-registration** — row #3 above fires the identical
`post_save(created=True)` signal, because Django's admin add view is an ordinary `ModelForm.save()`
on a new instance; there is nothing in the signal receiver that distinguishes "who saved this" from
"a learner saved their own". The same will be true of the educator-interface's future add-registration
action (row #10), since nothing in the model or its `Meta` records who created a row (no
`created_by` field).

This is a genuine UX question the spec should settle explicitly, not a fact that resolves itself:
- **For:** the learner did not know they were registered until told; "you're registered" is exactly
  as true and exactly as useful regardless of who clicked the button. The bell exists precisely so a
  user learns about their own activity after the moment has passed (idea.md's "Why"), and an
  educator-initiated registration is activity on the learner's account just as much as a
  self-registration is.
- **Against:** if the spec's mental model is "notify me about things *I* did", an educator-initiated
  registration does not fit, and a learner newly added to a course by staff might reasonably expect a
  different message ("You've been registered for X by your organisation") rather than the
  self-registration copy ("You registered for X"). Nothing in the current code distinguishes the two
  cases to let the notification text differ even if the spec wanted it to (no actor/`created_by`
  field on `LearnerCourseRegistration` to key off of).
- **Recommendation:** treat both as the same event and same copy for this spec (simplest, matches
  "the point where `course.registered` fires today" literally, and needs no new field). If the
  product wants different wording for staff-initiated registration later, that needs a `created_by`
  or equivalent actor field first — flag it as a later refinement rather than solving it here.

### 1b. Re-registration after deactivation — is there an `is_active` flag / unique constraint?

Yes to both, and they are the mechanism that already prevents a duplicate notification: there is
exactly one `LearnerCourseRegistration` row per `(site, learner, course)`
(`unique_learner_course_registration`, `models.py:122-126`), `is_active` toggles it off and back on,
and `_, created = update_or_create(...)` (`views.py:897`) or `get_or_create(...)` (qa commands) means
reactivating an existing row is always `created=False`. Because the announce decision is
`announce=created` (`signals.py:198`), **reactivation after a deactivation never re-announces**,
by construction, with no extra guard needed. The comment at `views.py:902-903` states this is
deliberate for the webhook ("Reactivating one an admin had switched off is not a second
registration") and the same reasoning carries over cleanly to a notification.

## 2. Course completion idempotency

`course_finish` (`freedom_ls/learner_interface/views.py:1613-1659`) is a plain `@login_required`
view, hit by GET on every visit to the completion page — including a refresh, the back button, or
a bookmarked URL. The completion branch is guarded by the stamp itself:

```python
if not course_progress.completed_time and not still_to_do:
    course_progress.completed_time = timezone.now()
    course_progress.save(update_fields=["completed_time"])
    ...
    fire_webhook_event("course.completed", ...)
```

(`:1636-1653`). `completed_time` (`freedom_ls/learner_progress/models.py:141`,
`DateTimeField(blank=True, null=True)`) is set exactly once and the branch is unreachable again
once it is non-null — a second, third, Nth visit to `course_finish` for the same
`CourseProgress` row finds `completed_time` truthy and skips the whole branch, so **there is no
duplicate stamp and no duplicate webhook/notification from repeat visits today.** The comment at
`:1631-1633` states this is deliberate: "the stamp and the webhook share this branch deliberately:
an announced completion cannot be taken back, so neither may happen without the other" — a
notification call added to this same branch inherits that guarantee for free.

**Is there any other place completion is recorded?** No production code path clears or re-sets
`completed_time` back to `None` once set. The only places `completed_time = None` appears are
QA/dev-fixture management commands (`qa_create_ga_setup_seed.py:159-163,193,222`,
`qa_create_dashboard_paging_fixtures.py:414`, `qa_create_application_docs_scenario.py:290`,
`qa_reset_learner_progress.py:141`) — none of these are product features; they exist to reset QA
fixture state between demo scenarios. This matches the roadmap's stated decision that "deliberate
retakes or progress resets" are out of scope for the educator interface rebuild
(`spec_dd/1. next/roadmap.md`, educator-interface section, "Out of scope for all twelve"). So today,
in production, `completed_time` is a true one-way stamp and the idempotency above is durable, not
incidental.

**Risk to flag, not a present bug:** if a future "retake"/"reset progress" feature ever sets
`completed_time` back to `None` on a `CourseProgress` row (as the QA commands already do for test
fixtures), the next visit to `course_finish` would re-run the branch and re-fire both the webhook
and, if a notification hook is added at the same spot, a second "you completed this course"
notification. Nothing in the current design prevents that — the guard is "has `completed_time` been
set", not "has this event already been announced". A `NotificationLog`/dedupe-key approach (or
simply accepting a second notification as correct once a genuine re-completion feature exists) is a
decision for whichever spec eventually adds resets, not this one, but this spec's notification call
should not assume `completed_time` transitions are permanently one-way if it wants to be robust
against that future.

**No other model records completion independently.** `learner_progress/signals.py`'s own
`post_save` receiver on `TopicProgress` (`:67-93`) and the `form_attempt_completed` receiver
(`:96-119`) only ever *recalculate* `progress_percentage`; neither one writes `completed_time` —
that field is written solely inside `course_finish`. There is no admin action or other view that
sets it.

## 3. Is either path run outside a request, and what site do the rows belong to?

- **`course_finish`** is always a `@login_required` Django view — always inside a request. Ambient
  site (via `SiteAwareManager`/middleware) is available throughout; no explicit `site_id` is needed
  to raise this notification. If the notification call wants to be defensive anyway,
  `course_progress.site_id` is directly on the instance (`CourseProgress` is a `SiteAwareModel`,
  `freedom_ls/learner_progress/models.py:106`), so there is no need to thread anything from the
  request at all.
- **`LearnerCourseRegistration` creation** is *not* always inside a request — qa_helpers management
  commands (row 5 above) run with no ambient request, and any future data migration or a downstream
  project's own script could too. Critically, **this does not need `fire_webhook_event`'s "pull
  `site_id` from the thread-local request, or silently return" pattern at all**, because
  `LearnerCourseRegistration` is itself a `SiteAwareModel` — `registration.site_id` is set on the row
  the moment it is saved (explicitly, by the caller, in every path above: `views.py:897-901` via the
  learner's own site through `get_cached_site`/`get_default_organisation`; qa commands via an
  explicit `site=site` kwarg; the admin form via the ambient request). The existing signal receiver
  already reads through to `learner.organisation_id` for the webhook payload
  (`signals.py:151`) and could equally well read `registration.site_id` directly.
  **This is the concrete answer to idea.md's open question** ("`fire_webhook_event` silently does
  nothing outside a request, and raising a notification must not"): raising the notification from
  inside `_ensure_and_announce` (or a receiver alongside it) with `site_id=registration.site_id`
  passed explicitly, rather than resolved from `_thread_locals.request` the way the webhook call
  does, makes the notification work identically whether or not a request is present — no special-casing
  needed, and no notifications silently lost for qa_helpers-created or future management-command-created
  registrations the way the webhook already silently drops them.

## 4. Do educators ever hit these events?

The shared header bar (`partials/header_bar.html`) is used by the learner dashboard, the course
player and the educator interface alike (per idea.md), so an organisation-staff or
instructor/TA user signed in to the educator interface sees the same bell. Neither event named in
this spec is fired by anything an educator does *as* an educator:
- `course.registered` fires only for an individual `LearnerCourseRegistration`, which requires a
  `Learner` row (a user's association with an *organisation for enrolment purposes*,
  `learner_management/models.py:51-64`) — a distinct concept from any instructor/organisation-staff
  role. Nothing in the codebase ties educator roles to `Learner` rows, and nothing prevents a user
  from holding both (an instructor who is also personally enrolled in a compliance course, say), but
  that is an edge case of "an educator is, incidentally, also a learner somewhere", not "educators
  get notified about their teaching activity". Cohort-based enrolment — the bulk mechanism educators
  actually use to put learners into courses — is explicitly excluded from firing anything today
  (`learner_progress/signals.py:201-227`, confirmed already in the sources-and-delivery research,
  and reiterated in idea.md's "What is settled": "Cohort registration and cohort membership changes
  raise no notification").
- `course.completed` fires only inside `course_finish`, a learner-facing player view keyed to
  `request.user`'s own `CourseProgress` — an educator never triggers this by reviewing or managing a
  learner's progress; there is no "mark as complete" action anywhere in `educator_interface`.

**Net: for this spec's two events, an educator's bell is empty unless that same person also happens
to hold a `Learner` row and registers for / completes a course themself.** This is worth stating
plainly in the spec (as idea.md's own framing implies but does not spell out numerically) — the bell
UI is universal across the shared header, but its *content* in this first cut is 100% learner-facing;
educator-relevant events (cohort registration, deadlines, application review) are explicitly deferred
to later specs (educator-interface-7 for cohort event naming, application-review-ui for approval
events).

## 5. Does a completion notification add value given the learner is already on the completion page?

Facts, not a recommendation:
- The learner who triggers `course.completed` is, in the same request/response cycle, rendered the
  completion page directly (`views.py:1660-1670` onward) — they see "you finished this course"
  immediately, synchronously, with no polling delay.
- A notification raised in the same branch would not be *seen* until the learner next opens the bell
  or polls picks it up — by which point they already know, because they were just shown the page.
  The value of the in-app notification here is not "tell the learner something they don't know yet";
  it is a **durable record** — something to look back at later ("when did I finish this course?"),
  something the notification centre lists alongside registration and (later) messages, and the thing
  spec 2 (email) and spec 7 (digests) key off to send an email/digest entry after the fact, since
  neither of those exists yet and the in-app notification is the first artifact either could read.
  Framed that way, it is not redundant with the completion page — it is the event's permanent record,
  and the completion page is only the synchronous, one-time announcement of the same fact.
- Contrast with course registration: the self-registration view redirects straight into the course
  player (`views.py:912`, "a freshly registered learner lands on the first course item"), so there is
  no equivalent synchronous "you're registered" confirmation screen today — the notification is the
  *first* place a learner sees that fact stated back to them (beyond incidentally now being inside
  the course). That is a stronger "does this add value" case for registration than for completion.

## References

- `freedom_ls/learner_management/models.py:109-130` (`LearnerCourseRegistration`, `is_active`, the
  unique constraint), `:51-64` (`Learner` docstring)
- `freedom_ls/learner_progress/signals.py:122-227` (`_ensure_and_announce`, the three `post_save`
  receivers, the "no `post_delete` counterpart" note)
- `freedom_ls/learner_interface/views.py:850-913` (self-registration view, `update_or_create`),
  `:1613-1680` (`course_finish`)
- `freedom_ls/learner_management/admin.py:368-395`, `freedom_ls/learner_management/forms.py:47-57`
  (`LearnerCourseRegistrationAdmin`, `LearnerCourseRegistrationAdminForm`)
- `freedom_ls/learner_management/factories.py:91-95` (`LearnerCourseRegistrationFactory`)
- `freedom_ls/qa_helpers/management/commands/qa_create_dashboard_paging_fixtures.py:354-366,414`,
  `qa_create_application_docs_scenario.py:263,290`, `qa_create_ga_setup_seed.py:159-222`,
  `qa_reset_learner_progress.py:141`
- `freedom_ls/learner_management/migrations/0001_initial.py` (schema-only, no data migration touches
  this model)
- `freedom_ls/course_applications/models.py:18-83` (no state field, no registration creation)
- `freedom_ls/webhooks/events.py:10-39` (`fire_webhook_event`'s thread-local request lookup and
  silent no-op with no request)
- `freedom_ls/learner_progress/models.py:106-141` (`CourseProgress`, `completed_time`)
- `freedom_ls/educator_interface/views.py:1083` (read-only registration listing today)
- `spec_dd/1. next/educator-interface-7-learner-administration/idea.md` (future individual
  registration/unregistration UI)
- `spec_dd/1. next/roadmap.md` (educator interface "Decisions already taken" #1 on deactivate not
  delete; "Out of scope for all twelve" on resets)
- `spec_dd/1. next/user-communication/research_notification_sources_and_delivery.md` (event-hook and
  delivery-stack survey this file builds on)

status: ok
