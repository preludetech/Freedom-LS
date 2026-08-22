# Research: field-level hardening

## Executive summary

Of the seven areas in scope, only one is genuinely time-sensitive: **timestamps**. Adding
`created_at`/`updated_at` to a model that has never had them is the one change in this whole unit that
cannot be done honestly after rows exist — a backfilled `created_at` on an existing row is not a
recovered fact, it is a fabricated one (it can only ever be "whenever the migration ran" or an arbitrary
chosen default), and there is no way to later tell a genuine value from a fabricated one by looking at the
column. Do this now, on the models that have **no** timestamp of any kind today: `accounts.User` (zero
timestamps at all — not even a signup date), `student_management.Cohort` and `CohortMembership`, every
concrete `content_engine` model (11 of them — genuinely zero timestamp coverage across the app),
`organisations.Organisation`, and the three deadline models `CohortDeadline`/`StudentDeadline`/
`UserCohortDeadlineOverride`. There is no single abstract base that can absorb all of these: `SiteAwareModel`
(`freedom_ls/site_aware_models/models.py:79-84`) doesn't cover `User` (which subclasses the lower
`SiteAwareModelBase`, `accounts/models.py:67`) or `role_based_permissions.SystemRoleAssignment` (a plain
`models.Model`, `role_based_permissions/models.py:9-14`) — so the right shape is a small standalone
`TimestampedModel` mixin applied explicitly per model, not bolted onto `SiteAwareModel` itself. Renaming the
*existing*, already-populated domain timestamps (`registered_at`, `assigned_at`, `requested_at`, `timestamp`)
to a uniform name is **not** in the same bucket — a Postgres column rename is a metadata-only operation at
any table size, so that is cosmetic and safe to defer (do-later), and several of those names genuinely carry
domain meaning `created_at` doesn't (`registered_at` ≠ "row created", it is "access granted"). Everything
else in this unit is genuinely optional or genuinely already fine: `accounts.User`'s integer PK next to
everyone else's UUID PK is a defensible, not a broken, choice — FK columns auto-match their target's type so
there is no internal inconsistency, the one real cost (User's PK is exposed, sequential, and enumerable in
educator-interface URLs, `freedom_ls/panel_framework/views.py:541`, unlike every UUID-keyed object) is real
but low-severity given email is the actual login/authorization key, and converting it now would touch
FKs in 7 apps plus already-shipped webhook payload shapes (`user_id` sent as a raw int,
`freedom_ls/student_management/models.py:97`, next to `course_id` explicitly cast to `str`, line 99) for a
benefit that doesn't clear the "materially cheaper now" bar — recommend leaving it, documenting the choice.
The `role_based_permissions.ObjectRoleAssignment.object_id` `CharField(255)` vs. the `UUIDField` used by
every other GFK in the codebase is not an inconsistency to fix either: it is the *correct* choice given
`ObjectRoleAssignment` targets are open-ended (any future model, possibly non-UUID), while every other GFK
in FLS targets a closed, guaranteed-UUID set (content_engine models) — recommend documenting the rule, not
unifying the types. Constraint naming/shape issues (`unique_cohort_name_per_site` misnamed,
`CourseInterest` missing `site` where its near-twin `CourseApplication` has it, `unique_together` vs.
`UniqueConstraint`) are all real but all cosmetic-to-lightly-defensive and all cheap at any time (Postgres
constraint/index renames are metadata-only) — pick the convention now (free), defer the actual renames
(do-later). `collection` → `course` on three FK fields is real and worth doing, but by the task's own bar it
is equally cheap later (a field rename touches the same call sites regardless of when it happens) — do-later.
Index coverage: nothing found rises above "cheap later via `CREATE INDEX CONCURRENTLY`" — say so plainly
rather than manufacture urgency. JSONField usage is, on inspection, well-judged everywhere except one: `tags`
(`content_engine/models.py:67`) is used as an admin `list_filter` (`content_engine/admin.py:133` etc.) despite
being a JSON list, which doesn't filter usefully as JSON and already has a same-file precedent for the
correct type (`Course.learning_outcomes` is an `ArrayField`, `content_engine/models.py:210-217`) — worth
matching that precedent while the table is empty, though not urgent. `access_config` and `scores` — the two
cases flagged for scrutiny — both hold up as genuinely correct JSONField uses: `access_config` is explicitly
backend-owned/opaque by design (`content_engine/models.py:178-181`, enforced by a system check,
`freedom_ls/course_access/checks.py`), and `scores` is polymorphic by strategy (a flat `{score, max_score}`
for quizzes vs. a nested category tree for `CATEGORY_VALUE_SUM`, `student_progress/models.py:235-361`),
never queried at the DB level, and about to be restructured by the in-flight `better_course_progress_tracking`
spec anyway — not evaluated further here.

## 1. Timestamps

**The backfill-honesty argument, precisely.** `auto_now_add=True` records the instant a row was inserted.
Adding that field via a migration *after* rows already exist forces a choice for every pre-existing row:
either a one-off default applied at migration time (every existing row gets the *migration's* run time, not
its true creation time) or a nullable backfill with no source of truth to backfill *from* (there is nothing
elsewhere in the row that records when it first existed). Either way, the resulting column is permanently and
undetectably wrong for every row that predates the migration — there is no way to tell, from the data alone,
which `created_at` values are real and which are fabricated. This is qualitatively different from every other
finding in this unit: a missing index is merely slow, a misnamed constraint is merely confusing, a wrong field
name is merely awkward — all recoverable, lossless fixes at any time. A missing `created_at` is the one case
where waiting destroys information that cannot be reconstructed. FLS has zero production rows today
(per the idea's premise) — every `created_at` added now is accurate from the first row it ever has.

**Renaming existing, already-correct timestamps is a different, non-urgent question.** `RenameField` in
Postgres is `ALTER TABLE ... RENAME COLUMN`, a catalog-only operation that doesn't rewrite the table and costs
the same whether the table has zero rows or ten million. So standardising `registered_at` → `created_at` (or
similar) later is genuinely no more expensive after deploy than before it — that piece is do-later, not
do-now, and several of the existing names are arguably *better* than a generic `created_at` would be:
`registered_at` names a domain event (access granted), not merely "row created"; `assigned_at`
(`role_based_permissions/models.py:30,63,103`) is the same pattern for role grants; `student_progress`'s
`start_time`/`completed_time`/`last_accessed_time` name attempt-lifecycle events that a bare
`created_at`/`updated_at` pair would not replace, only duplicate.

**Where there is genuinely nothing today (do now):**

| Model | Current state | Recommendation | Judgement |
|---|---|---|---|
| `accounts.User` (`accounts/models.py:67-134`) | No timestamp field of any kind — not even a signup date | Add `created_at` (`auto_now_add`); `updated_at` optional but cheap to add alongside | **Do-now** — flagship backfill-honesty case; account age is a routine reporting/support need with no field to derive it from later |
| `student_management.Cohort` (`models.py:16-32`) | None | Add `created_at` | **Do-now** — cheap, and cohorts are long-lived administrative objects worth dating |
| `student_management.CohortMembership` (`models.py:35-48`) | None | Add `created_at` (reads as "joined cohort at") | **Do-now** — directly reportable ("when did this student join"); check for overlap with `better_course_progress_tracking`'s `CourseRun` provenance work before implementing, since that spec is mid-flight on adjacent membership/registration semantics |
| `content_engine` — `Topic`, `Activity`, `Course`, `CoursePart`, `Form`, `FormPage`, `FormContent`, `FormQuestion` (all via `BaseContent`, `models.py:55-101`) | None — 8 models with zero timestamp coverage | Add `created_at`/`updated_at` to `BaseContent` (single field addition, propagates to all 8) | **Do-now** — flagship case #2: content is loaded/re-loaded via a file-based pipeline (`content_engine/management/commands/content_save.py`, which touches nothing timestamp-related today), so "when was this last edited" is currently unanswerable and would stay unanswerable forever for anything imported before the field existed |
| `content_engine.QuestionOption`, `File`, `ContentCollectionItem` (`models.py:552-606`, `381-418`) | None — these three extend `SiteAwareModel` directly, not `BaseContent`, so a `BaseContent` fix does not cover them | Add `created_at`/`updated_at` individually | **Do-now** — same reasoning as above; call out explicitly so the `BaseContent` fix isn't assumed to be complete coverage |
| `organisations.Organisation` (`models.py:28-60`) | None | Add `created_at` | **Do-now** — cheap, small table, genuinely useful ("when was this org onboarded") |
| `student_management.CohortDeadline`, `StudentDeadline`, `UserCohortDeadlineOverride` (`models.py:135-290`) | None | Add `updated_at` at minimum (audit trail for deadline extensions — "was this deadline changed after it passed" is a real dispute-resolution question); `created_at` too, cheap alongside | **Do-now** — small, cheap, and the value (audit trail on a disputable admin action) is real, not decorative. Note: `StudentDeadline` is being renamed to `LearnerDeadline` by the in-flight `learner-terminology-rename` spec (`spec_dd/2. in progress/learner-terminology-rename/idea.md:83-91`) — land timestamps under whichever name lands first, don't block on the rename |

**Where an existing name is legitimately domain-specific (leave as-is):**

| Model.field | Why it's not `created_at` in disguise |
|---|---|
| `UserCourseRegistration.registered_at`, `CohortCourseRegistration.registered_at` (`student_management/models.py:65,121`) | Names "access granted", a real domain event distinct from generic row-creation semantics used elsewhere |
| `role_based_permissions.*.assigned_at` (`models.py:30,63,103`) | Names "role assigned"; for these models assignment and creation happen to be the same instant, but the name carries intent a generic `created_at` wouldn't |
| `accounts.LegalConsent.timestamp` (`accounts/models.py:182`) | An append-only audit record; "timestamp" reads correctly as "when this consent was recorded" in a compliance context |
| `student_progress` — `start_time`, `last_updated_time`, `completed_time`, `last_accessed_time`, `complete_time` (`student_progress/models.py:88-90,515-517,542-544`) | Attempt-lifecycle semantics a bare created/updated pair would duplicate, not replace. Not evaluated further — `better_course_progress_tracking` is actively restructuring these models into the `CourseRun` shape (`spec_dd/2. in progress/better_course_progress_tracking/idea.md:41-54`) |
| `reports.GeneratedReport.requested_at` (`reports/models.py:69`) | Borderline: row-creation *is* the request event here, so this is closer to `created_at` wearing a label than the others above. Still: a rename is a metadata-only operation at any time — **do-later**, not urgent |

**Where an app already gets it right (the convention to standardise toward, no action needed):**
`webhooks` (`created_at`/`updated_at` throughout, `webhooks/models.py:73-74,369,392,422-423`), `course_interest`
(`created_at`, `models.py:38`), `course_applications` (`created_at`+`updated_at`, `models.py:42-43`), the new
`Learner` model from the in-flight `learners-associated-with-organisations` spec (`created_at`,
`spec_dd/2. in progress/learners-associated-with-organisations/idea.md:59`). These four are the pattern: name
it `created_at`/`updated_at` unless a more specific domain name genuinely earns its keep.

**Mixin placement.** No abstract base in FLS currently carries timestamps. `SiteAwareModel`
(`site_aware_models/models.py:79-84`) is the obvious first place to look, but it would miss `accounts.User`
(subclasses the lower `SiteAwareModelBase`, `models.py:53-77`, not `SiteAwareModel`) and
`role_based_permissions.SystemRoleAssignment` (a plain `models.Model`, `role_based_permissions/models.py:9-14`,
deliberately not site-aware) — exactly the two models with the least timestamp coverage today. Recommend a
small standalone `TimestampedModel(models.Model)` abstract mixin (two fields, `abstract = True`) applied
explicitly to each model that needs it, mixed in alongside `SiteAwareModel`/`SiteAwareModelBase`/`models.Model`
as appropriate, rather than folded into `SiteAwareModel` itself. **Judgement: do-now** — this is a one-time
design decision that is free to make now and expensive to unwind once a dozen models have each grown their
own copy-pasted pair of fields.

## 2. PK types

**This is not a relational-integrity problem.** Django infers a FK column's type from its target's PK
automatically, so every FK pointing at `accounts.User` across the codebase already agrees with `User`'s
`BigAutoField` — there is no place where a UUID and an integer are forced to compare or join against each
other. Verified: at least 7 apps carry a FK to `User` — `accounts` (`LegalConsent.user`, `models.py:174-178`),
`role_based_permissions` (`SystemRoleAssignment.user`, `SiteRoleAssignment.user`,
`ObjectRoleAssignment.user`, `models.py:16-20,49-53,83-87`), `student_management`
(`CohortMembership.user`, `UserCourseRegistration.user`, `UserCohortDeadlineOverride.user`,
`RecommendedCourse.user`, `models.py:37,63,237,299-303`), `student_progress` (`FormProgress.user`,
`TopicProgress.user`, `CourseProgress.user`, `models.py:85-87,509-511,536-538`), `reports`
(`requested_by`, `models.py:56-62`), `course_interest` (`user`, `models.py:28-32`), `course_applications`
(`user`, `models.py:32-36`) — none of them are typed inconsistently with each other; the type follows `User`
automatically in every case. So "PK types disagree" is accurate as a *description* but not, by itself,
evidence of a defect.

**Where it is real: exposure and enumeration, not correctness.** `accounts.User`'s `BigAutoField` produces
small, sequential, guessable integers. Every other object in the system that appears in a URL is a UUID —
verified concretely: the educator interface builds detail-page URLs by interpolating `current_instance.pk`
directly into the path (`freedom_ls/panel_framework/views.py:538-544`), so a `Cohort`/`Course` detail URL
carries an unguessable UUID while a `User` detail URL (via `UserConfig`, `educator_interface/views.py:769-774`)
carries a small sequential integer — the one place in the whole app where an object's identity in a URL is
enumerable. The same asymmetry shows up in `UserCourseRegistration.save()`'s webhook firing
(`student_management/models.py:83-103`): `course_id` is explicitly cast with `str(self.collection_id)` (line
99) because it's a UUID that needs a JSON-safe form, while `user_id` is sent as the raw integer (line 97) —
an external webhook consumer receives a sequential, enumerable identifier for every registered user, forever,
as part of a payload contract. Because nothing has shipped yet, this webhook payload shape is itself still
cheap to change (there are no external consumers to break) — but that is a webhook-contract question, not a
database-structure one, and is out of this unit's scope; flagged here as a downstream consequence worth the
webhooks-owning spec's attention, not a recommendation of this unit's.

**Severity is low, not absent.** `email` is the actual login/authorization key
(`USERNAME_FIELD = "email"`, `accounts/models.py:77`) — knowing a user's numeric ID grants no access on its
own, and every view that exposes user data already goes through guardian's per-object permission checks
(e.g. `CohortDataTable`'s `get_objects_for_user`, per the sibling organisations research). The practical risk
is limited to "an authorised educator can infer roughly how many users exist and roughly when a given user
signed up relative to others," which is a mild information leak to an already-trusted audience, not an
account-takeover vector.

**Cost of converting now vs. later.** Converting `User` to a UUID PK now means: changing which base class it
extends (`SiteAwareModelBase` → `SiteAwareModel`, or manually adding a UUID field), a schema change touching
7 apps' FK columns (mechanically trivial on empty tables), and updating the type hints that already encode
`int` explicitly in a few places (e.g. `dict[tuple[int, UUID], TopicProgress]`,
`educator_interface/views.py:387-388,458,466-468`) — all mechanical, all doable in one pass while there is no
data. Converting it *later* means the same schema change plus reconciling every downstream integration that
has since come to depend on `user_id` being a stable integer — session/auth continuity, any external API
consumer, any webhook subscriber, any exported report keyed on it. That is a real, materially-higher cost
later — which is exactly the "do it now if you're going to do it at all" test this unit is built around. But
clearing that cost bar only matters if the change is warranted, and per the severity analysis above it is not:
**recommendation is to keep `BigAutoField` for `User`**, on the grounds that it is a defensible, common choice
(Django's own default, cheaper to index/store, no functional cost anywhere), not a broken one.
**Judgement: won't-do** (converting the type). One cheap, genuinely do-now action: `SystemRoleAssignment`
already documents its own deliberate BigAutoField choice in a code comment (`role_based_permissions/models.py:9-14`,
*"Uses BigAutoField ... because this intentionally does not extend SiteAwareModel"*) — `User` has no
equivalent comment explaining why it's the one `SiteAwareModelBase` (not `SiteAwareModel`) subclass in the
codebase. **Do-now**: add a one-line comment on `accounts.User` recording that the integer PK is deliberate,
mirroring the existing pattern, so a future contributor doesn't "fix" it by accident.

**Does the `role_based_permissions` deliberate-BigAutoField comment still hold?** Yes for
`SystemRoleAssignment` (genuinely global, no site FK, `models.py:9-43`) — nothing in this unit's findings
touches that reasoning. `SiteRoleAssignment` and `ObjectRoleAssignment` (`models.py:46-118`) *do* extend
`SiteAwareModel` and so already carry UUID PKs; the comment on `SystemRoleAssignment` only ever claimed to
explain that one model, and it still does.

**One small, unrelated, free finding surfaced while checking this:** `freedom_ls/webhooks/apps.py:6` sets
`default_auto_field = "django.db.models.BigAutoField"` on the `WebhooksConfig` `AppConfig`, but every model in
`webhooks/models.py` extends `SiteAwareModel`, which explicitly declares its own UUID `id`
(`site_aware_models/models.py:80`) — so this per-app setting is dead configuration; it has never had any
effect and reads as if webhooks models use BigAutoField when they don't. **Judgement: do-now** — deleting it
is a one-line, zero-risk clarity fix, unrelated to the `User` question but caught by the same grep.

## 3. GFK `object_id` types

Two conventions coexist, and both are correct for what they're used for — this is not the same shape of
problem as the PK question above, because here a single universal type would be a **regression**, not a
simplification.

**`UUIDField` — used everywhere the GFK's target set is closed and guaranteed-UUID.** `CohortDeadline.object_id`
(`student_management/models.py:149`), `StudentDeadline.object_id` (`:196`), `UserCohortDeadlineOverride.object_id`
(`:244`) all target `Topic | Form` only — both always `content_engine` models with UUID PKs
(`content_engine/models.py:80`, inherited via `SiteAwareModel`). `student_progress.CourseProgress.last_accessed_object_id`
(`student_progress/models.py:561`) targets the same closed set. `content_engine.ContentCollectionItem.collection_id`/
`child_id` (`content_engine/models.py:392,403`) target `Course | CoursePart` and any content-item type
respectively — again always `content_engine` models, always UUID. For all of these, `UUIDField` is strictly
better than a string column would be: native 16-byte comparison instead of string comparison, no
serialization ambiguity, and the type system documents the constraint (nothing in these models could ever
hold a non-UUID target even by mistake, since only `content_engine` models are ever linked in).

**`CharField(255)` — used exactly once, where the target set is deliberately open.**
`role_based_permissions.ObjectRoleAssignment.object_id` (`role_based_permissions/models.py:92`) is the only
GFK in the codebase whose target is not a closed set — `ObjectRoleAssignment` exists specifically to let
*any* model become an authorization target (today only `Cohort`, per `role_based_permissions/README.md:35`,
but the model imposes no such restriction, and nothing else in the app would need to change if a future model
— including, hypothetically, `User` itself, whose PK is an integer — became an assignable target). A
`CharField` is the only `object_id` type that can represent every possible Django PK type without knowing in
advance what they are; a `UUIDField` here would make it impossible to ever grant a role on a non-UUID-keyed
object, which is precisely the flexibility this model exists to provide.

**What breaks or is merely awkward today: nothing.** No code path was found that compares or joins
`ObjectRoleAssignment.object_id` against a `UUIDField` GFK's `object_id`, so the type mismatch never has to be
reconciled at a call site. The only cost is storage/comparison efficiency (`CharField(255)` vs. a native
`uuid` column) on `role_based_permissions_objectroleassignment`, a low-cardinality table by nature (one row
per user/role/object grant), so this is a non-issue in practice.

**Is a single convention achievable?** No, and forcing one would be wrong given `User`'s integer PK exists and
`ObjectRoleAssignment` needs to remain generic. **Recommendation: keep the dichotomy, document the rule so
future GFK additions pick correctly instead of by copy-paste accident** — "closed, guaranteed-UUID target
set → `UUIDField`; open/heterogeneous target set → `CharField`." **Judgement: do-now** for the one-line
docstring addition (free, prevents future drift); **won't-do** for any type unification (would be a
regression, not a fix).

## 4. Constraints

| Issue | Where | Fix | Judgement |
|---|---|---|---|
| Misleading name: `unique_cohort_name_per_site` is actually scoped to `(site_id, organisation, name)`, not just site | `student_management/models.py:24-29` | Rename to `unique_cohort_name_per_organisation`; optionally drop the redundant `site_id` column from the constraint fields, since `organisation` is itself a `SiteAwareModel` (`organisations/models.py:28`) and already pins exactly one site | **Do-later** — `ALTER TABLE ... RENAME CONSTRAINT` and a constraint rebuild are metadata/index operations, not backfill-sensitive; safe to defer to a batch cleanup |
| `CourseInterest`'s unique constraint omits `site` (`user`, `course` only); its near-twin `CourseApplication` includes it (`site`, `user`, `course`) | `course_interest/models.py:41-45` vs. `course_applications/models.py:46-51` | Add `site` to `CourseInterest`'s constraint for consistency with its twin | **Do-later** — technically redundant either way, since `accounts.User` is itself site-scoped (a `User` row belongs to exactly one site), so the two models are already equivalent in practice; the in-flight `learners-associated-with-organisations` spec independently reaches for the same "belt-and-braces, not load-bearing" `site` column on its new `Learner` model (`spec_dd/2. in progress/learners-associated-with-organisations/idea.md:61-63`) — worth matching that emerging convention, but not urgent since there is no real duplicate-row risk to close |
| `unique_together` (older API) used alongside `Meta.constraints`/`UniqueConstraint` (current API) inconsistently: `content_engine` — `Topic`, `Activity`, `Course`, `CoursePart`, `Form` all `["site","slug"]` (`content_engine/models.py:153,168,240,361,450`) and `File` `["site","file_path"]` (`:602`); `student_progress` — `QuestionAnswer` (`:497`), `TopicProgress` (`:521`), `CourseProgress` (`:568`); `webhooks.WebhookSecret` (`:426`) | Various | Convert to named `Meta.constraints = [models.UniqueConstraint(...)]` for consistency with newer models (`Organisation`, `Cohort`, `CourseInterest`, etc., which already use `UniqueConstraint`) | **Do-later** — functionally identical, stylistic only; `student_progress`'s three models are about to be restructured by `better_course_progress_tracking` anyway (`CourseRun`/placement-scoped progress, see §1), so converting them now risks wasted work |

**Recommendation on convention:** pick `Meta.constraints` + `UniqueConstraint` with an explicit `name=` as
the house style going forward (already the majority pattern in newer models) — **do-now** as a documented
rule (free), with the actual conversions of existing `unique_together` usages **do-later**, batched whenever
convenient rather than gated on the deploy date.

## 5. Field naming

| Field | Model | Actually holds | Judgement |
|---|---|---|---|
| `collection` | `UserCourseRegistration` (`student_management/models.py:58-62`) | FK to `content_engine.Course` | **Do-later** |
| `collection` | `CohortCourseRegistration` (`:112-116`) | FK to `content_engine.Course` | **Do-later** |
| `collection` | `RecommendedCourse` (`:304-308`) | FK to `content_engine.Course` | **Do-later** |

All three are legacy names (`content_engine.Course` was presumably once a more generic "collection of
content" concept). Renaming to `course` is worth doing for clarity, but by this unit's own bar it does not
qualify as do-now: a Django field rename (`RenameField`) is a metadata-only column rename in Postgres,
identical cost whether the table has zero rows or a million, and the code-side cost (updating every
`.collection`, `.collection_id`, `collection__title`-style lookup across the codebase) is the *same*
mechanical find-and-replace exercise regardless of when it happens — nothing about waiting makes it harder.
**Recommendation: do-later**, but worth bundling into whatever pass eventually touches these models for other
reasons (e.g. if `better_course_progress_tracking`'s `CourseRun` work already touches `UserCourseRegistration`
FKs, do the rename in the same PR to avoid two separate migrations touching the same rows). No other
drifted field names were found in the models covered by this unit.

## 6. Index coverage

Every gap found below is the kind Postgres can close later with `CREATE INDEX CONCURRENTLY` (or, for a
composite unique constraint, a same-cost-then-or-now rebuild) without meaningful lock contention even against
a populated production table — so, per this unit's own instruction, none of these clear the "materially
cheaper now" bar. Listed for completeness, all **do-later**:

| Gap | Where it's hot | Why it's currently harmless | Judgement |
|---|---|---|---|
| `FormProgress` has no composite index on `(user, form)` — unlike `TopicProgress`/`CourseProgress`, it deliberately allows multiple rows per `(user, form)` (one per attempt), so there is no `unique_together` to piggyback an index on | `educator_interface`'s `CohortCourseProgressPanel._fetch_progress_maps` (`educator_interface/views.py:409-414`), filtered `user_id__in=..., form_id__in=...` | Both `user` and `form` FKs are already individually indexed (Django auto-indexes FK columns); Postgres can bitmap-AND the two single-column indexes reasonably well at current/near-term scale | **Do-later** — and `better_course_progress_tracking` is about to change this model's shape anyway (placement-scoped progress, `spec_dd/2. in progress/better_course_progress_tracking/idea.md:74-93`); don't index a model that's mid-redesign |
| `ContentCollectionItem` has no composite index on `(collection_type, collection_id)` or `(child_type, child_id)` — only `collection_type`/`child_type` are auto-indexed (they're FKs), `collection_id`/`child_id` are plain `UUIDField`s (`content_engine/models.py:385-404`) | `Course.children()`/`CoursePart.children()` (`content_engine/models.py:302-322,363-375`), called on every course/part page render across both student and educator surfaces, and reused by `CohortCourseProgressPanel` | Table is currently small (one row per content-item placement); the `content_type` half of the pair already narrows the scan a lot in practice | **Do-later** |
| `role_based_permissions.ObjectRoleAssignment` — already has `Index(fields=["content_type","object_id","role","is_active"])` (`models.py:112-115`) | N/A — flagged only to note this one is already correctly indexed | No gap | Not applicable — included to show the pattern is already followed correctly here |
| `webhooks.WebhookEndpoint.event_types__contains=[...]` (`webhooks/events.py:71`) — a JSON containment lookup on an un-indexed `JSONField(default=list)` (`webhooks/models.py:52`) | Fires on every outbound webhook event, matching subscribers by event type | Per-site endpoint counts are small (a handful of configured webhooks, not thousands); a GIN index would help at scale but nothing here is slow today | **Do-later** — out of this unit's stated scope (educator interface / reports) but noted since it was found along the way; a Postgres GIN index add is exactly the kind of thing `CREATE INDEX CONCURRENTLY` handles cleanly post-deploy |

No index gap was found in the educator-interface or reports query paths that reaches "expensive to add
later" — `CohortDeadline`/`StudentDeadline`/`UserCohortDeadlineOverride` GFK lookups are always additionally
scoped by an already-indexed FK first (`cohort_course_registration=selected_reg`,
`educator_interface/views.py:452-456,471-478`), `CourseProgress`/`TopicProgress` already get a composite index
via their `unique_together` (`student_progress/models.py:568,521`), and `GeneratedReport.status` already
carries `db_index=True` (`reports/models.py:66`). **Overall judgement for this section: no do-now items.**

## 7. JSONField usage

| Field | Where | Genuinely schemaless, or a table waiting to happen? | Judgement |
|---|---|---|---|
| `content_engine.Course.access_config` | `content_engine/models.py:182-190` | **Genuinely schemaless, by explicit design.** Docstring at the field itself: *"BACKEND-PRIVATE: no view, template, or utility may read or branch on `access_config` directly"* (line 178-180) — the shape is owned entirely by whichever `COURSE_ACCESS_BACKEND` is configured (`freedom_ls/course_access/backends.py`), validated per-backend via a dedicated system check (`freedom_ls/course_access/checks.py:27-66`, error `E001`), and different backends can legitimately want different keys. Normalising this into columns would require FLS to pick one backend's shape as canonical, defeating the pluggability the field exists to provide | **Won't-do** |
| `student_progress.FormProgress.scores` | `student_progress/models.py:91` | **Genuinely polymorphic, currently.** Shape depends on `Form.strategy`: a flat `{"score": int, "max_score": int}` for `QUIZ` (`score_quiz`/`compute_quiz_scores`, `:363-397`) vs. a nested category tree (`{category: {score, max_score, sub_categories: {...}}}`) for `CATEGORY_VALUE_SUM` (`score_category_value_sum`, `:235-361`). Never queried at the database level (confirmed by repo-wide grep — every read site is `fp.scores.get(...)` in Python, e.g. `reports/gather.py:282-285`); always recomputed from source `QuestionAnswer` rows, so it's derived/cache data, not a system of record. Not evaluated further — `better_course_progress_tracking` is actively restructuring this model | **Won't-do** (for this unit; revisit if scoring needs bulk filtering/sorting at the DB level in future reporting work) |
| `content_engine.BaseContent.meta` | `content_engine/models.py:64-66` | Optional freeform metadata, `help_text="Optional metadata as key-value pairs"`. Grep found **no read site anywhere in the codebase** outside the admin form (`content_engine/admin.py:126` etc.) — currently write-only/unused | **Won't-do** — nothing to normalise; revisit only once something actually reads it |
| `content_engine.BaseContent.tags` | `content_engine/models.py:67` | A list of freeform strings, but used as a Django admin `list_filter` (`content_engine/admin.py:133,145,189,217,239`) — `list_filter` on a `JSONField` storing a list filters by exact-list-value, not by "contains this tag," so the admin's own use of the field doesn't actually work the way a tag filter should. The same file already has the correct precedent one field away: `Course.learning_outcomes` is an `ArrayField(CharField(...))` (`content_engine/models.py:210-217`) for exactly this "list of short strings" shape | Recommend `ArrayField(CharField(max_length=...))` to match `learning_outcomes`'s existing precedent, or a real `Tag` model + M2M if cross-content tag browsing is ever wanted. **Judgement: do-later** — the admin filter being non-functional is a pre-existing minor bug, not a data-loss risk, and the field is unused outside the admin, so there is no urgency; cheap to fix at either time since it's currently empty/unused |
| `content_engine.ContentCollectionItem.overrides` | `content_engine/models.py:407-411` | Round-tripped by the content-import pipeline (`content_engine/management/commands/content_save.py:685`, writes it out) but **never read anywhere** — no consumer interprets it. An unimplemented placeholder | **Won't-do** — nothing to normalise until a reader exists; flag for whoever eventually implements per-placement overrides that the field is already there |
| `accounts.SiteSignupPolicy.additional_registration_forms` | `accounts/models.py:148` | An ordered list of dotted Python import paths to `django.forms.Form` subclasses (`accounts/registration_forms.py:1-5`), actively used across `accounts/middleware.py`, `views.py`, `registration_forms.py`. Genuinely configuration, not data — never filtered, always read/written whole | **Won't-do** — correct use of JSON for a small, ordered, whole-read config list |
| `webhooks.WebhookEndpoint.event_types` | `webhooks/models.py:52` | A small, bounded list of event-type strings per endpoint (dozens at most), queried via `__contains` (`webhooks/events.py:71`, see §6) | **Won't-do** — right-sized for JSON; if it ever needs a real index, that's a Postgres GIN index add (§6), not a schema change |
| `webhooks.WebhookEvent.payload` | `webhooks/models.py:368` | The actual event payload — inherently variable shape (different event types carry different data), read/replayed whole, never queried into | **Won't-do** — textbook correct JSONField use |

## Risks and gotchas

1. **The three sibling specs are actively restructuring exactly the models this unit would otherwise touch
   hardest.** `better_course_progress_tracking` renames `CourseProgress` → `CourseRun`, adds new FKs, and
   makes `TopicProgress`/`FormProgress` placement-scoped
   (`spec_dd/2. in progress/better_course_progress_tracking/idea.md:41-93`); `learner-terminology-rename`
   renames `StudentDeadline` → `LearnerDeadline` and its field/constraint (`.../learner-terminology-rename/idea.md:83-91`);
   `learners-associated-with-organisations` adds a new `Learner` model with its own timestamp/constraint
   pattern (`.../learners-associated-with-organisations/idea.md:48-63`). Any plan built from this research
   must sequence around these — timestamps on the progress-tracking models are explicitly deferred here for
   that reason (§1), and the deadline-model timestamp recommendation should land under whichever name
   `learner-terminology-rename` settles on.
2. **The `User` PK question is the one place a "leave it" verdict genuinely depends on believing severity is
   low.** If a future spec adds a public-facing API or export that serializes `user_id` directly (the webhook
   payload at `student_management/models.py:97` is the existing precedent for exactly this pattern), the
   enumeration concern documented in §2 stops being hypothetical. Worth a standing note for whoever designs
   that surface, not a reason to revisit this unit's recommendation now.
3. **`content_engine.BaseContent.meta`/`.tags` being unread today is a snapshot, not a guarantee.** If content
   authoring grows a real use for either field between now and deploy, the "won't-do" verdict in §7 should be
   re-checked — an unread JSONField that gains a consumer mid-flight is exactly the kind of drift this whole
   pre-deploy exercise exists to catch early.
4. **The timestamp mixin decision (§1) needs to land before the `content_engine`, `Cohort`/`CohortMembership`,
   and deadline-model additions**, since those are presented as depending on it (`TimestampedModel` applied
   per-model). Doing the additions ad hoc per model first and retrofitting a mixin later would mean touching
   the same models twice.
5. **The `unique_cohort_name_per_site` rename (§4) touches the same model (`Cohort`) that
   `learners-associated-with-organisations` is adding a sibling `Learner` model next to** — no direct
   dependency, but worth doing in the same review pass for locality of change.

status: ok
