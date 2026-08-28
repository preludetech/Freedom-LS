# Better course progress tracking

> **Revised after the `learner-terminology-rename`, `basic_reports`, `fls-integration-system-checks`
> and `learners-associated-with-organisations` merges.** The last revision was written for the
> Organisations merge and is now stale twice over: the three apps this feature works in were
> renamed, and enrolment was re-keyed onto a new `Learner` model. Every earlier `path:line` is dead.
> A full spec was written on this branch and then deleted. Five decisions it reached are folded into
> this document as its own positions — they are marked **[from the spec phase]**, and the argument
> behind each is recoverable with `git show 70b4cc36:"spec_dd/2. in
> progress/better_course_progress_tracking/1. spec.md"`. See `## Research` for which research files
> are current.

## Problem

Progress is keyed on `(user, content)`, not on a learner's *pass through a course*:

- `TopicProgress` — `unique_together = ["user", "topic"]` (`learner_progress/models.py:521`)
- `CourseProgress` — `unique_together = ["user", "course"]` (`learner_progress/models.py:568`)
- `FormProgress` — no uniqueness constraint at all; many rows per `(user, form)`, one per attempt.
  It is the one model that already has attempt semantics.

Neither of the two constraints includes `site`, so that uniqueness is global across every Site, not
per-tenant. And none of the three carries any organisation dimension. Five consequences fall out.

**1. Enrolment moved to `Learner`; progress did not.** `learners-associated-with-organisations`
introduced `Learner` (`learner_management/models.py:51-80`) — one row per `(user, organisation)`,
unique on that pair (`:73-77`) — and hung every enrolment record off it: `LearnerCourseRegistration`
keyed `(site_id, learner, collection)` (`:120-126`), `CohortMembership` keyed `(learner, cohort)`
(`:88-93`), and the deadline models. `LearnerCourseRegistration` dropped its `organisation` column
entirely; organisation now comes from `learner.organisation`. Progress stayed on the bare `User`.
The seam is visible in the code: the educator progress matrix reaches progress through
`OuterRef("learner__user")` (`educator_interface/views.py:360-366`).

**2. Organisations promised independence that progress cannot deliver.** The shipped spec explicitly
blesses one person holding two registrations for one course, one per organisation — "The unique
constraint is `(site_id, learner, collection)`, so that is legal" (`spec_dd/3.
done/2026-08-23_17:20_learners-associated-with-organisations/1. spec.md:554-558`). Those two
registrations share one `CourseProgress` row: one percentage, one completion time, one resume
pointer. A learner who finishes for Client A is instantly complete for Client B, and Client B's
educator — inside an organisation-scoped interface — sees a percentage earned somewhere else.
`docs/product/learner-tracking.md:23` already says this out loud in product language: "None of this
is scoped by organisation." This is live in `main` today.

**3. A learner can only ever do a course once.** Within one organisation the effective key is
unchanged, and the two constraints above mean there is nowhere to put a second pass. Renewals,
recertification and cohort re-runs after a fail remain unrepresentable.

**4. Sharing content between courses corrupts progress in both.** Nothing in `ContentCollectionItem`
(`content_engine/models.py:381`) stops the same `Topic` or `Form` being linked into two courses —
possible today, just not yet exercised. Because `TopicProgress` has no course dimension and
completion is computed from a **global per-user** set of completed ids
(`learner_progress/signals.py:80-86`), completing a topic in a "revision" course would silently tick
it in the full course. The planned modular-courses work walks straight into this.

**5. Rows are minted for courses nobody registered for, with no `site`.**
`update_course_progress_on_completion` (`learner_progress/signals.py:35-97`) will happily
`update_or_create` a `CourseProgress` (`:92-96`) passing no `site=`, as will `view_course_item`
(`learner_interface/views.py:666-670`). That is why eight `qa_helpers` commands pass `site=` by
hand, and it makes the model's own docstring — "These are only created when a user EXPLICITY chooses
to register" (`learner_progress/models.py:527-534`) — false today. Whatever creates a pass must
decide this deliberately; fold the docstring correction in.

## Goal

Give a learner's pass through a course a first-class identity that owns their item progress, so a
course can be taken more than once, shared content stays independent per course, and two
organisations running the same course for the same person stay independent of each other.

## Shape

`CourseProgress` **keeps its name** and becomes the record of *one learner's pass through one
course*. What changes is what a row means.

> **On the word "pass".** FLS already has a noun for a `CourseProgress` row — **course progress
> record**, from `verbose_name_plural = "Course progress records"`. This document keeps that as the
> formal term and uses **pass** as coined shorthand for the same thing: one learner's single journey
> through one course, in one organisation, from start to completion or abandonment. It is new here,
> it means nothing else in the codebase, and a spec may drop it entirely in favour of the full
> phrase. Nothing else in this document is a coinage.

```
CourseProgress
    learner              -> FK Learner        (replaces user; organisation comes with it)
    course
    is_active
    learner_registration -> FK, nullable  \  exactly one is set;
    cohort_registration  -> FK, nullable  /  both SET_NULL
    start / last_accessed / completed times, progress_percentage
    resume pointer       -> collection-item FKs, not a GenericForeignKey

    UNIQUE (learner, course) WHERE is_active

TopicProgress / FormProgress
    -> non-null FK to the CourseProgress row that owns them
    -> scoped to the ContentCollectionItem that places the content, not to the bare Topic / Form
```

### Why key on `Learner`

`Learner` *is* "this person, in this organisation". Keying on it rather than on `(user,
organisation)` is not a shortcut — it is using the model the codebase already has.

- **The stored-organisation argument evaporates.** The previous revision argued organisation had to
  be a column on the table because a partial unique index cannot span a foreign-key hop.
  `learner_id` is on the table, so `UNIQUE (learner, course) WHERE is_active` is enforceable with no
  organisation column at all.
- **No new cross-app dependency.** `docs/app_structure.md:88` already has `learner_progress -->
  learner_management`; there is no `learner_progress --> organisations` edge. Keying on `Learner`
  reaches `Organisation` transitively, through the app that already owns that edge. An
  `organisation` FK on `CourseProgress` would add one.
- **It matches the registration grain exactly**, so "which registration, which pass" is a join
  rather than a reconstruction.
- **It has external precedent.** SCORM is the one surveyed system that names a first-class object
  distinct from the learner — the *registration* — precisely so a pass can be counted and re-counted
  without touching learner identity. Most commercial products (Docebo branches, Absorb departments)
  dodge the question by forbidding one person from belonging to two groupings at all, a path FLS
  already rejected when it shipped `Learner`. See `research_multi_org_progress_grain.md`.
- **Cost, stated plainly:** every read path moves from `user=` to `learner__user=`. The educator
  matrix already does that hop.

The partial-unique shape is not novel here: `organisations/models.py:41-57` already ships
`one_default_organisation_per_site`, a `UniqueConstraint` with a `condition`, for exactly the "only
one row may carry this flag" problem `is_active` has.

### Decisions carried over from the spec phase

**A pass's life follows the registration that granted it.** **[from the spec phase]** The record
carries `learner_registration` and `cohort_registration`, exactly one set, both `SET_NULL`. Resolve
which registration the learner currently holds; same registration, same pass; different registration
or NULL, retire the old one (`is_active=False`) and start a fresh one. There is no list of events
that count as "new" — the comparison is the whole test.

This reverses the previous revision, which rejected those FKs. That rejection was about *provenance*
— a mutable access grant is a poor durable record of how access was earned — and it still stands.
The FKs are not used that way. Their job is **identity**, and they are also what makes retirement
cheap: "which passes did this registration grant" is `registration.course_progress_records`, not a
query reconstructing the answer from learner, course and organisation.

It also keeps the deliberateness the earlier revision wanted without building anything. There is no
unregister flow in FLS and no re-register flow, so "a deliberate re-registration action" described
something that does not exist. Registrations only change by a human act, and a pass inherits that.

> **Caveat the spec must confront, not inherit.** A cohort move is a human click that produces *two
> automatic writes* — delete the old `CohortMembership`, create the new one — so it is the
> comparison logic, not the click, that decides whether the learner keeps their work. Every
> comparable system with an analogue (Moodle cohort sync most directly, Canvas SIS-driven section
> changes) treats membership churn as a *dangerous* proxy for "this learner wants a fresh start",
> and Canvas's SIS batch-mode incidents show what happens once a sync glitch can mean "retire this
> record". `research_enrolment_bound_progress_lifecycle.md` favours fixing this with an explicit
> transfer step inside the future move action rather than by weakening the resolution rule. The spec
> must at minimum say whether that transfer is compatible with the retirement design as written,
> because `learner-management-actions` cannot be specced until it knows.

**A new pass hard-resets item completion.** **[from the spec phase]** No partial credit across
passes. Every product surveyed defaults this way, and every system that offers a real fresh start —
SCORM's new registration, Absorb re-enrolment, Totara recertification, Moodle `local_recompletion` —
makes the reset an explicit, named operation rather than an implicit side effect. "Keep the best
score" legitimately exists only across attempts *within* one pass, which `FormProgress` already
supports.

**No migration backfill.** **[from the spec phase]** Delete every existing progress row and add the
new columns non-nullable. Re-keying `TopicProgress` from `(user, topic)` is ambiguous by nature —
the row never captured which course it belonged to — and would need a tie-break, a quarantine and a
retention story. None of that is needed: the only progress data that exists is development data.
`final_pre_deploy_db_structure_cleanup` is built on the same precondition and sequences itself
*after* this work, so the intermediate migration written here is folded away by its later reset.

**The resume pointer stops being a `GenericForeignKey`.** **[from the spec phase]**
`get_resume_index` (`learner_interface/utils.py:268-288`) matches the pointer against the course's
children by `(type, pk)`. That stops identifying a position the moment a `Topic` can be placed
twice, so the learner would resume at whichever collection item came first.

**No rename, and the flag is `is_active`.** **[from the spec phase]** Renaming the model buys a word
and costs a hand-authored migration plus churn across every import, admin class, factory and test
that names `CourseProgress`. `is_active` is the flag name `Learner`, `LearnerCourseRegistration` and
`CohortCourseRegistration` already use. That does mean four models now carry `is_active`, so any
sentence naming two of them must name the model.

## Item progress is scoped to the collection item

`TopicProgress` and `FormProgress` are scoped to the `ContentCollectionItem` that links the content
into a course or part (`content_engine/models.py:381`) — not to the bare `Topic`/`Form`:

```
TopicProgress:  one row per (course progress record, collection item)
FormProgress:   many rows per (course progress record, collection item), one per attempt
```

This is the definition-versus-usage split every comparable system draws: Open edX keys
`StudentModule` on `(student, module_state_key, course_id)`, SCORM scopes to a registration, LTI to
a `resource_link_id`. Progress attaches to where content is *used*, never to the shared content
object.

Scoping to the pass alone would already give per-course and per-organisation independence. Going to
the collection item additionally handles the same topic appearing twice in one course, and pays for
part of its own cost: `update_course_progress_on_completion` currently traces *upward* from a
content item to find every course containing it, which is most of why it carries a `@claude`
refactor TODO (`learner_progress/signals.py:43`). A row that already knows its collection item and
its pass knows its course directly, and that traversal disappears.

The cost is real and should not be hand-waved at spec time: the `children()` accessors must expose
collection-item identity, every "has this learner completed this topic" check must decide whether it
means this collection item or the topic wherever it appears, and deleting a collection item needs an
explicit policy. Removing one must **not** cascade-delete the completion record.

Note that this is a different axis from what happens when the `Topic`, `Form` or `Course` row itself
is hard-deleted. `final_pre_deploy_db_structure_cleanup`'s deletion-semantics research recommends
`PROTECT` there. Both belong in the final schema and neither should be merged into the other's
reasoning.

## Explicitly not in scope

Each of these is deferred to a named successor rather than refused outright.

- **No attempt-history UI.** Prior passes are queryable but not surfaced.
- **No learner-facing organisation switch.** The learner interface has no organisation dimension in
  its URLs, so a learner holding passes in two organisations works in whichever one
  `organisation_for_learner_course()` resolves.
- **No organisation-aware course *access*.** `is_registered_for_course`
  (`learner_management/utils.py:69-101`) and every `COURSE_ACCESS_BACKEND` stay organisation-blind.
  **This asymmetry is deliberate and should be stated in the spec rather than discovered: access
  stays organisation-blind while progress becomes organisation-scoped.** A registration in any
  organisation opens the course; organisation decides which pass the work lands in, not whether the
  learner may enter.
- **No validity / expiry / recertification-window concept.** Totara-style windows are real
  complexity with a documented failure mode where an early retake is not credited. This work is the
  substrate one would sit on; adding it later is additive once multiple passes exist, and a rewrite
  if not.
- **No unregister flow, no cohort-move action, no explicit retake trigger, no progress reset.** None
  exist today. All four are claimed by `spec_dd/1. next/learner-management-actions/`, which
  sequences itself after this work.
- **No registration-level provenance.** A pass records which registration it is *currently* bound
  to, not a durable history of how access was earned. If durable provenance is ever wanted, the
  answer is a record frozen at completion time, not a live FK to something that moves.
- **No modular-courses authoring.** Only the schema that stops it being a lossy migration later.
- **No content snapshots.** Decided, not deferred by omission: a pass does **not** pin a content
  snapshot in this cut. `content_snapshots` is in flight beside this work and still names no
  consumer; a pass remains the obvious first one, and the direction is fixed if it is ever built —
  progress may depend on `content_snapshots`, never the reverse. "What did this learner actually
  see" stays unanswerable until then, and that is accepted.
- **No `Learner` deletion.** Deactivation is the only removal (see the decisions below). Nothing
  here adds a delete path, and the spec should not invent one.

## Decisions taken

These were the open questions. Each is now settled; the spec inherits the answer rather than
re-opening it.

**A deactivated `Learner` keeps every pass exactly as it stands.** Deactivating a `Learner` does not
touch their stored work: registrations, memberships and progress rows are all left alone, passes
stay `is_active`, and the educator matrix keeps showing removed learners with their history intact.
`Learner` deletion is not allowed for now, so there is no second case to design for. The only thing
`learner.is_active = False` means is that the person no longer participates through that
organisation — it is not a retirement signal for their passes, and the pass-resolution rule must not
read it as one.

**Deadlines become `Learner`-scoped too, in this work.** This reverses the shipped position. The
`learners-associated-with-organisations` spec kept `learner_management/deadline_utils.py` keyed on
`learner__user` on purpose, so a person holding two `Learner` rows saw one merged deadline list.
Progress is moving to the `Learner` grain and deadlines follow it, so the two share one grain rather
than sitting at odds. Concretely, the seven `learner__user=` filters in `deadline_utils.py` (`:65`,
`:81`, `:109`, `:136`, `:216`, `:228`, `:247`) resolve against a single `Learner`. This is a
behaviour change to shipped code outside the progress models and needs its own tests: a person in
two organisations must see each organisation's deadlines separately, not a union.

**A learner reaches only one organisation's pass through the UI, and that is intended.**
`organisation_for_learner_course()` (`learner_management/queries.py:89-115`) returns exactly one
answer — cohort registration wins, otherwise `latest_registration()`'s `(-is_active,
-registered_at)` tiebreak (`learner_management/queries.py:70-86`). Both passes exist in the
database; only the resolved one accumulates work. Holding an *active* registration for the same
course in two organisations at once is an unlikely enough scenario today that nothing is built for
it. The schema keeps it representable — two `Learner` rows, two passes — so if it ever becomes real
the answer is to route work to both registrations, not to re-key anything. State this in the spec
rather than leaving it emergent from a tiebreak.

**Both webhooks gain pass and organisation identity.** Today `(user, course)` is unique, so
`course.registered` (`learner_management/models.py:128-159`) and `course.completed`
(`learner_interface/views.py:1269-1280`) are unambiguous while carrying only `user_id` /
`user_email` / `course_id` / `course_title` and a timestamp. After this change one person can hold
two passes for one course — a retake, or one per organisation — and those payloads no longer say
which one. Both send sites already hold the answer: the registration knows its `Learner`, and
`course_finish` is holding the `CourseProgress` when it fires. So both payloads gain
`organisation_id` and the course-progress (pass) id. The additions are purely additive; no existing
field changes name or meaning. `xapi_implementation` is out of scope and none of this is shaped for
it.

One ordering constraint the spec must settle rather than assume: `course.registered` fires from
`LearnerCourseRegistration.save()`, so whether it can name a pass depends on when a pass is minted.
If passes are created lazily on first content access, no pass exists yet at that moment and the
payload can only carry the organisation. The cleanest resolution is to create the pass as part of
registration — which is also what makes the model's own docstring true again (consequence 5) — but
that is a decision about pass creation, not about webhooks, and it belongs with the rest of the
lifecycle rule.

**`CourseProgress.id` is the durable handle.** It names one learner's pass through one course in one
organisation, it is never reused, and downstream work may bind to it — a retired pass keeps its id.
Nothing in this cut consumes that: `certificates` and `xapi_implementation` are both out of scope,
and this work adds no `PROTECT` relationship for them. Stating the guarantee here is what stops each
of them re-deriving it.

**`RecommendedCourse` stays `User`-keyed** (`learner_management/models.py:352-378`). It is a
recommendation, not an enrolment, and this matches the shipped Organisations spec's own non-goal.
Nothing about it changes.

## Known landmines

Verified against the current tree in `research_fls_impact_surface_current.md`, which ranks them.

**These crash.**
- `course_finish` (`learner_interface/views.py:1256-1258`) — `get_object_or_404(CourseProgress,
  user=, course=)`. A hard 500 on course completion for exactly the learners this feature serves.
- `view_course_item`'s `CourseProgress.objects.get_or_create(user=, course=)` (`:666-670`) and the
  `TopicProgress.objects.get_or_create(user=, topic=)` at `:797-799` — both on ordinary player
  navigation.
- Tests doing a bare `.get(user=, course=)`, e.g.
  `learner_interface/tests/test_resume_and_redirect.py:205,320`.
- `learner_progress/admin.py` — `list_display` built on `"user"`, which becomes a `FieldError` under
  a `user` → `learner` FK change.

**These are silently wrong, which is worse.** They produce plausible percentages with nothing to
grep for, and need tests asserting *which* pass's data appears, not just that the page renders.
- The educator matrix `Subquery(...)[:1]` (`educator_interface/views.py:360-366`) — picks an
  arbitrary row **and applies no organisation filter**, while the data tables beside it in the same
  organisation-scoped interface *do* (`:151-176`, `:1013-1026`). An educator already sees a roster
  scoped to their organisation and a percentage that is not. Closing that is part of this work.
- `.first()` on assumed singletons in `_detail_cta_label` (`learner_interface/views.py:130-136`,
  which drives the Start / Continue / Review CTA), `_player_chrome_context` (`:730-751`) and
  `get_resume_index` (`learner_interface/utils.py:268-288`).
- Dict collapses keyed on course id in `get_current_courses` (`learner_interface/utils.py:700-728`)
  and `get_course_listing` (`learner_interface/utils.py:834-839`), plus `get_completed_courses`
  (`learner_interface/utils.py:683-697`), which builds a set of completed course ids and so marks a
  course complete regardless of which pass completed it.
- Item-id-keyed maps in `_fetch_player_progress_maps` (`learner_interface/utils.py:310-346`) and the
  educator matrix's sibling.
- `update_course_progress_on_completion` (`learner_progress/signals.py:35-97`) — global per-user
  completed-id sets with no course or pass scoping, and no `site=`. Several of the above trace back
  to it.

**The `reports` app is exposed in a way both this idea and the deleted spec previously described
wrongly.** Reports never read `CourseProgress` — `reports/gather.py:218` carries an explicit
prohibition, and the whole app recomputes from `TopicProgress`/`FormProgress`. So the failure mode
is not "reports on an arbitrary pass"; it is quieter: **every pass merges into one.** Completions
are unioned across passes (`reports/indexes.py:272-278`), attempt numbering renumbers a new pass's
first sitting as N+1, the cohort confusion analysis takes each learner's first attempt *ever* rather
than this pass's (`reports/indexes.py:391-398`), and `has_any_progress` stays true after a reset so
`NoRecordedActivityRule` (`reports/at_risk.py:56-64`) never fires for a learner starting again. The
app's "first attempt" and "latest attempt" conventions must be re-scoped to "within one pass",
explicitly, rather than left to surface as a report bug.

**Also.**
- `deadline_utils.py`'s seven `learner__user=` filters, per the decision above. They are correct
  today and become wrong only because the grain moves under them, so there is nothing to grep for
  afterwards either — the tests are the only thing that will catch a missed one.
- The two webhook payloads, per the decision above. `course.registered` fires from
  `LearnerCourseRegistration.save()`, which uses `Learner._base_manager` deliberately because there
  may be no ambient site; the organisation lookup it gains must respect that same constraint.
- `FormProgress.get_or_create_incomplete` / `get_latest_incomplete` / `finalise_stale_incomplete`
  are used across six call sites in `learner_interface/views.py`. Scoping some but not all lets an
  attempt started under one pass be resumed or finalised under another.
- `CourseProgressFactory` / `TopicProgressFactory` (`learner_progress/factories.py:21-48`) have no
  `django_get_or_create`, so roughly forty test call sites carry an implicit singleton assumption.
- `recalculate_progress_percentages` needs its completed-id sets rescoped from global-per-user.
- Test coverage for "two passes, same course, same learner" is entirely net-new — the current
  constraints make such a test impossible to write. It has two shapes worth covering: two passes in
  one organisation (a retake) and one pass each in two organisations.
- The two `@claude` TODOs (`learner_progress/models.py:59` and `learner_progress/signals.py:43`) are
  entangled with this change. Fold them in rather than touching that code twice. Do not delete them
  either way.

**New behaviour since the last revision, which the spec must not undo.** Completion is now
pass-aware: a failed quiz no longer completes an item (`learner_progress/queries.py`,
`attempt_completes_form` / `completed_form_ids_by_user`), and `course_finish` will not stamp
`completed_time` while any quiz is unpassed.

## Sequencing

This sits directly on top of Organisations and `Learner` — the pass's `Learner` FK, the
`organisation_for_learner_course()` resolver and the collapsed registration key all come from them.

`basic_reports` has **shipped**, so the earlier "land before it" warning is obsolete; the exposure
it described is real but at the item grain, not the course grain. Still downstream and still waiting
on decisions made here: `certificates` and `report-upgrades` and `xapi_implementation` (`spec_dd/1.
next/`), each needing a stable "which pass" identifier, and `learner-management-actions`, which
sequences itself explicitly after this work and already has opinions about the retirement rule.
`content_snapshots` and `final_pre_deploy_db_structure_cleanup` are in flight beside it; the latter
deliberately runs last and tells its own author not to touch the models this feature is mid-redesign
on.

Any system check this work adds follows the house conventions from `fls-integration-system-checks`:
`freedom_ls_learner_progress.E00N`/`.W00N`, one condition per id, registered from
`AppConfig.ready()`, no database access, retired ids never reused. A data-integrity assertion about
progress rows is therefore a management command or a test, never a check. And
`freedom_ls/contrib/conformance/test_migrations.py:19-26` asserts there are no pending migrations,
so the model change ships with its migration in the same PR.

## Research

**Current.** These four were written against the tree as it stands and supersede the six below where
they disagree.

- `research_multi_org_progress_grain.md` — how comparable systems key progress when one person
  studies through several organisations, tenants or departments
- `research_enrolment_bound_progress_lifecycle.md` — stress-testing "a pass lives and dies with its
  registration", and the cohort-move and bulk-sync failure modes
- `research_fls_impact_surface_current.md` — the full blast radius, verified, ranked by risk
- `research_downstream_feature_pressure.md` — what the queued and in-progress roadmap demands of
  this model

**Superseded, kept as a record of research actually done.** The six below pre-date the Organisations
merge, the learner rename and the `Learner` model. They cite constraints and `path:line` references
that no longer exist, and have no concept of an organisation. Where they and this document disagree,
this document is current.

- `research_lms_enrolment_models.md` — Moodle / Canvas / Open edX / Totara / SCORM / LTI
- `research_recertification_and_retakes.md` — renewal, retakes, completion history, certificate
  binding
- `research_cohort_group_enrolment.md` — materialise versus derive group access
- `research_shared_content_across_courses.md` — definition versus usage, modular courses
- `research_django_modelling_and_migration.md` — constraints, FK shapes, migration mechanics
- `research_fls_impact_surface.md` — the pre-rename blast radius
