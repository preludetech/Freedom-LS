# Research: Migration strategy for the student → learner app-label rename

## Summary

Django has no first-class "rename an app label" migration operation. The only reason this rename is
tractable at all is the stated premise: no live installs, dev DB rebuilt from scratch. Given that
premise, the choice is not really "rewrite vs squash" as a pure risk trade-off — it is a choice
between two strategies that **both work**, plus a subtlety the idea doc doesn't mention: two of the
existing `RunPython` migrations (`0006_validate_no_duplicate_students`,
`0008_populate_user_from_student`) hardcode **raw SQL table names built from the old app label**
(`freedom_ls_student_management_student`, etc.). If you rewrite migrations in place, those literal
strings must also be edited by hand — `dependencies`/`to=` string rewrites alone are not enough. That
is a correctness trap, not just a style question. Additionally, `squashmigrations`' `replaces`
mechanism is built to reconcile *already-applied* history for the *same* app label across deployed
databases — since nobody has ever migrated under the new label, `replaces` buys nothing here; it only
adds an extra file with a `replaces` list that will never match any real `django_migrations` rows.

**Recommendation: regenerate a fresh `0001_initial` per renamed app** (`freedom_ls_learner_management`,
`freedom_ls_learner_progress`) via `manage.py makemigrations` after deleting the old migration files,
rather than in-place string rewriting or `squashmigrations`/`replaces`. This retires the four
dead-`Student` migrations for free, sidesteps the hardcoded-table-name trap entirely, and produces the
cleanest possible history for what is, per the idea doc, "the most breaking change FLS has shipped"
anyway — a downstream consumer upgrading past this release has to do a manual cutover no matter which
option is picked (see §6). `student_interface` has zero migrations, so nothing to decide there.
This flips back toward in-place rewrite only if FLS acquires real downstream installs with applied
migrations *before* this spec ships — which the idea doc says is not the case today.

---

## 1. Options enumerated

| # | Option | Mechanics | `django_migrations` rows | Existing DB can migrate forward? | Reversible? | Interacts with label rename? |
|---|---|---|---|---|---|---|
| (a) | **In-place string rewrite** | Hand-edit every existing file: `dependencies` tuples, `to=` FK app-label prefixes, `migrations.swappable_dependency` unaffected (uses settings, not label), **and the raw-SQL table names in 0006/0008**. Keep all 15/5 files, same filenames, same operation count. | Untouched structurally — same row count, same names, just now recorded under the new label going forward (rows for the old label simply never existed if DB is fresh). | N/A here (fresh DB only) — but *would* work forward for a real downstream DB **only if** you also manually `UPDATE django_migrations SET app = 'freedom_ls_learner_management' WHERE app = 'freedom_ls_student_management'` and manually `ALTER TABLE ... RENAME` every table, because Django's loader has no concept of "this app used to be called X." | Same reversibility as today, operation-by-operation. | Every `to="freedom_ls_student_management.X"` string and the `dependencies` tuples must change; **raw SQL table-name literals in 0006/0008 are easy to miss** and will silently break a from-scratch replay if left stale (table won't exist under the new label). |
| (b) | **`squashmigrations` with `replaces`, keep old files** | Run `manage.py squashmigrations student_management 0015` (before or after the rename) producing `0016_squashed... .py` (or `--squashed-name`) with `replaces = [('freedom_ls_student_management','0001_initial'), ...]`. Old files stay. Non-`elidable` `RunPython` (0006, 0008 — neither currently sets `elidable=True`) is **kept verbatim** in the squashed file, so its raw-SQL table-name trap moves into the squashed file too, unless you first mark them `elidable=True` (0006 safely can be — it's a read-only validation; 0008 cannot be dropped silently since it's a real data copy, though moot with zero data). | Squashed migration is applied instead of the 15 originals for new installs; `django_migrations` gets one row per replaced entry is **not** what happens — Django records the row for the file that ran (squashed or individual) depending on migration state at the time. | Would let a partially-migrated downstream DB (mid-way through the old 15) keep advancing through the *old* individual files until done, then switch — but only if the `replaces` tuples still reference the **old** app label, which stops existing the moment the app config is renamed. Since nobody has ever run these migrations under `freedom_ls_student_management` outside this repo's own dev/CI, there is no real database this mechanism reconciles. | Reversible only if all elided/kept operations are reversible (RunSQL/RunPython without a reverse fn is not). | `replaces` is keyed to `(old_app_label, migration_name)` tuples that must be written *before* any label rename is finalized; **combining squash with a simultaneous label rename is exactly the scenario Django's docs don't cover** (confirmed — see §3). |
| (c) | **Squash, then delete replaced files (Django's documented 2-stage process)** | Stage 1: (b). Release/commit. Stage 2 (later, only after "all systems have upgraded"): delete the 15 replaced files, repoint any migration that depended on them to the squashed file, remove `replaces` from the squashed migration's class. | Ends with a single migration file per app, same end state as (d), but reached in two commits instead of one, and only after Django's documented "give downstream time to upgrade" waiting period. | This waiting period is the entire point of the two-stage process, and it exists to protect *downstream consumers with already-applied migrations*. FLS has none today. | Reversibility unaffected once fully squashed. | Same label-rename friction as (b) during stage 1; stage 2 is functionally identical to (d) — same output, more ceremony, and Django's own docs frame the two-stage dance as existing *specifically* to protect deployed databases that FLS does not have yet. |
| (d) | **Delete all migrations, regenerate a single fresh `0001_initial` per app** | Delete every file under `student_management/migrations/` and `student_progress/migrations/` except `__init__.py` (do this as part of the rename, i.e. inside the already-renamed `learner_management`/`learner_progress` packages). Run `manage.py makemigrations learner_management learner_progress`. Django reads current `models.py` (post-rename, `StudentDeadline`→`LearnerDeadline` already applied) and emits one `0001_initial.py` per app with correct dependencies on `freedom_ls_content_engine`, `sites`, `freedom_ls_organisations`, `contenttypes`, and the swappable user model — the same external dependencies the current final-state migrations already carry. | For a fresh DB: one row per app instead of 15+5. For any hypothetical existing DB: **breaks it outright** — `makemigrations` has no memory of the deleted-Student intermediate schema, so a real downstream DB that had actually applied the old 15 migrations would show `0001_initial` as unapplied/conflicting and Django would try to `CREATE TABLE` on tables that already exist. | No — this option is safe **only** under the "no live installs, rebuilt from scratch" premise stated in the idea doc. If that premise is wrong for even one consumer, this option corrupts their DB. | New single migration is reversible like any generated initial (its `CreateModel`s reverse to `DeleteModel`s). | Cleanest interaction with the label rename: the fresh `0001_initial` is written *for* the new label from the start, so there is no old/new label mismatch to reconcile anywhere, and the raw-SQL-table-name trap in 0006/0008 disappears because those migrations (and the `Student` model they served) never existed in the regenerated history. |
| (e) | **Hybrid: fresh initial for the renamed apps, leave all other apps untouched** | Identical to (d), scoped explicitly to `learner_management` and `learner_progress` only. `student_interface` has 0 migrations so there is nothing to regenerate there — this collapses (d) and (e) into the same action set for this repo today. | Same as (d), scoped to two apps; the other 9 apps' `django_migrations` history is completely unaffected (confirmed no cross-app dependency exists — see §2). | Same caveat as (d). | Same as (d). | Same as (d); explicitly does *not* touch `organisations`, `content_engine`, `role_based_permissions`, `accounts`, `webhooks`, etc. |

Given `student_interface` has zero migrations, in this repo **(d) and (e) are the same action**. The
real three-way choice is (a) rewrite-in-place vs. (b)/(c) squash-with-`replaces` vs. (d)/(e) fresh
regenerate.

---

## 2. Migration inventory (verified in this repo)

`student_management/migrations/` — 15 files (excluding `__init__.py`):

| File | Operations | Dead-`Student`? | Cross-app deps (verified) | Safe to squash away entirely? |
|---|---|---|---|---|
| `0001_initial.py` | `CreateModel` × 5: `Cohort`, `CohortCourseRegistration`, `RecommendedCourse`, `Student`, `CohortMembership`, `StudentCourseRegistration`; 3 `AddConstraint` | Creates it | `freedom_ls_content_engine.0001_initial`, `sites.0002_...`, swappable `AUTH_USER_MODEL` | No — this is the schema root; survives only as the *content* folded into a new `0001_initial`, not this file |
| `0002_cohortdeadline.py` | `CreateModel` `CohortDeadline` | No | `contenttypes.0002_...`, own app `0001_initial`, `sites.0002_...` | Yes — pure schema, folds cleanly |
| `0003_studentdeadline.py` | `CreateModel` `StudentDeadline` | No (survives as `LearnerDeadline` per idea §5) | `contenttypes`, own `0002`, `sites` | Yes — folds cleanly (field/model renamed elsewhere in scope) |
| `0004_studentcohortdeadlineoverride.py` | `CreateModel` `StudentCohortDeadlineOverride` | References `Student` FK, but model itself survives renamed as `UserCohortDeadlineOverride` (via `0011`) | `contenttypes`, own `0003`, `sites` | Yes — folds cleanly |
| `0005_alter_student_cellphone_alter_student_id_number.py` | 2 `AlterField` on `Student` | Yes — alters the doomed model | own `0004` | Yes — folds cleanly (net effect subsumed since `Student` is deleted in `0010`) |
| `0006_validate_no_duplicate_students.py` | `RunPython` — raw SQL `SELECT ... FROM freedom_ls_student_management_student GROUP BY user_id HAVING COUNT(*) > 1`, raises if duplicates. `reverse` is a no-op. | **Yes — pure `Student`-model dead code**, no `elidable=True` set | own `0005` | **Not safely squashable via `squashmigrations`** without first adding `elidable=True` (it's non-optimizable RunPython) — but trivially droppable entirely under (d)/(e) since it validates a model being deleted 4 migrations later and has zero purpose in a fresh install |
| `0007_cohortmembership_user_and_more.py` | 3 `AddField` (nullable `user` FK on `CohortMembership`, `StudentCohortDeadlineOverride`, `StudentCourseRegistration`) | Transitional (student→user cutover) | own `0006`, swappable `AUTH_USER_MODEL` | Yes — folds cleanly, net effect subsumed by final state |
| `0008_populate_user_from_student.py` | `RunPython` — raw SQL `UPDATE <table> SET user_id = s.user_id FROM freedom_ls_student_management_student AS s WHERE ...` for 3 tables, reverse sets `user_id = NULL` | **Yes — pure `Student`-model dead code**, no `elidable=True`, and **hardcodes the old-label table name literally**, the specific correctness trap flagged in the Summary | own `0007` | **Not safely squashable via `squashmigrations`** without care (data migration, not elidable by default); trivially droppable entirely under (d)/(e) — no data exists to copy in a fresh install |
| `0009_remove_student_fk_make_user_non_nullable.py` | `RemoveField` × 3 (`student` FK off all three models), `AlterField` × 3 (`user` non-nullable), `RemoveConstraint`/`AddConstraint` pairs renaming `unique_student_*` → `unique_user_*` | Yes — completes the student→user cutover | own `0008`, swappable `AUTH_USER_MODEL` | Yes — folds cleanly, net effect subsumed |
| `0010_delete_student.py` | `DeleteModel` `Student` | **Yes — this is the deletion itself** | own `0009` | Yes — folds cleanly (cancels with `0001`'s `CreateModel` under Django's squash optimizer, or simply never exists in a fresh regenerate) |
| `0011_rename_models.py` | `RenameModel` × 2: `StudentCourseRegistration`→`UserCourseRegistration`, `StudentCohortDeadlineOverride`→`UserCohortDeadlineOverride` | No (renames survivors) | own `0010` | Yes — folds cleanly. **This is the in-tree precedent for this exact spec**: a bare `migrations.RenameModel`, no custom SQL, no `db_table` override anywhere in the three apps so the underlying Postgres table is renamed automatically along with the model. This is the direct analog for what an equivalent `RenameModel`-based *in-place* approach to the label rename would need to imitate at the app-label level — except Django has no `RenameApp` operation, only `RenameModel`. |
| `0012_alter_usercourseregistration_collection.py` | `AlterField` (`related_name` change) | No | `freedom_ls_content_engine.0006_...`, own `0011` | Yes — folds cleanly |
| `0013_cohortmembership_unique_user_cohort_membership.py` | `AddConstraint` | No | own `0012`, `sites`, swappable `AUTH_USER_MODEL` | Yes — folds cleanly |
| `0014_cohort_organisation_and_more.py` | `AddField` × 2 (`organisation` FK on `Cohort`, `UserCourseRegistration`) | No | **`freedom_ls_organisations.0001_initial`** (new cross-app dependency, confirmed one-directional — `organisations` migrations do not reference `student_management` back), own `0013` | Yes — folds cleanly |
| `0015_remove_cohort_unique_cohort_name_per_site_and_more.py` | `RemoveConstraint` × 2, `AddConstraint` × 2 (constraints now scoped by `organisation`) | No | `freedom_ls_content_engine.0014_...`, `freedom_ls_organisations.0001_initial`, own `0014`, `sites`, swappable `AUTH_USER_MODEL` | Yes — folds cleanly |

`student_progress/migrations/` — 5 files, all pure schema, none touch `Student`:

| File | Operations | Dead-`Student`? | Cross-app deps | Safe to squash away entirely? |
|---|---|---|---|---|
| `0001_initial.py` | `CreateModel` × 4: `FormProgress`, `CourseProgress`, `QuestionAnswer`, `TopicProgress` | No | `freedom_ls_content_engine.0001_initial`, `sites`, swappable `AUTH_USER_MODEL` | No (schema root, folds into new `0001_initial`) |
| `0002_courseprogress_progress_percentage.py` | `AddField` | No | own `0001` | Yes |
| `0003_add_progress_percentage_index.py` | `AlterField` (adds `db_index`) | No | own `0002` | Yes |
| `0004_alter_questionanswer_text_answer.py` | `AlterField` | No | own `0003` | Yes |
| `0005_courseprogress_last_accessed_content_type_and_more.py` | `AddField` × 2 | No | `contenttypes.0002_...`, own `0004` | Yes |

No `RunPython`/`RunSQL` at all in `student_progress` — this app is trivially safe under any option;
the whole "which option is riskier" question is really only about `student_management`'s four dead-
`Student` migrations.

### Cross-app dependency verification (idea claims "no app outside these three depends on their labels" — VERIFIED)

`grep -r "freedom_ls_student_management\|freedom_ls_student_progress\|freedom_ls_student_interface"
freedom_ls/*/migrations/*.py` returns matches **only inside `student_management/migrations/` and
`student_progress/migrations/` themselves** (self-references via `dependencies` tuples and `to=`
FK strings). Zero matches in `accounts`, `content_engine`, `course_applications`, `course_interest`,
`organisations`, `role_based_permissions`, `webhooks`, or `educator_interface` (which has no
migrations of its own). The dependency arrow between `student_management` and `organisations` runs
**one way**: `student_management/migrations/0014_...` and `0015_...` depend on
`freedom_ls_organisations.0001_initial`; `organisations`'s own migrations do not depend back on
`student_management`. This confirms the idea doc's claim and means the rewrite/squash/regenerate
graph is fully self-contained to these two apps — no other app's migration dependency list needs
editing under any option.

---

## 3. What Django's official docs say (docs.djangoproject.com, "Migrations" → "Squashing migrations", Django 6.0)

- **Mechanics**: `squashmigrations` extracts every `Operation` from the target range, runs an
  optimizer (`CreateModel`+`DeleteModel` cancel out, `AddField` rolls into `CreateModel`, etc.), and
  writes one new file with a `replaces = [(app, name), ...]` list. Non-optimizable operations
  (`RunSQL`, `RunPython`) survive verbatim in the squashed file **unless explicitly marked
  `elidable=True`**.
- **`replaces` semantics**: it lets Django use the squashed file for fresh installs while still
  advancing a partially-migrated database through the original individual files until it catches up,
  then switching over. This is explicitly a mechanism for reconciling *already-applied history under
  the same app label* — it is not documented as covering, and does not naturally cover, a
  simultaneous app-label rename, because the old label stops being a registered app the moment the
  rename lands.
- **Documented multi-stage removal process** (the reason it exists): (1) squash, keep old files,
  release; (2) *wait until all environments — including third-party deployments not under your
  control — have applied the squashed migration*; (3) only then delete the replaced files, repoint
  any migrations that depended on them, and strip the `replaces` attribute; (4) release again. Django
  is explicit that skipping the wait risks breaking any database still mid-way through the old
  sequence — this wait period is precisely what FLS's "no live installs" premise makes moot today.
- **Django 6.0 addition**: `squashmigrations` can now squash already-squashed migrations, without
  first transitioning them to normal migrations — useful for iterative squashing when you can't be
  sure every environment has caught up yet. Not relevant here since nothing has been squashed before.
- **Circular dependencies / mis-optimization**: docs warn the optimizer can produce a
  `CircularDependencyError` on complex interdependent models, with `--no-optimize` as an escape hatch
  and manual dependency-splitting as the fix. Not triggered by anything in this repo's migrations
  (linear dependency chain, no circularity), but worth naming as a general squash risk class.
- **App/model renaming during squash**: not explicitly addressed in the docs at all — confirmed by
  this research, this repo's situation (label rename + migration-history decision, simultaneously) is
  genuinely undocumented territory, reinforcing that whichever option is chosen should be the
  simplest one that produces a *correct* end state, not the one that most closely follows a squashing
  recipe designed for a different problem (reducing file count on a live, deployed schema).

---

## 4. What other distributable Django packages do (community, not official)

- The general community consensus (Johnny Metz, "Stop Using Django's squashmigrations: There's a
  Better Way") is that `squashmigrations` is designed for exactly the case FLS does *not* have —
  environments you don't fully control that might be mid-migration. For projects/packages where you
  either control every environment or, as here, know there are zero applied-migration environments in
  existence yet, a **clean reset** (delete migration files, regenerate) is the recommended simpler
  path, with the explicit caveat that **neither approach preserves `RunPython`/`RunSQL` data
  migrations** — they must be manually re-added if their data effects are still needed. In FLS's case
  the two `RunPython` migrations being retired (0006, 0008) serve a model being deleted in the same
  breath, so nothing needs to be manually re-added.
- The `django-replace-migrations` tool (GitGuardian) formalizes "reset without faking": it generates a
  new initial migration and adds the old migration names to that new migration's `replaces` list, so
  already-migrated databases are marked as satisfied without needing `--fake`. This is a middle path
  between (a)/(b) and (d)/(e) that wasn't in the original five-option list — worth naming as **option
  (f)**: functionally like (d)/(e) (fresh initial, one file) but with a `replaces` list retrofitted so
  an already-migrated *same-label* database doesn't need faking. It still doesn't solve the
  label-rename problem specifically (the `replaces` tuples would still need to reference the old label
  the same way squashmigrations' would), so it inherits the same "not designed for a simultaneous
  label change" caveat as (b)/(c).
- Wagtail's own major-version upgrade guides mention deleting all migration files except the squashed
  ones as part of some major-version cutovers, but always paired with an explicit, published upgrade
  path telling site operators exactly what commands to run and in what order — i.e., large reusable
  Django packages that *do* reset migration history do so as a deliberate, documented, versioned
  breaking change for downstream consumers, never silently. This maps directly onto the idea doc's own
  framing: this rename is "the most breaking change FLS has shipped," and §9 (Upgrade notes) already
  commits to documenting it via `/fls-dev:update_upgrade_notes` — so whichever migration-file strategy
  is picked, it needs to show up there regardless.
- No evidence found of any of allauth/django-oscar/djangocms doing a bare, undocumented migration
  reset on a reusable app with existing downstream installs — when packages do this, it is always
  gated behind a major version bump with explicit operator instructions (commonly: "upgrade to version
  N first, let migrations settle, then upgrade to N+1 which contains the reset").

---

## 5. Recommendation

**Delete the existing migration files in `learner_management/migrations/` and
`learner_progress/migrations/` (post-rename) and regenerate a single fresh `0001_initial.py` per app
via `manage.py makemigrations`** (options d/e, which are identical here since `student_interface` has
no migrations). This is the cleanest reachable end state, it retires
`0006_validate_no_duplicate_students`, `0008_populate_user_from_student`,
`0009_remove_student_fk_make_user_non_nullable`, and `0010_delete_student` for free (their entire
purpose was servicing a `Student` model that will not exist in the codebase after this spec lands),
and it eliminates the hardcoded-old-label-table-name trap in 0006/0008 by construction rather than
requiring a careful manual edit that a reviewer has to trust was done correctly. It also avoids paying
for `squashmigrations`' `replaces` machinery, which is built to protect already-migrated databases
that do not exist for these two apps today. The trade-off: this is safe **only** because the idea
doc's premise holds — no live installs, dev DB rebuilt from scratch, zero applied migrations under
either label anywhere. **The recommendation flips to in-place rewrite (option a)** — carefully,
including the raw-SQL table-name literals in 0006/0008 — the moment that premise is false for even one
consumer (e.g. if a downstream project has already run `manage.py migrate` against
`freedom_ls_student_management` before this spec ships), because only in-place rewrite (paired with a
manual `django_migrations`/table-rename cutover script for that consumer) has any chance of carrying
forward an already-migrated database; a fresh-regenerated `0001_initial` will conflict with tables
that already exist under the old label.

**Does the choice interact with the app-label rename?** Yes, directly: the fresh-regenerate option is
*more* compatible with a simultaneous label rename than either squash variant, because it writes
`0001_initial` under the new label from the start with no old-label residue anywhere in the file
(no stale `dependencies` tuples, no stale `to=` strings, no stale raw SQL). The squash-with-`replaces`
options are the *worst* fit for a simultaneous label rename specifically, because their entire value
proposition (reconciling already-applied old-label history) is nullified the instant the old label
stops being a registered app — they'd be paying full `squashmigrations` complexity cost for a benefit
that doesn't apply here.

**Filenames stay historical, as the idea requires**: under the recommendation, `0002` through `0015`
in `student_management` and `0002`–`0005` in `student_progress` do not survive — which the idea doc
explicitly permits ("a file called `0006_validate_no_duplicate_students.py` keeps that name if it
survives at all"). Nothing in this recommendation renames a surviving migration file; it only removes
files that no longer need to exist.

---

## 6. One thing this doesn't solve, regardless of option chosen

None of options (a)–(f) make a simultaneous app-label rename safe for an *already-migrated* downstream
database — Django has no `RenameApp` migration operation, only `RenameModel` (the exact tool
`0011_rename_models.py` uses for models, and the direct in-tree precedent the idea doc cites). A real
consumer with applied `freedom_ls_student_management` migrations would need a manual, documented
cutover (rename the Postgres tables, hand-edit `django_migrations.app` rows, or a bespoke data
migration) no matter which of these options is picked for the *file* strategy. Since the idea doc
states this doesn't apply today, this is out of scope for the decision itself, but it belongs in the
upgrade notes (§9 of the idea doc) as a named risk for whoever eventually *is* the first downstream
consumer to upgrade across this release.

---

## Reference URLs

- [Migrations — Django 6.0 documentation, "Squashing migrations"](https://docs.djangoproject.com/en/6.0/topics/migrations/#squashing-migrations) — official
- [Stop Using Django's squashmigrations: There's a Better Way — Johnny Metz](https://johnnymetz.com/posts/squash-django-migrations/) — community
- [How to reset your Django migrations? — Conrad, Django Unleashed (Medium)](https://medium.com/django-unleashed/how-to-reset-your-django-migrations-3717228054a0) — community
- [Cleaning Up Your Django repo — A Holistic Approach to Managing Migration Files — Ronny Vedrilla (Beyonder)](https://medium.com/ambient-innovation/cleaning-up-your-django-repo-a-holistic-approach-to-managing-migration-files-2cbfd740d3ad) — community
- [django-replace-migrations (GitGuardian) — PyPI](https://pypi.org/project/django-replace-migrations) — community tool, option (f)
- [django-replace-migrations — GitHub](https://github.com/GitGuardian/django-replace-migrations) — community tool, option (f)
- [Upgrading Wagtail — Wagtail Documentation](https://docs.wagtail.org/en/stable/releases/upgrading.html) — community/package precedent

---

status: ok
