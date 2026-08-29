---
name: reference-half-nulled-deadline-contenttype
description: Producing "content_type IS NULL but object_id populated" deadline rows by deleting a ContentType — why the Topic ContentType must never be the one you delete, and the Activity-as-decoy-target trick
metadata:
  type: reference
---

# Half-nulling a deadline row (QA test 5.3, `final_pre_deploy_db_structure_cleanup`)

The ask: a deadline row whose `content_type` FK has been nulled by deleting the
`ContentType` it pointed at, while `object_id` stays populated. All three deadline
models declare `content_type = FK(ContentType, on_delete=SET_NULL, null=True)`
(`freedom_ls/learner_management/models.py`), so deleting the ContentType really does
produce that state. The rows are NOT cascaded away.

## THE TRAP — `ContentCollectionItem` FKs to ContentType are CASCADE

```
freedom_ls_content_engine.ContentCollectionItem.collection_type  on_delete=CASCADE
freedom_ls_content_engine.ContentCollectionItem.child_type       on_delete=CASCADE
```

So deleting the **Topic** ContentType (the obvious choice — most item-scoped deadlines
point at it) deletes **21 ContentCollectionItem rows**: every topic falls out of every
course and course-part. Every course TOC, the player, and all progress QA are destroyed.
Same shape for `form_engine.form` (5 items = every quiz) and `content_engine.coursepart`
(10 items). NEVER delete those three to make a half-nulled row.

Measured blast radius on the Aug 2026 DemoDev DB:

| ContentType | Permission (CASCADE) | ContentCollectionItem (CASCADE) | deadline rows (SET_NULL) | LogEntry (SET_NULL) |
|---|---|---|---|---|
| `content_engine.topic` | 4 | **21** | 2 CohortDeadline + 3 LearnerDeadline | 1 |
| `content_engine.coursepart` | 4 | **10** | 0 | 0 |
| `form_engine.form` | 4 | **5** | 1 LearnerDeadline | 0 |
| `form_engine.formpage` | 4 | 0 | 0 | 0 |
| **`content_engine.activity`** | 4 (unheld) | **0** | 0 | 0 |

## The answer — `Activity` as a decoy target

`Activity` is a first-class registered content type (`SchemaContentTypes.ACTIVITY`,
`ActivityFactory` exists) but the dev DB has **zero** Activity rows, so **nothing**
points at its ContentType. Create one Activity, deliberately leave it OUT of every
course (do NOT create a `ContentCollectionItem` for it — that row would itself
CASCADE-delete and would change a real course's TOC), scope one deadline on each of
the three models to it, then delete the `activity` ContentType. Total collateral:
1 ContentType + 4 unheld `auth.Permission` rows. Nothing else in the DB.

`formpage` is an equally narrow alternative (also 0 non-permission holders) but a
FormPage is not a course item, so Activity is the semantically honest target.

Always check permission holders before deleting a ContentType: `Permission.content_type`
is CASCADE and guardian's `UserObjectPermission.permission` cascades off that, so a held
permission silently takes object-level grants with it. The command refuses if any of the
four permissions is held by a user or group.

## Command

`freedom_ls/qa_helpers/management/commands/qa_create_half_nulled_deadlines.py`
(djclick, positional `SITE_NAME` defaulting to `DemoDev`, idempotent).

```
uv run python manage.py qa_create_half_nulled_deadlines DemoDev                        # seed only
uv run python manage.py qa_create_half_nulled_deadlines DemoDev --delete-content-type  # seed + half-null
```

Seeds the Activity (`qa-half-nulled-deadline-target`) plus one item-scoped
`CohortDeadline` / `LearnerDeadline` / `LearnerCohortDeadlineOverride`, prints the full
blast radius, then deletes the ContentType and re-reads each row to prove it survived
with `content_type_id=None`. Its `_describe_holders()` helper (walk `apps.get_models()`
for FKs whose `related_model is ContentType`, print `on_delete.__name__` + row count) is
the reusable way to size ANY ContentType deletion.

Defaults: cohort `QA Progress Demo Cohort`, course `functionality-demo-course-parts`,
`demodev_s1@email.com` for the LearnerDeadline, `qa-eve.middle@example.com` for the
override (that pair already had a whole-course override, so the cohort membership that
`LearnerCohortDeadlineOverride.clean()` demands is known to exist).

## What the half-nulled rows do to the app (verified, no browser breakage)

- Course-level fallbacks in `deadline_utils` filter `content_type__isnull=True,
  object_id__isnull=True` — **both** null — so a half-nulled row is never mistaken for
  a course-level deadline. Resolution is unchanged.
- `get_course_deadlines()` still emits a junk `(None, <object_id>)` key in its map. The
  TOC only ever does `.get((ct_id, item.pk))` for real items, so the key is dead weight,
  not a render bug.
- `__str__` is safe: a GenericFK with a null content_type returns None, so the row prints
  as "... - Whole course".
- Smoke-tested 200s: learner course detail + player for both learners, and all three
  deadline admin changelists **and** change forms.

## TRAP — re-running the command resurrects the ContentType

`ContentType.objects.get_for_model()` is a **get_or_create**. Calling the command a
second time "to check it is idempotent" therefore re-created the `activity` ContentType
with a new id (55) and seeded three fresh item-scoped rows alongside the half-nulled ones.
Caught and cleaned up the same day; the command now checks for
`content_type__isnull=True, object_id=<target pk>` on all three models and returns early
**before** `get_for_model` is ever called. Note the resurrection brings back only the
ContentType row, not its four Permissions — `create_permissions` runs on `post_migrate`.

Generalise: any command whose whole point is a *deleted* ContentType must probe with
`ContentType.objects.filter(app_label=..., model=...)`, never `get_for_model`.

## Re-creation caveat

`ContentType.objects.get_for_model()` is a get_or_create and `post_migrate` runs
`create_contenttypes`, so the `activity` ContentType comes back (with a **new** id) after
any `manage.py migrate`. The half-nulled rows stay `content_type_id=NULL` regardless —
nothing rewrites them — so the fixture survives; only the row's absence does not.

## Follow-on ask: "isolate the half-nulled row" (Aug 2026)

The seeding command leaves each half-nulled row sharing its registration with a genuine
course-level row (`content_type IS NULL` **and** `object_id IS NULL`) — because
`qa_create_soft_deadline` / `qa_create_learner_deadlines` / `qa_create_deadline_overrides`
had already put one there. All three `clean()` methods key on **`content_type__isnull=True`
alone** and never look at `object_id`:

```python
existing = CohortDeadline.objects.filter(
    cohort_course_registration=...,
    content_type__isnull=True,      # <- object_id is NOT part of the filter
).exclude(pk=self.pk)
```

So the genuine course-level row makes the half-nulled row **unsaveable for an unrelated
reason**, masking the behaviour test 5.3 is actually trying to exercise. The fix is to delete
the genuine both-NULL row on that registration, leaving the half-nulled row as the only
`content_type IS NULL` row there.

Deleted for that pass (DemoDev): `CohortDeadline a1b471b0`, `LearnerDeadline c9d32486`,
`LearnerCohortDeadlineOverride 7d3b6223` — all three both-NULL, all on
reg `c088aae3`/`84937d8b`. Survivors: 4 / 7 / 1.

**Nothing FKs to any of the three deadline models** (verified by walking `apps.get_models()`),
and there are no `pre_delete`/`post_delete` receivers on them — the only ones in the tree are
`reports.GeneratedReport` and a comment in `learner_progress/signals.py`. So each delete is
exactly 1 row, zero cascade. This is the cheapest delete in the deadline area.

### Guard the delete on shape, not just pk

A QA plan naming rows by pk is still worth re-deriving. Assert before deleting:

```python
assert row.content_type_id is None and row.object_id is None
```

That distinguishes the genuine course-level row from the half-nulled one, which is the whole
point — the two are indistinguishable in `__str__` (**both** print "... - Whole course",
because a GenericFK with a null `content_type` returns None regardless of `object_id`). Never
identify these rows by their `str()` in a changelist; read `object_id`.

### Proving the isolation worked

Rolled-back `full_clean()` + `save()` on each half-nulled row (passes now), plus a **negative
control**: re-insert a decoy both-NULL row in the same rolled-back transaction and confirm the
half-nulled row goes back to raising "A course-level deadline already exists for this cohort
registration." The negative control reproduces the tester's original symptom, which is what
proves the diagnosis rather than just the absence of an error.
