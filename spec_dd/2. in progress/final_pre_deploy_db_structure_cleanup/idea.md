# Final pre-deploy database structure cleanup

FreedomLS has not been deployed. Once it is, schema changes stop being cheap: FLS ships as a git
submodule into downstream projects that run `migrate` against their own databases, so every structural
decision made now is one somebody else's production data has to live with.

This is the sweep that catches what the shipped specs did not. It is a cleanup, not a feature hunt.
Names, app placement, relationships, and the handful of additive changes that are only honest to make
while no rows exist.

## The window

FLS is never deployed standalone. A production deployment is a *concrete project* built from the
`freedom-ls-concrete-template` repo, so the point of no return is **the first `migrate` any downstream
project runs against a database it intends to keep**.

That point is closer than it reads. `docs/product/deployment.md` records the build step as built. The
template repo ships Caddy, Docker Compose and CI that pushes a per-commit SHA-tagged image, and
production Cloudflare R2 buckets were configured on 2026-08-27. What remains unbuilt is VPS
provisioning and the step that pulls an image onto a server. The gap used to be three layers. It is
one.

Nothing here says a downstream `migrate` has run, and nothing here can. Dev databases in this repo are
disposable and rebuilt per worktree, and this tree has no visibility into the deploy repo at all.
Silence is not evidence either way. The window is open, it is narrower than it looks, and it will not
announce when it shuts.

---

## Do now

Ranked by cost if deferred, which is the only ranking that matters here.

| # | Finding | Cost if deferred |
|---|---|---|
| 1 | **Timestamps are absent, not merely inconsistent.** `accounts.User` carries no timestamp of any kind, not even a signup date. `content_base.BaseContent` has none, which is eight content models at once, and `File`, `ContentCollectionItem` and `form_engine.QuestionOption` sit outside that base and need the same fix individually. Nor do `Organisation`, `Cohort`, `CohortMembership`, `SiteSignupPolicy`, `CourseFormAttempt`, or the three deadline models, which are edited in place and want `updated_at` as well as `created_at`. `QuestionAnswer` has `last_updated_time` and no `created_at`, and `save_answers()` rewrites it on every visit to a form page, so the original submission time dies the first time a learner edits an answer. | The one genuinely unbackfillable item. A `created_at` added after rows exist is not a recovered fact, it is a fabricated one, and nothing in the data distinguishes the two afterwards. |
| 2 | **Migration history should be reset once, project-wide.** Delete each app's migrations, regenerate a fresh `0001_initial`. 47 files across 11 apps, 18 of them in `content_engine`, which carries a merge migration caused by a duplicate `0010_` and a `0015`/`0016` delete pair that only unwinds form models `form_engine` recreates from scratch. | The option expires at the window above and never returns. Decision 5 runs it **last**, behind a re-check gate. |
| 3 | **`webhooks` declares no `label`**, so its four tables are `webhooks_*`, the only prefix in the schema that is not `freedom_ls_`. `health` is unlabelled too, and owns no tables. `icons` is unlabelled by design, per Decision 3. | The one genuine table-namespacing gap. After deploy it is a downstream-run data migration renaming production tables, and Django's own docs warn that a label change after migrations ship "will result in breaking changes to ... any existing installs". It is also a boot-time collision: a downstream project with its own `webhooks` or `health` app cannot start. |
| 4 | **`LearnerCourseRegistration.collection`, `CohortCourseRegistration.collection` and `RecommendedCourse.collection`** are FKs to `Course`, while `course_applications` and `course_interest` already call the identical field `course`. `collection` is also already taken: `ContentCollectionItem.collection` is a genuine GFK over `Course`/`CoursePart`, and the two meanings sit in the same queries. | At the database level a rename is metadata-only and costs the same forever. But FLS is a *library*. Once a downstream project writes `.collection`, the rename becomes a breaking API change needing upgrade notes and downstream edits. That is the cliff. 106 files reference the name, so the sweep has to tell the two meanings apart. |
| 5 | **`UserCohortDeadlineOverride` names a `User` it no longer has.** Its only person-identifying field is `learner`, and the sibling models re-keyed by the same spec already say `Learner` in their names. | The same cliff as #4, on a footprint of 12 files, all internal to FLS today. A class rename is metadata-only in Postgres now and a breaking import rename for any downstream project afterwards. |
| 6 | **`QuestionAnswer.question` is CASCADE**, so deleting one `FormQuestion` erases every learner's answer to it. `FormProgress.form` being `PROTECT` stops the whole `Form` from being deleted; it says nothing about a question being trimmed off one. | Silent, unrecoverable learner-data loss through a live admin page. `PROTECT` is one line now and a migration plus a workflow change later. The two registration `.collection` FKs should become explicit `PROTECT` in the same pass. They are already blocked transitively, because every active registration mints a `PROTECT`-guarded `CourseProgress`, which leaves this model's integrity resting on another model's cascade policy. |
| 7 | **The Django admin exposes full delete on `Topic`, `Course`, `CoursePart`, `Form`, `FormPage`, `FormQuestion` and `QuestionOption`**, contradicting `docs/product/content-editing-workflow.md`, which states there is no admin-side or browser-based authoring interface. It is the only live path any of these cascades fire from. Re-import is upsert-only and never deletes. | No deadline. This costs the same at any time. It earns do-now because it is the cheapest change in the document and closes the most ground, including the one gap no `on_delete` can reach (Decision 2). |
| 8 | **The three deadline models' GFK `content_type` FKs are CASCADE**, against the codebase's own precedent: `TopicProgress.collection_item`, `CourseProgress.last_accessed_item` and `CourseFormAttempt.collection_item` are all `SET_NULL`, so that removing what a pointer names cannot destroy the record holding it. | Consistency fix. Each model's `clean()` already treats a null `(content_type, object_id)` pair as a whole-course deadline, so `SET_NULL` degrades into a state the model already validates and renders. |
| 9 | **`WebhookDelivery.endpoint` is CASCADE**, so an ordinary admin delete of an endpoint config erases every delivery attempt ever recorded against it, with their status codes and response bodies. Its sibling `WebhookDelivery.event` is CASCADE too but unreachable, because both those admins already hard-disable delete. | The one place in the matrix where the data lost is compliance evidence rather than learner progress, and it is the reachable half of the pair. See the open question. |
| 10 | **Move `RecommendedCourse` into its own app.** It is the third member of the pre-registration-intent family, after `CourseApplication` and `CourseInterest`, which each got a single-model app. It depends on nothing they do not. | Only free during the reset pass, where a fresh `0001_initial` absorbs the move. Afterwards it needs a state-only migration to keep the table while its app-label lineage changes. Well-trodden, but no longer free. Runs **with** the reset, not before or after it. |
| 11 | **Delete `app_authentication`.** Not installed, no migrations, zero tables. But `Client.api_key` is a plaintext, queryable, admin-visible `CharField`, one uncommented line away from shipping, in a repo where `WebhookSecret` next door already uses `EncryptedTextField`. | A dormant credential trap for whoever re-enables it without re-reading the model. If API-client auth is wanted later it should be designed properly, with hashed key storage and a rotation story. |
| 12 | **Write down the extractable-app convention and guard it.** Nothing in `docs/` states when `SiteAwareModel` applies, and no check anywhere validates app labels. `freedom_ls/icons/checks.py` also raises `freedom_ls.E00x` ids under a label no installed app holds. | Near-zero cost. It stops #3 recurring in an app not yet written, and stops a blanket rule from fighting the three apps already queued to leave FLS. See Decision 3. |
| 13 | **Four one-line clarity fixes.** `default_auto_field` is declared in 19 `apps.py` files and consulted in two: `accounts.User` and `SystemRoleAssignment`, the only models not rooted in `SiteAwareModel`'s explicit UUID pk. `accounts.User` has no comment recording that its integer PK is deliberate. The GFK `object_id` type rule is undocumented. And `ContentCollectionItem` still carries a dead `collection_old` field from the pre-GFK design. | Free. Each one stops a future contributor "fixing" something already correct, or copying dead configuration into a new app out of habit. |
| 14 | **Constraint defects.** `Cohort`'s constraint is named `unique_cohort_name_per_site` but scopes to `(site_id, organisation, name)`, so two organisations on one site can already share a cohort name. `CourseInterest` and `Learner` omit `site` where `CourseApplication` includes it. And the same column is spelled three ways across `Meta.constraints`: `"site_id"` in `learner_management`, `"site"` elsewhere, omitted in `course_interest`. | No deadline on its own: a constraint rename is catalog-only at any table size, and the missing `site` is unreachable because `User`, `Course` and `Organisation` are all themselves site-scoped. Rides along because constraint names persist in the database and the reset absorbs the migration. Settle `"site"` as the house spelling in the same pass. |
| 15 | **Eight `unique_together` blocks** remain on `Topic`, `Activity`, `Course`, `CoursePart`, `File`, `Form`, `QuestionAnswer` and `WebhookSecret` where the rest of the codebase uses named `UniqueConstraint`. | No deadline, and functionally identical. The gain is FLS naming the constraint instead of the database, which is only free while the reset is still ahead of it. |
| 16 | **Two index gaps.** `ContentCollectionItem` has no composite index on `(collection_type, collection_id)` or `(child_type, child_id)`, since its `Meta` carries only `ordering`, and `collection_id`/`child_id` are plain `UUIDField`s. `WebhookEndpoint.event_types` takes a JSON containment lookup on every outbound event with no GIN index. | `CREATE INDEX CONCURRENTLY` closes both later without meaningful lock contention, so neither expires. Both are a handful of lines in a `Meta` the pass is already editing. |
| 17 | **Move `calculate_course_progress_percentage` from `learner_management/utils.py` to `learner_progress`.** It has no `learner_management` dependency and every real caller is in `learner_progress`. | No deadline. It buys correct ownership, not a smaller dependency graph: `learner_progress` imports `Learner` and both registration models across four other files, because that is what a `CourseProgress` is keyed on. A 26-line function, two real call sites, two `qa_helpers` commands, and one test module that moves wholesale. |
| 18 | **`content_base.tags` is a `JSONField` holding a list of short strings**, one field away from `Course.learning_outcomes`, which is already the `ArrayField` this shape wants. | No deadline, and no data to migrate: nothing in `demo_content` sets it, no query filters on it, no template reads it. `ArrayField` is the correct type and enables `__contains`/`__overlap` and a GIN index. It does **not** fix the admin filter (see do-later), so do not claim it does. |

## Do later

No deadline pressure, and nothing here rides along with the pass above: one is mostly a decision to
leave things alone, one needs a filter this cut is not writing, and one is a feature.

| Finding | Why it can wait |
|---|---|
| A custom admin filter for `tags` | `list_filter = ("tags",)` uses `AllValuesFieldListFilter`, which lists distinct whole values. That is equally broken on an `ArrayField` as on a `JSONField`, so #18 does not fix it. Filtering by one tag needs a `SimpleListFilter` that unnests, and that is true whichever type the field is. |
| Normalise existing domain-named timestamps (`registered_at`, `assigned_at`, `requested_at`, `timestamp`) | A Postgres column rename is catalog-only at any table size. Several of these names also carry meaning `created_at` would lose. `registered_at` means "access granted", not "row created". |
| `Activity` has no `ActivityProgress` model | Real, and genuinely deferrable rather than conveniently so. No course places an `Activity` today, so there is no progress to migrate around whenever the model arrives. `CourseItemProgress` is already the abstract base it would extend. |

## Won't do

- **An explicit `through` model for `QuestionAnswer.selected_options`.** It is the only fix here whose
  price rises after deploy, a bare migration now against a join-row data migration later. But locking
  the admin down (#7) closes the same gap for free, and the through table buys nothing else.
- **A frozen answer-text snapshot on `QuestionAnswer`.** Preserving historical answer text is a
  feature, not database structure, and a nullable field costs the same at any time. The real gate is
  "before the first learner answer exists", which is deploy time.
- **Convert `accounts.User` to a UUID PK.** FK columns already agree automatically, so this is not an
  integrity problem. The one real cost is that `User` is the only object whose identity appears in a
  URL as a small sequential integer, and `email` is the actual auth key behind per-object permission
  checks. Defensible, not broken.
- **Unify the GFK `object_id` types.** `UUIDField` where the target set is closed and guaranteed-UUID;
  `CharField(255)` exactly once, on `ObjectRoleAssignment`, where the target set is deliberately open.
  Forcing one type would make it impossible to grant a role on a non-UUID-keyed object.
- **Merge the three deadline models** into one polymorphic model. `deadline_utils` resolves all three
  by name in a fixed priority order and bulk-indexes each by its own FK-typed registration id. A GFK
  owner would replace three indexed lookups on the hot deadline path with one, and break the batching.
- **Merge `course_access` / `course_applications` / `course_interest`.** `course_access` has no models
  at all, only a swappable-backend seam, and the other two carry explicit "do not architect these
  away" notes in their own model docstrings.
- **Rename `learner_management`.** "Management" is vague but accurate for cohorts, learners,
  registrations and deadlines, and nothing narrower covers them without splitting models that validate
  against each other. There is no cost asymmetry making this pre-deploy-urgent, and #10 tightens the
  fit anyway.
- **Retention, anonymisation, and a canonical `delete_user()` flow.** Every user-side FK stays
  `CASCADE`, unchanged. `user-data-retention-idea.md` owns this, and CASCADE is one of the three
  defaults it will choose between per model.
- **Touch `xapi_learning_record_store`.** Its `models.py` is fully commented out and it owns no
  tables. Its `apps.py` `name` does not match its real module path, so installing it as-is would
  `ImportError`. But `xapi_implementation` already scopes the directory rename that fixes it, and
  doing it here only creates merge friction.

---

## Decisions

1. **Timestamps go on a standalone `TimestampedModel` mixin, not on `SiteAwareModel`.** Folding them
   in would miss the two models with the least coverage: `accounts.User` subclasses the lower
   `SiteAwareModelBase`, and `SystemRoleAssignment` is a plain `models.Model`, deliberately not
   site-aware. It would also force a generic pair onto models that already carry a correct
   domain-named timestamp, producing two fields that say the same thing. The mixin lands *before* the
   per-model additions, or the same models get touched twice.

   The mixin carries both fields, so `updated_at` arrives wherever `created_at` does rather than
   waiting for a later pass. One call-site fix goes with it: `role_based_permissions` deactivates
   roles through `QuerySet.update()`, which never fires `auto_now`, so its three deactivation sites
   have to set `updated_at` explicitly or the column goes stale unnoticed.

2. **The content admin loses delete.** `webhooks/admin.py` already overrides `has_delete_permission`
   to `False` on its two audit models, and the same pattern applies to the content models. This is the
   only fix that reaches the gap Django gives no lever for: `QuestionAnswer.selected_options` uses an
   auto-generated through table, so deleting one `QuestionOption` silently drops the join row from
   every answer that selected it, and `PROTECT` on `QuestionAnswer.question` does not close that.
   Locking the admin down also makes the code match `docs/product/content-editing-workflow.md` instead
   of contradicting it. It does not replace the `PROTECT` changes. `danger_content_delete` and any
   future API bypass admin permissions entirely.

3. **Extractable apps are a named exception to both the `freedom_ls_` label convention and the
   `SiteAwareModel` convention.** An app is extractable when a spec has committed it to leaving
   `freedom_ls/` as its own installable package. Today that is `icons`, which becomes
   `django_semantic_iconify`, so an FLS-prefixed label would only be renamed twice;
   `markdown_rendering`; and the planned `referral-link-tracker`, designed with no `site_aware_models`
   edge at all. They are exempt from nothing else. Dependency direction still points host to app,
   never the reverse. `health` is not extractable and gets `freedom_ls_health`.

   Write the convention into `docs/` before `referral-link-tracker` is built, or a future contributor,
   or `/fls-dev:plan_structure_review`, will read the missing edge as an oversight and "fix" it. The
   guardrail belongs beside the conformance suite as an FLS-internal probe rather than an exported
   downstream check, and encodes the exemption as an allowlist rather than asserting a blanket prefix.
   The related house rule: a system-check id's label segment must equal that app's own registered
   `AppConfig.label`, whatever it is.

4. **The three pre-registration course FKs keep CASCADE**, on `CourseApplication`,
   `CourseInterest` and `RecommendedCourse`. None has progress, answers or registrations behind it. They are pre-registration
   signals, and deleting the course discards a stale preference. `CourseApplication` is the one to
   revisit later, when application review adds a decision state. At that point deleting the course
   would erase a decision record rather than a preference, and that is the review spec's call.

5. **The migration reset runs last, behind a re-check gate.** All four specs it was waiting on have
   landed. Immediately before executing, **re-verify that no downstream project has run a `migrate` it
   intends to keep**. In practice that means asking whoever owns the deploy repo whether a VPS has
   been provisioned and `migrate` run against a Postgres instance anyone intends to keep data in. This
   repo's own green tests and clean migration state are not an answer to that question. If the answer
   is yes, or cannot be obtained, fall back to ordinary forward migrations, which are always safe.

   This is a **declared, one-time exception** to `CLAUDE.md`'s "never edit existing migration files".
   The rule guards against rewriting a migration some database's history already vouches for having
   run. Deleting a file and regenerating from current model state does not touch such a file. It
   discards an artifact before it was ever load-bearing. The exception covers this one pass and
   nothing after it: once any downstream `migrate` has run against a database meant to be kept, the
   door is closed permanently.

   There is precedent in this repo already. `learner_management` and `learner_progress` are each a
   single `0001_initial` today, and got there by exactly this operation, deletion and regeneration
   rather than squashing with a `replaces` list, during the specs that restructured them. Rewriting
   label strings inside existing files is the third option, and this cut rejects it outright: it
   carries the same downstream risk with none of the benefit, and produces files that still look
   historical but no longer are.

---

## Ordering

1. The `TimestampedModel` mixin, then the per-model timestamp additions.
2. The `webhooks` and `health` label fix, as its own separately-reviewable change. It rewrites label
   strings across nine of ten migration files and should diff against `docs/app_structure.md` alone.
3. The `collection` → `course` and `UserCohortDeadlineOverride` renames. Both are field- and
   class-level, so keep them clear of any model move.
4. The rest of the do-now list.
5. **The migration reset, last**, behind the Decision 5 gate, carrying the `RecommendedCourse` app
   move with it.

Two hazards worth naming. `PROTECT` on `QuestionAnswer.question` will make `danger_content_delete`
fail loudly unless it clears answers before questions. It already clears progress before content for
exactly this reason, so extend the same ordering and say why in the command's help text. And a
`RecommendedCourse` app move done at any time other than the reset needs a state-only migration, which
is why it is pinned to step 5 rather than floated.

## Open question

**`WebhookDelivery.endpoint`: `SET_NULL` or `PROTECT`?** `PROTECT` needs nothing added but blocks
deleting an endpoint that has any delivery history at all, which may be too strict for a
rotate-and-replace workflow. `SET_NULL` needs the field to become nullable, and needs
`WebhookEndpoint.url` denormalised onto the delivery so the audit row still says where it was trying
to send once the endpoint is gone.

---

## Research

- `research_model_inventory.md`: every concrete model, with a keep/rename/move/re-relate verdict
- `research_deletion_semantics.md`: the full `on_delete` matrix and the live delete paths
- `research_field_level_hardening.md`: timestamps, PK types, GFK key types, constraints, indexes, JSONFields
- `research_app_boundaries_and_labels.md`: app labels, table namespacing, the extractable-app convention, dormant apps
- `research_migration_reset_strategy.md`: squash vs rewrite vs reset, and the tripwire
- `research_roadmap_pressure.md`: what queued work implies about today's schema (all 25 items: nothing)
- `research_forms_app_extraction.ANSWERED.md`: kept for its costing, since the extraction shipped
- `notes_for_other_specs.md`: findings this cut surfaced that belong to somebody else's spec
