# Query-cost analysis: "All Courses" list page

Read-only analysis to settle the design decision:

> "If displaying the progress bar on a course adds an N+1 query then DO NOT
> display it. Only display it if it is cheap."

Plus: the **"Next up: <item>"** line is being **removed** from the cards, and the
four statuses (Not registered / Registered-but-0% / In progress / Complete) must
be computed correctly and cheaply for the whole list.

All citations are to files under
`/home/sheena/workspace/lms/freedom-ls-worktrees/student-interface-all-courses-list/`.

---

## 0. The one fact that drives everything: `course.children()` is an N+1 hotspot

`Course.children()` and `CoursePart.children()` are defined as:

- `freedom_ls/content_engine/models.py:211-213` — `Course.children()` → `[item.child for item in self.items.all()]`
- `freedom_ls/content_engine/models.py:254-256` — `CoursePart.children()` → same pattern

`items` is a `GenericRelation` to `ContentCollectionItem`
(`content_engine/models.py:174-179`, `244-249`), and `item.child` is a
`GenericForeignKey` (`content_engine/models.py:281-285`).

Cost of a single `course.children()` call:

1. **1 query** to load the `ContentCollectionItem` through-rows (`self.items.all()`).
2. **1 query per `item.child` access**. There is **no** `prefetch_related` /
   `GenericPrefetch` anywhere in `student_interface/` or on these accessors
   (confirmed by grep — the only `child_items` reference is the `related_name` on
   the FK at `content_engine/models.py:282`). A plain `[item.child for item in ...]`
   list comprehension resolves each GFK lazily and individually, so it is **1 query
   per child** (Django does not auto-batch GFK in a loop without an explicit prefetch).

So for a course with `k` top-level children, `course.children()` costs roughly
`1 + k` queries. For a `CoursePart`, each `.children()` adds another `1 + (its children)`.
This is the dominant per-course cost and it is what makes the "Next up" walk expensive.

---

## 1. Current query cost of the `all_courses` view

View: `freedom_ls/student_interface/views.py:152-177`.

### 1a. Fixed (batched, O(1)) prologue

- `get_all_courses()` — `Course.objects.all()` — **1 query**
  (`student_interface/utils.py:427-429`), evaluated by `list(...)` at
  `views.py:155`.
- `get_current_courses(request.user)` (`views.py:157`) →
  `utils.py:449-478`. This calls:
  - `get_course_registrations(user)` (`utils.py:148-156`): **3 queries** — the
    `UserCourseRegistration` `values_list`, the `CohortCourseRegistration`
    `values_list`, and the final `Course.objects.filter(Q | Q).distinct()`.
  - **1 query** for `CourseProgress.objects.filter(user=, course__in=all_registered).select_related("course")`
    (`utils.py:460-463`) — **all registered progress rows in ONE query**, mapped
    by `course_id`.

So the prologue is a constant ~5 queries regardless of how many courses exist.
`progress_by_id` and `registered_ids` (`views.py:158-159`) are built from the
already-fetched `current` list — **no extra queries**.

### 1b. Per-course loop (`views.py:160-171`) — the N+1 region

For every course in the full list:

**Registered branch (`views.py:163-167`):**
- `progress_percentage` is read from the in-memory `progress_by_id` dict — **0 queries** (the bar itself is free).
- `_annotate_next_up(course, request.user)` (`views.py:167`) is the expensive part.

`_annotate_next_up` (`views.py:44-65`) → `get_course_index(user, course)`
(`utils.py:159-193`). Per registered course that costs:

1. `get_is_registered(user, course)` (`utils.py:133-145`): up to **2 queries**
   (a `UserCourseRegistration.exists()`, and if false a `CohortCourseRegistration.exists()`).
   Note this re-checks registration even though the caller already knows it — wasteful.
2. Deadlines: `get_course_deadlines(user, course)` is called per course when
   `config.DEADLINES_ACTIVE` (`utils.py:171-172`) — additional queries when deadlines are on.
3. `course.children()` (`utils.py:180`): **1 + k** queries (see §0).
4. For each child, `create_child_dict_with_flattened_index`
   (`utils.py:242-369`):
   - For a `CoursePart` it calls `content_item.children()` again
     (`utils.py:263`) → another **1 + (part children)** queries, and then a
     `get_content_status` per part-child.
   - For each `Topic`/`Form` (top-level or inside a part), when registered,
     `get_content_status` (`utils.py:49-131`) runs **1 query**: a
     `TopicProgress.filter(...).first()` (`utils.py:60-62`) or a
     `FormProgress.filter(...).order_by().first()` (`utils.py:74-78`).
     For a `Form` that is a completed QUIZ, `form_progress.passed()` reads
     `form_progress.form...` which may add a query if `form` isn't cached.
   - `_get_deadlines_for_item` calls `ContentType.objects.get_for_model(...)`
     (`utils.py:204`) — cached by Django after warm-up, so ~0 steady-state.

**Per registered course this is roughly:** `2 (is_registered) + 1 (children rows)
+ k (child GFKs) + Σ(1 + part_children) for each CoursePart + 1 per
viewable Topic/Form (get_content_status)`. Concretely, for a modest course with
~8 viewable items split across 2 parts you are looking at **~20-30 queries per
registered course**, and it scales linearly with content size and the number of
registered courses on the page.

**Unregistered branch (`views.py:168-171`):**
- `_annotate_preview_context(course, is_registered=False)` (`views.py:92-111`)
  calls `list(course.children())` (`views.py:102`): **1 + k queries per course**.
  `get_content_status` is **not** called (children are unregistered → BLOCKED
  without progress lookups), so it is cheaper than the registered branch but
  still N+1 on `course.children()` (~`1 + k` per course).

### 1c. Total

`all_courses` currently issues:

```
~5 (batched prologue)
+ Σ over registered courses on page  (~20-30 queries each, content-dependent)
+ Σ over unregistered courses on page (~1 + k each)
```

i.e. it is **strongly N+1** today. The N+1 cost is dominated by
`_annotate_next_up` → `get_course_index` (the `get_is_registered` re-check, the
recursive `course.children()`/`CoursePart.children()` GFK walks, and the
per-item `get_content_status` progress lookups), plus the
`_annotate_preview_context` → `course.children()` walk on the unregistered cards.

The same pattern drives `dashboard` (`views.py:114-149`): `_annotate_next_up`
per registered course (`views.py:123`) and `_annotate_preview_context` per
recommended/available course (`views.py:128`, `138`).

---

## 2. Is `progress_percentage` cheap to display? YES.

`CourseProgress.progress_percentage` is a **stored** `IntegerField(default=0, db_index=True)`
(`student_progress/models.py:565`). It is **pre-computed on write**, not at read
time: `update_course_progress_on_completion` (`student_progress/models.py:24-89`)
recalculates it via `calculate_course_progress_percentage`
(`student_management/utils.py:4-53`) and stores it with
`CourseProgress.objects.update_or_create(... defaults={"progress_percentage": ...})`
(`models.py:85-89`) whenever a Topic/Form is completed
(`CourseItemProgress.save`, `models.py:107-120`).

Therefore, displaying the bar requires **only reading a stored column** — no
recomputation, no `course.children()` walk at render time.

For a list of courses, **all percentages can be fetched in ONE query** and mapped
by `course_id`:

```python
progress_by_id = dict(
    CourseProgress.objects
    .filter(user=user, course__in=course_ids)
    .values_list("course_id", "progress_percentage")
)
```

`get_current_courses` already does exactly this for registered (non-completed)
courses in a single query (`utils.py:458-463`), reading
`course_progress.progress_percentage` from the in-memory dict
(`utils.py:474`). The same single query trivially extends to **completed courses
and the whole list** — just widen `course__in` and don't filter out
`completed_time`. There is **no N+1** in fetching percentages.

**Verdict on the bar itself:** showing `progress_percentage` is O(1) batched and
cheap. The expense on the current page comes entirely from `_annotate_next_up`
(and the preview `children()` walk), **not** from the progress bar.

---

## 3. Minimal-query recipe for all four statuses + progress for the whole list

Goal statuses, per course:
- **Not registered** — course not in the registered set.
- **Registered but 0%** — registered, `progress_percentage == 0` (and not completed).
- **In progress** — registered, `progress_percentage > 0`, `completed_time is None`.
- **Complete** — registered, `completed_time is not None`.

These can all be derived from a **constant number of batched queries**, independent
of the number of courses:

1. **All courses** — `Course.objects.all()` → **1 query**
   (`get_all_courses`, `utils.py:427-429`).
2. **Registered course id set** — `get_course_registrations(user)`
   (`utils.py:148-156`) → **3 queries** (direct regs, cohort regs, the
   `Course` fetch). If you only need the *ids* you can drop the third query and
   union the two `values_list` results → **2 queries**.
3. **One `CourseProgress` query for the whole registered set**, selecting the
   three fields that decide everything:

   ```python
   progress_rows = {
       cp["course_id"]: cp
       for cp in CourseProgress.objects
           .filter(user=user, course__in=registered_ids)
           .values("course_id", "progress_percentage", "completed_time")
   }
   ```
   → **1 query**.

Then classify each course in pure Python (no further queries):

```python
for course in all_courses:
    if course.id not in registered_ids:
        status = NOT_REGISTERED
        continue
    row = progress_rows.get(course.id)
    if row and row["completed_time"] is not None:
        status = COMPLETE
    elif row and row["progress_percentage"] > 0:
        status = IN_PROGRESS
    else:
        status = REGISTERED_ZERO          # row missing or 0%
    pct = row["progress_percentage"] if row else 0
```

**Total: ~4-5 queries for the entire page** (all courses + registrations +
one progress query), yielding all four statuses *and* the progress percentage for
every course, with **zero per-course queries**.

Note: a course can be registered with **no** `CourseProgress` row (the model
docstring at `student_progress/models.py:547-554` notes rows exist only after
explicit registration; in practice `register_for_course` does not create one —
`views.py:240-256` only creates a `UserCourseRegistration`). The recipe handles
this: a missing row → 0% → "Registered but 0%". Good.

---

## 4. What does removing "Next up" save?

Removing `_annotate_next_up` from the per-course loop (`views.py:167`, and the
dashboard at `views.py:123`) eliminates the entire `get_course_index` walk per
course, which is where the bulk of the N+1 lives:

- the `get_is_registered` re-check (~2 queries/course),
- the per-course (and per-CoursePart) `course.children()` GFK walks (`1 + k` each),
- the per-item `get_content_status` `TopicProgress`/`FormProgress` lookups
  (1 each),
- the per-course `get_course_deadlines` call when deadlines are active.

That is the dominant cost on the page. Dropping "Next up" turns each **registered**
card from ~20-30 queries down to **0 extra queries** (the bar reads from the
batched `progress_by_id` dict). The remaining N+1 on the page would then be the
**unregistered** cards' `_annotate_preview_context` → `course.children()`
(`views.py:171` → `views.py:102`), ~`1 + k` per unregistered course — only
relevant if those cards still need preview child titles. If the redesigned card
no longer embeds the preview child list, that walk can be dropped too, making the
whole page O(1) batched.

---

## 5. Existing query-count tests

Grep for `assertNumQueries` / `django_assert_num_queries` / `CaptureQueriesContext`
across `freedom_ls/`:

- `freedom_ls/site_aware_models/tests/test_get_cached_site.py:74,83` — uses
  `django_assert_num_queries(0)` (site cache test; unrelated to this page).
- `freedom_ls/webhooks/tests/test_admin.py:69` — only a **comment** mentioning
  `assertNumQueries`; no actual assertion.

**There are no query-count assertions guarding `all_courses`, `dashboard`,
`get_course_index`, or `course.children()`.** A regression test
(`django_assert_num_queries`) around `all_courses` would be worth adding alongside
the redesign to lock in the batched behaviour.

---

## VERDICT

**Showing the progress bar on the all-courses list is CHEAP and does NOT cause
N+1**, provided it is implemented from the **stored** `CourseProgress.progress_percentage`
column fetched in a single batched query (`CourseProgress.objects.filter(user=,
course__in=...)` mapped by `course_id`), exactly as `get_current_courses` already
does (`utils.py:458-463`). The bar is a column read; it triggers no
`course.children()` walk and no per-course progress recomputation.

The N+1 on the current page comes from **`_annotate_next_up` → `get_course_index`**
(re-checked registration, recursive `course.children()` GFK walks, per-item
`get_content_status` lookups) and, for unregistered cards,
`_annotate_preview_context` → `course.children()` — **not** from the progress bar.

**Recommended implementation:** remove "Next up" (drop `_annotate_next_up`), and
compute all four statuses + progress for the whole list from ~4-5 batched queries
(all courses + registrations + one `CourseProgress` query). This satisfies the
product owner's constraint: keep the progress bar, because it is cheap.
