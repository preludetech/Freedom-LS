# Final pre-deploy database structure cleanup

FreedomLS has not been deployed. Once it is, schema changes stop being cheap: FLS ships as a git
submodule into downstream projects that run `migrate` against their own databases, so every
structural decision made now is one somebody else's production data has to live with.

This is the sweep that catches what the in-flight specs don't. It is a cleanup, not a feature hunt —
renames, app placement, relationships, and the handful of additive changes that are only honest to
make while no rows exist.

**The window is narrower than "before we deploy".** FLS is never deployed standalone; a production
deployment is a *concrete project* (`docs/product/deployment.md:110-116`). So the point of no return
is **the first `migrate` any downstream project runs against a database it intends to keep**. The one
downstream project that exists, `ConcreteFlsImplementation`, currently has no deployment artifacts at
all — no Dockerfile, no compose file, no CI (`spec_dd/3. done/2026-07-09_09:42_support-concrete-project-deployment-master-decomposed-into-specs/concrete_project_idea.md:25-27`).
The window is open. It will not announce when it shuts.

---

## The forms question, answered

The idea asked: *should the forms that are managed by the content engine be in their own app? they
seem complicated enough that they should be.*

**No.** The intuition is real but mis-locates the complexity. The hard parts of forms — scoring,
attempts, resumability, quiz percentages, per-question answer state — already live in
`learner_progress` (`FormProgress` is 405 of 571 model lines), and the player UI already lives in
`learner_interface` (`views.py:832-1338`). Both already have their own apps. What is left in
`content_engine` is structural definition: five models of title, order and FK fields, no more
intrinsically complex than `Course`/`CoursePart`'s own GFK-based `children()` tree, which nobody is
proposing to extract.

Extraction would also cost real things for no functional gain: the abstract bases
(`BaseContent`/`TitledContent`/`MarkdownContent`) have no good new home, the single shared pydantic
registry and single-pass importer would have to be forked or re-coupled, and every table would be
renamed. The decisive fact: **six apps that already depend on `content_engine` import
`Form`/`FormPage`/`FormQuestion` interchangeably with `Topic`/`Course` in the same functions.**
Extraction wouldn't shrink `content_engine`'s fan-in — it would add at least seven new edges to the
dependency graph.

What forms actually want is a `models/` package with a `forms.py` module inside the same app — same
label, same tables, zero migration, most of the organisational benefit. Because that costs no
migration, it carries **no pre-deploy deadline at all**, which is why it lands in do-later below
rather than do-now. That is the honest answer, not a hedge.

---

## Ranked findings

Ranked by cost-if-deferred, which is the only ranking that matters here.

### Do now

| # | Finding | Cost if deferred |
|---|---|---|
| 1 | **`webhooks` has no `label`** (`freedom_ls/webhooks/apps.py`), so its four models' tables are `webhooks_*`, not `freedom_ls_webhooks_*`. `health` and `icons` are also unlabelled (no models, so no tables). | The one genuine table-namespacing gap in the codebase. After deploy this is a downstream-run data migration renaming production tables. It is also a boot-time collision risk: a downstream project with its own `webhooks`, `health` or `icons` app cannot start. Django's own docs warn a label change after migrations ship "will result in breaking changes to ... any existing installs". |
| 2 | **Timestamps are absent, not merely inconsistent.** No `created_at`/`updated_at` on `accounts.User` (no timestamp of any kind — not even a signup date), `Cohort`, `CohortMembership`, all 11 `content_engine` models, `Organisation`, or the three deadline models. | The one genuinely unbackfillable item. A `created_at` added after rows exist is not a recovered fact, it is a fabricated one, and nothing in the data distinguishes the two afterwards. |
| 3 | **Authored content cascades into learner records.** Three separate CASCADE chains — `FormProgress.form`, `TopicProgress.topic`, `CourseProgress.course` — mean hard-deleting a `Form`/`Topic`/`Course` silently destroys every learner's progress for it. Plus `QuestionAnswer.question` and the two registration `.collection` FKs. Nine FKs should become `PROTECT`. | Silent, unrecoverable learner-data loss. Cheap to fix now; after deploy it needs a migration plus an admin-workflow change. Moodle enforces exactly this rule at the product level. |
| 4 | **Migration history should be reset once, project-wide** — delete each app's migrations, regenerate a fresh `0001_initial`. 57 files today, including four that only service a `Student` model deleted long ago and a merge migration caused by a duplicate `0010_`. | The option expires at the tripwire above and never returns. See Decision 4 — this runs **last**, behind a re-check gate. |
| 5 | **`LearnerCourseRegistration.collection`, `CohortCourseRegistration.collection`, `RecommendedCourse.collection`** are all hard FKs to `content_engine.Course`. `course_applications` and `course_interest` already call the identical field `course`. | At the database level a rename is metadata-only and costs the same forever. But FLS is a *library*: once downstream projects write `.collection` in their own code, the rename becomes a breaking API change needing upgrade notes and downstream edits. That is the cliff, and it is a real one. |
| 6 | **`calculate_course_progress_percentage` lives in `learner_management/utils.py:17`** but its only real caller is `learner_progress` (`signals.py:25`). It is the sole cause of the `learner_progress → learner_management` runtime edge (`docs/app_structure.md:88`). | Nearly free to fix, and it deletes a dependency-graph edge outright. Deferring costs nothing but nothing is gained by waiting either. |
| 7 | **Two constraint defects.** `Cohort`'s constraint is named `unique_cohort_name_per_site` but is on `(site_id, organisation, name)`. `CourseInterest`'s unique constraint omits `site` where its near-twin `CourseApplication` includes it. | Individually cheap at any time. Included as do-now because the pass is already open in these files, not because deferring is dangerous. Constraint names do persist in the database. |
| 8 | **Deadline GFK `content_type` FKs are CASCADE** on three models, against the codebase's own precedent (`CourseProgress.last_accessed_content_type` is deliberately `SET_NULL` "so deleting a content model type cannot cascade-delete progress"). | Consistency fix; each model's `clean()` already treats a null pair as a whole-course deadline, so `SET_NULL` degrades into an already-tested state. |
| 9 | **`WebhookDelivery.endpoint` is CASCADE**, so deleting an endpoint config erases its entire delivery audit history. | Same audit-survives-its-subject principle. A new finding, not in the original brief. |
| 10 | **Three one-line clarity fixes.** `webhooks/apps.py` sets `default_auto_field = BigAutoField` which has never had any effect (its models are `SiteAwareModel`, UUID PK). `accounts.User` has no comment recording that its integer PK is deliberate. The GFK `object_id` type rule is undocumented. | Free. Each one prevents a future contributor "fixing" something that is already correct. |
| 11 | **Delete `app_authentication`.** Not installed, no migrations, zero tables — but its `Client.api_key` is a plaintext, queryable, admin-visible `CharField`, one uncommented line away from shipping. | Code hygiene riding along, not a DB-structure finding — flagged as such. If API-client auth is wanted later it should be designed properly, with hashed key storage and a rotation story. |

### Do later

No deadline pressure — these cost the same after deploy as before it.

| Finding | Why it can wait |
|---|---|
| Split `content_engine/models.py` into a `models/` package with `forms.py` | Pure code organisation. No label change, no table rename, no migration. |
| Extract `RecommendedCourse` into its own small app | It is the third member of the "pre-registration intent" family (`CourseApplication`, `CourseInterest`) that each got their own single-model app. Structurally identical, just misplaced. A model move is a migration-lineage question — keep it away from the field rename. |
| `Activity` has no `ActivityProgress` model | A real gap: an `Activity` in a course tree is permanently untracked. But `CourseItemProgress` is already an abstract base built so the subclass is close to free to add later. Building it now is exactly the scope creep this idea rules out. |
| Normalise existing timestamp names (`registered_at`, `requested_at`, `assigned_at`, `timestamp`) | A Postgres column rename is catalog-only at any table size. Several of these names also carry domain meaning `created_at` would lose — `registered_at` means "access granted", not "row created". |
| Convert remaining `unique_together` usages to named `UniqueConstraint` | Functionally identical. Several sit on models `better_course_progress_tracking` is about to restructure. |
| `content_engine.tags` should be an `ArrayField`, matching `Course.learning_outcomes` one field away | Used as an admin `list_filter` where JSON-list filtering doesn't work usefully. A pre-existing minor bug, and the field is unused outside the admin. |
| Index gaps (`FormProgress(user, form)`, `ContentCollectionItem` GFK pairs, `WebhookEndpoint.event_types` GIN) | `CREATE INDEX CONCURRENTLY` closes all of these later without meaningful lock contention. Nothing here reaches "expensive to add later". |

### Won't do

Stated so they read as deliberate, not as gaps.

- **Extract forms into their own app.** ~~Answered above.~~ Superseded: this shipped as
  `spec_dd/2. in progress/extract_forms_into_seperate_app/1. spec.md`, landing before this cleanup so
  the migration reset in finding 4 now runs *after* the extraction and regenerates `0001_initial` for
  `content_base`/`form_engine` along with everything else.
- **Convert `accounts.User` to a UUID PK.** FK columns already agree automatically — this is not an integrity problem. The one real cost is that `User` is the only object whose identity appears in a URL as a small sequential integer. Severity is low: `email` is the actual auth key and every view goes through per-object permission checks. Defensible choice, not a broken one.
- **Unify the GFK `object_id` types.** `UUIDField` is used where the target set is closed and guaranteed-UUID; `CharField(255)` exactly once, on `ObjectRoleAssignment`, where the target set is deliberately open. Forcing one type would be a regression — it would make it impossible to ever grant a role on a non-UUID-keyed object.
- **Merge the three deadline models** into one polymorphic model, or split them into their own app. They are near-identical by shape but each hangs off a different registration; consolidating trades three explicit FK-typed models for one GFK on the hot deadline-lookup path.
- **Merge `course_access` / `course_applications` / `course_interest`.** The separation is deliberate and documented in the code itself: `course_access` is a swappable-backend seam, and the other two are minimal seeds with committed future shapes.
- **Add an answer-text snapshot to `QuestionAnswer`.** See Decision 3 — the research recommended it and the recommendation was wrong for this cut.
- **Retention, anonymisation, and a canonical `delete_user()` flow.** Every user-side FK stays `CASCADE`, unchanged and flagged. This belongs to `user-data-retention-idea.md`.
- **Touch `xapi_learning_record_store`.** Fully commented out, no tables, and `xapi_implementation` already plans the rename it would otherwise need.

---

## Decisions

1. **The `webhooks` label fix does not ride along with `learner-terminology-rename`.** The two are
   mechanically similar — both rewrite app-label strings across a migration history — but that spec's
   scope explicitly excludes `webhooks`. Land them as separate, separately-reviewable changes so a
   structure-review gate can diff each against `docs/app_structure.md` independently.

2. **Timestamps go on a standalone `TimestampedModel` mixin, not on `SiteAwareModel`.** Folding them
   into `SiteAwareModel` would miss the two models with the least coverage today: `accounts.User`
   (subclasses the lower `SiteAwareModelBase`) and `SystemRoleAssignment` (a plain `models.Model`,
   deliberately not site-aware). The mixin decision must land *before* the per-model additions, or
   the same models get touched twice.

3. **No snapshot column on `QuestionAnswer`.** The deletion research recommended freezing
   `question_text` and `selected_option_texts` at answer time, on the grounds that it is
   unbackfillable and is the only thing that survives the M2M gap. On review the urgency argument
   does not hold: the real gate is "before the first learner answer exists", which is deploy time,
   not today — so nothing is lost by leaving it to `content_snapshots` or to a future authoring cut.
   And preserving historical answer text is a *feature*, with an owner already, not database
   structure. It is recorded here as a note for those specs, not built.

   The underlying gap is real and should be written down where those specs will find it: **Django
   exposes no `on_delete` lever on the auto-generated M2M through table** for
   `QuestionAnswer.selected_options`, so deleting a single `QuestionOption` silently drops the join
   row from every answer that selected it. `PROTECT` on `QuestionAnswer.question` does not close
   that. The cheaper fix is probably to stop content being hard-deleted through the admin at all —
   see Open Questions.

4. **The migration reset runs last, behind a re-check gate.** Delete and regenerate, project-wide,
   once — after `learner-terminology-rename`, `learners-associated-with-organisations` and
   `better_course_progress_tracking` have all landed, because each of them changes models in the apps
   this would otherwise regenerate twice. Immediately before executing it, **re-verify that no
   downstream project has run a `migrate` it intends to keep**; if that has changed, fall back to
   ordinary forward migrations, which are always safe.

   This is a **declared, one-time exception** to `CLAUDE.md`'s "never edit existing migration files",
   and should be recorded as one. The rule guards against quietly rewriting a migration that has
   already run against real rows — which is precisely the failure this gate exists to prevent.
   Deleting and regenerating from current model state is categorically different from editing a
   migration's logic in place. That third option — hand-rewriting label strings inside existing files
   — is rejected outright: it carries the same downstream risk with none of the benefit, and produces
   files that still look historical but no longer are.

5. **Self-contained, extractable apps are a named exception to the `SiteAwareModel` convention.**
   `referral-link-tracker` will be the first app in the graph with no `site_aware_models` edge, by
   deliberate design, so it stays liftable out of FLS. There is currently no written convention
   anywhere in `docs/` about when `SiteAwareModel` should be used. Write it down *before* that app is
   built, or a future contributor — or `/fls-dev:plan_structure_review` — will read the missing edge
   as an oversight and "fix" it, silently reintroducing the coupling it was designed to avoid. The
   exception is narrow and should stay narrow.

6. **A conformance guardrail asserting every installed app's label starts with `freedom_ls_`.**
   The machinery already exists (`freedom_ls/contrib/conformance/`, and the `base/checks.py` system
   checks). Near-zero cost, and it stops this exact problem recurring in an app not yet written.

---

## Sequencing

This idea is a **sibling** of the three in-flight specs, not an umbrella over them. It assumes they
land and only adds what they miss. But the order matters:

1. [DONE] `learner-terminology-rename` first. It renamed three app labels and therefore every table
   those apps own. Anything here touching those models lands under the new names:
   `learner_management`, `learner_progress`, `learner_interface`.
2. [DONE] `learners-associated-with-organisations`, which introduced `Learner` and re-keyed every
   enrolment model onto it. Still pending: `better_course_progress_tracking`, which re-keys
   `CourseProgress` from `user` onto `Learner`, adds an `is_active` flag so a learner can hold more
   than one pass at a course, and re-scopes `TopicProgress`/`FormProgress` from the bare
   `Topic`/`Form` to the `ContentCollectionItem` that places them — do not index or add timestamps
   to models it is mid-redesign on.
3. Everything in this idea's do-now list except the migration reset.
4. **The migration reset, last**, behind the Decision 4 gate.

Two ordering hazards worth naming:

- The `collection` → `course` rename and the `RecommendedCourse` app extraction both touch the same
  model but are different kinds of change. Do the field rename on its own; a model move is a
  migration-lineage question that belongs with the reset.
- `PROTECT` on the content FKs will make `danger_content_delete` fail loudly once any learner data
  exists. It fails safe — the transaction rolls back — but the command's messaging doesn't explain
  why. Update its help text in the same change.

---

## Open questions

1. **The Django admin exposes full delete on `Form`, `FormQuestion`, `Topic`, `Course`, `CoursePart`
   and `FormPage`, which directly contradicts `docs/product/content-editing-workflow.md:19` ("There
   is no admin-side or browser-based authoring interface").** The docs and the code disagree about
   whether this surface exists. It is also the live surface the `PROTECT` recommendations defend
   against — content re-import is upsert-only and never deletes, so the admin and
   `danger_content_delete` are the only two paths that fire these cascades at all. Should this cut
   lock the admin down, or just document the surface honestly? Locking it down is arguably the
   cheaper fix for the M2M gap in Decision 3 than any schema change.

2. **Is `learner_management` the right name?** It holds cohorts, `Learner`, registrations,
   deadlines and recommendations. "Management" is a vague noun but an accurate one, and no better
   name suggests itself. Flagged rather than decided — `learner-terminology-rename` was a word swap
   and deliberately did not re-think app boundaries, so the question it left open is still open.

---

## Research

- `research_model_inventory.md` — every concrete model, with a keep/rename/move/re-relate verdict
- `research_forms_app_extraction.md` — the forms question, with the extraction costed
- `research_app_boundaries_and_labels.md` — app labels, table namespacing, dormant apps, misplaced code
- `research_field_level_hardening.md` — timestamps, PK types, GFK key types, constraints, indexes, JSONFields
- `research_deletion_semantics.md` — the full `on_delete` matrix
- `research_migration_reset_strategy.md` — squash vs rewrite vs reset, and the tripwire
- `research_roadmap_pressure.md` — what queued work implies about today's schema (ten of eleven items: nothing)
