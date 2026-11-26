# Research: best practices for retiring removed content

Scope: soft-retiring content rows with a nullable `retired_at`, keeping them out of every learner-facing read, keeping audit data whole, mark-and-sweep inside one transaction, and un-retire on return. Sources are cited inline. Items marked "(inference)" are my judgement, not from a source.

## 1. Default manager vs explicit querysets

**Source facts**
- Django docs: `_base_manager` is used for forward related access (`answer.question`). Django must be able to fetch the related object even if the default manager would hide it. Base managers are not used when querying across relationships (`filter(question__x=...)`) or for reverse and many-to-many access. The docs warn not to filter in a base manager's `get_queryset()`, because forward access to a hidden row would then fail. https://docs.djangoproject.com/en/5.2/topics/db/managers/
- django-safedelete makes `objects` hide soft-deleted rows, with `all_objects` and `deleted_objects` as escape hatches. Related managers cannot reach those named managers. https://django-safedelete.readthedocs.io/en/latest/models.html and https://django-safedelete.readthedocs.io/en/1.1.2/managers.html

**Implications for this spec**
1. Do not filter retired rows in the base manager. A `FormProgress.form`, `QuestionAnswer.question` or `TopicProgress.topic` that points at a retired row must still resolve for audit and educator views. This is the main reason a hiding default manager is risky here.
2. Changing the default manager (`objects`) is a middle option. It hides retired rows from `Model.objects.filter(...)`, but it does not cover cross-relation filters (`Form.objects.filter(formpage__formcontent__...)`), `select_related`/`prefetch_related` traversals, or reverse related managers. Reverse related managers are built from the default manager class, so they would be filtered, which may be wanted for learner reads and unwanted for audit reads. (inference, from the docs above)
3. The site-aware manager already exists in FLS, so a second hiding layer would stack on it. The safest pattern is an explicit, composable queryset method (for example `.live()` or `.not_retired()`) applied at each learner-facing read. A default hiding manager would trade unseen leaks for hidden surprises in audit and educator code. (inference)
4. Prefer an opt-out-by-name design that fails loudly. Keep `objects` unfiltered, add `.live()`, and add a test that walks every learner-facing view and asserts a retired row cannot appear. A leak test per surface beats trusting a manager.
5. Prefetch and related-manager leakage is the largest pitfall. `prefetch_related("children")` or `course.topics.all()` returns retired children unless the filter is passed through `Prefetch("rel", queryset=Child.objects.live())` (with `to_attr` if both views are needed). Filter joins also need the condition, for example `filter(formpage__retired_at__isnull=True)` for every hop of the tree. A retired parent does not by itself hide its children in SQL, so the sweep must retire the children or every read must check ancestors. (inference)
6. Retire the descendants explicitly in the sweep rather than inferring from the parent. The sweep marks any row whose uuid is absent. A removed `FormPage` file normally removes its questions too. If a parent is retired but a child is still present in the source (moved elsewhere), the child's own `parent` FK decides. Add a read-side check on the ancestor chain only where a child can outlive a retired parent. (inference)
7. Retired is a hard filter applied before any shuffle, draw or count. The idea states this. Make the filter part of the one function that loads the question tree, so the shuffle and the pool code cannot bypass it. (inference)

## 2. Soft-delete pitfalls to check against this design

| Pitfall | Source | Relevance here |
|---|---|---|
| `unique=True` and `UniqueConstraint` also count hidden rows; use a partial constraint `condition=Q(deleted__isnull=True)` | django-safedelete docs (models page above) | Content is keyed by uuid, and upsert un-retires the same row, so no new row is created. Existing uniques (for example `(site, file_path)`, slugs inside a parent) keep counting retired rows. This is right: a returning file reuses its row. Do not make uniques partial, or a returning row could collide with a replacement. Check slug or title uniques that a replacement row with a new uuid could hit. |
| Hidden rows block cascade deletes or are masked inconsistently | https://code.djangoproject.com/ticket/2698 | Not triggered: FLS uses PROTECT and never deletes. `danger_content_delete` remains the only delete path. |
| Cascade soft-delete flags (`deleted_by_cascade`) so undelete restores only what the cascade hid | safedelete docs | Not needed. Retirement here is per-row by absence from the source, so each row retires and un-retires by its own uuid. Do not cascade. |
| `save()` silently undeletes (safedelete default) | safedelete docs | Related lesson: an ordinary `save()` during sync is exactly how un-retire should happen, but only through the sync path. Other code that saves a retired row (educator edits, admin) must not clear `retired_at` by accident. Set `retired_at` only in the sync service and make the field read-only in the admin. (inference) |
| `QuerySet.update()` and `bulk_update` skip `save()` and signals | Django behaviour | Sweep should use one `.update(retired_at=now)` per model for speed. Then do not rely on `save()` signals or `auto_now` fields for retire. If `updated_at` matters for audit, set it in the same `update()`. (inference) |
| Admin shows hidden rows or none | general | Admin uses `_default_manager`. Because `objects` stays unfiltered here, the admin shows everything. Add a `retired_at` list filter and column (as answered). |

## 3. Referential integrity and audit trail for regulated records

- Learner rows reference content with PROTECT, so the retire flag is the only safe state, as the idea says. The audit trail keeps rows whole: nothing is cascaded, nothing is nulled.
- Record "when" with the timestamp. The answers settled on no per-row audit entry and a count in the `content_save` output. Common regulated-record guidance is to keep a record of what changed and when. A count plus the per-row `retired_at` timestamp lets a reviewer reconstruct the set (`retired_at = <run time>`). Using one timestamp for the whole run (a single `now` captured once) makes that set queryable. Recommend capturing one `run_started_at` value and using it for every retire in the run. (inference)
- Retire and un-retire should be symmetrical in output: report `retired`, `un-retired` and unchanged counts per model.
- Pinning at attempt start: store which questions made up the served paper on the attempt itself (the shuffle spec's served paper), so retirement mid-attempt cannot change what the learner sees or the `max_score`. This needs the paper to be materialised per attempt, not recomputed from the live tree. Version pinning for revisions is spec 3. (inference)
- Learner data that points at retired rows stays readable in educator views. Because forward FK access uses the base manager, `answer.question` resolves for a retired question as long as the base manager is unfiltered (Django docs above).
- Progress and completion: the answers settled on excluding retired children from totals and completion. Implement the denominator and the completion check through the same `.live()` queryset so one definition serves both. A completed `CourseProgress` row recorded earlier should be recalculated, or an explicit rule should say it is not. (inference; this is an open decision for the spec)

## 4. Mark-and-sweep sync in one transaction

Sources for the pattern are general (garbage collection mark and sweep; "sync with soft-delete" in ETL practice). I found no Django-specific authority page, so treat this as design guidance.

1. Wrap the whole run in `transaction.atomic()`: upserts, un-retire and the sweep. A failure rolls back everything, so a run that aborts retires nothing (as the idea requires).
2. Mark: during upsert, collect the identifiers seen (uuid per model, `file_path` for `File`) in memory as sets. Set `retired_at=None` in the upsert itself, so un-retire is the same write as the content update.
3. Sweep: after all paths are processed, for each model `Model.objects.filter(site=site, retired_at__isnull=True).exclude(uuid__in=seen).update(retired_at=run_time)`. Scope by site, and only file-sourced rows. Rows made some other way must not be swept. Check the model's source marker. (inference)
4. Guard against an empty or partial run retiring everything. A mark-and-sweep with a bad input (empty directory, wrong path, failed parse that was swallowed) retires the whole site. Recommended guards: fail the run if a parse error occurred, and fail or require an explicit flag when the sweep would retire more than a set fraction, or when zero rows were found for a site that has existing content. This protects regulated content from a misconfiguration. (inference; spec 1 covers several paths and the git checks)
5. Large `uuid__in` lists: with thousands of uuids, use a temporary set difference in Python (fetch existing live uuids, subtract seen, update by pk chunks) or a subquery, to stay under parameter limits. PostgreSQL handles large `IN` lists, but chunking keeps it predictable. (inference)
6. Concurrency: take a lock so two saves for one site cannot interleave (an advisory lock or `select_for_update` on the Site row). Otherwise run A could sweep rows run B just added. (inference)
7. Sweep order does not matter for correctness since there are no cascades, but do the sweep after every path is processed, and after ancestors move. A row that moved to another parent keeps its uuid and is simply "seen".
8. Idempotence: a second run with the same input retires and un-retires nothing. Test this.

## 5. Un-retire on reappearance

- Same uuid returns, so the upsert sets `retired_at=None` alongside the content update. Kept learner data is live again with no further step.
- For `File` (keyed by path, no uuid), the same rule applies using `(site, file_path)`.
- Children: a returning parent does not automatically return children. Each child un-retires only if its own uuid is seen in the run. That is correct, since a child absent from the source stays retired.
- `ContentCollectionItem` is skipped on read when the child is retired and shows again when the child returns. This needs no state on the item (as answered). Implement it as a join condition on the child's `retired_at` in the outline query. Mind the generic-relation case: the child is reached through a content type, so the filter cannot be a plain FK join. Check how outline queries resolve the child; the filter may need to run in Python after the fetch or per content type. (inference)

## 6. Practical checklist for the spec

- One shared mixin or abstract field for `retired_at`, plus a queryset method `live()`/`not_retired()` and a `is_retired` property. (CLAUDE.md forbids abstract base classes unless asked, so a plain mixin, or repeating a field and a queryset method, needs a decision.)
- Do not change `_base_manager` or the default manager to filter.
- Audit every learner-facing read, including `Prefetch`, `select_related`, reverse relations, cross-relation filters, counts, shuffles and draws. Add a regression test per surface that creates a retired row and asserts it never appears.
- Tests: retire; un-retire; idempotent second run; aborted run retires nothing; learner rows untouched; attempt started before retirement keeps the question; attempts started after do not get it; completion excludes retired children; thin-pool validation error names the page.
- Read-only `retired_at` in admin; admin `list_filter` and column.
- Sync output counts per model for retired and un-retired.
- Guard against mass-retire from a bad input.

## Sources

- Django managers (base manager, default manager, warning against filtering base managers): https://docs.djangoproject.com/en/5.2/topics/db/managers/
- django-safedelete models (visibility managers, unique constraints, undelete, cascade): https://django-safedelete.readthedocs.io/en/latest/models.html
- django-safedelete managers (related managers cannot reach named managers): https://django-safedelete.readthedocs.io/en/1.1.2/managers.html
- Django ticket 2698 (default-manager filtering vs referential integrity on delete): https://code.djangoproject.com/ticket/2698
- Soft delete overview: https://dev.to/bikramjeetsingh/soft-deletes-in-django-a9j

status: ok
