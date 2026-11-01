# Research: best practices for per-placement due dates

Topic `best_practices`. Applied to `idea.md`. Web search results were secondary sources in places; those are flagged. Findings about FLS code come from reading `freedom_ls/deadlines/resolver.py` (`_defaults_by_course`).

## 1. Layered configuration and override precedence

- **Nearest, most specific scope wins; absence falls through.** Hugo's front matter `cascade` passes values down to descendants "unless overwritten by self or a closer ancestor's cascade"; a page's own value beats the section's, which beats the site's. Cascade can also be targeted at a subset of descendants with `_target` (path, kind). Source: https://discourse.gohugo.io/t/is-there-an-elegant-way-to-dynamically-include-a-pages-type-and-or-layout-in-a-params-lookup/47385 and https://gohugo-cn.onrender.com/content-management/front-matter (the second is a mirror of older docs; confirm on gohugo.io).
- **Applied.** The idea's order is: staff overrides (existing layers) > placement value > child file value > nothing. Hugo's model places the most specific author scope on top. FLS's twist is that the placement, which is the more specific scope, beats the child file, and staff layers sit above both. Keep the layers as an ordered list of (source, value) so the resolver stays a "first layer that has a value wins" fold. That keeps staff-over-content unchanged and adds one layer.
- **Per-field versus per-bundle fall-through (decide in the spec).** Hugo and Kustomize merge key by key. The deadline value is a bundle (`due_date`, `due_time`, `due_days_after_registration`), and the three fields interact: `due_time` means nothing without `due_date`, and fixed versus relative are mutually exclusive. Recommended: a placement value replaces the child file's value as a whole bundle, so a placement of `due_days_after_registration: 7` cannot inherit the file's `due_date` and produce an invalid mix. Document this as a deliberate departure from key-wise merge.
- **Explicit "no deadline here" needs a representation.** The motivating case is a part with dates in one course and none in the other. If a placement can only add a value, the file's dates leak into the "none" course. Cascade systems handle this with an explicit null or empty value (Hugo and Kustomize can both blank a key). Decide how an entry says "no due date, ignore the file's" versus "no opinion". Suggested: key absent means no opinion; an explicit empty or `null` bundle means none. This needs a tri-state in storage as well (see section 3). Hugo/Kustomize treatment of null is from general knowledge, not verified here.

## 2. Content-as-code: shared modules parameterised per reference

- **Kustomize** keeps the base untouched and puts the per-use change in the referencing overlay, via patches that name a target; list entries need a stable key (`name`) or the patch appends duplicates instead of merging. Sources (secondary): https://www.golinuxcloud.com/kubernetes-kustomize/ , https://docs.opencenter.cloud/docs/reference/ref-kustomize , https://github.com/konrad945/kustomize/blob/master/examples/inlinePatch.md . Lessons:
  - The shared thing (part, topic) stays unchanged; the parent's reference carries the parameters. This matches the idea.
  - Address inner items by a stable key. The idea uses the item's path relative to the part, which is a good stable key. Do not use list position.
  - Make a patch that matches nothing an error. Kustomize patches with a missing target are a known source of silent no-ops; the idea already says to fail the load.
- **Hugo cascade `_target`** is the same pattern from the static-site side: a parent applies values to a path-selected subset of descendants.
- **Moodle** has no per-placement dates: an activity belongs to one course, "expected completion" is set on the activity, and reuse is by copying the course and re-dating through the Dates report. Sources: https://www.monash.edu/learning-teaching/teachhq/moodle/moodle-setup/how-to/use-the-moodle-dates-report , https://moodle.org/mod/forum/discuss.php?d=447897 (relative dates requested but not built in). That copy-then-redate workflow is the pain this spec removes. It also shows why a date on the shared object cannot be the answer.
- **Applied schema shape.** Keep `Child` as `{path, due_date?, due_time?, due_days_after_registration?, items?: {<relative-path>: DueDateFields}}`. Reuse `DueDateFields` for validation so a placement entry and a child file validate identically. Reject unknown keys (`extra="forbid"`), since a typo like `due_dat` silently doing nothing is the main hazard of a free-form `overrides` dict. This supports retiring `overrides`, which nothing but the admin reads, in favour of first-class keys. If kept, do not put due fields in it.
- **Shorthand for "all items of the part".** Established tools offer a wildcard or target selector (Hugo `_target`, Kustomize target selectors). It is cheap to add if it is one extra key on the part placement, but the idea says do not build unrequested features. Recommended: named items only unless the spec owner asks, and record it as open.

## 3. Storing per-placement settings and constant read query counts

- **Guidance: columns for fixed-shape, queryable data; JSON for sparse, evolving or variable-shape data.** Sources (blog posts and READMEs, not Django docs): https://www.dev.to/romansorin/using-djangos-jsonfield-you-probably-dont-need-it-heres-why-17ck , https://riptutorial.com/django/topic/1759/django . "If you're storing data with static keys, consider using multiple normal fields."
- **Applied to the two storage questions in the idea:**
  - **The placement's own value** (course→part or course→topic row, a `ContentCollectionItem` that exists already): use the same three `due_*` columns the row already has for the child's content default. Wait: those columns on the row currently hold the *child's file default* for rows whose parent is the collection. Check in the spec whether the course→child row's columns are already the content default for a directly placed child. If so, a directly placed child needs no new storage: the entry's value simply is what the sync writes, with the entry beating the file at write time. Only the *shared-part-item* case needs new storage. Verify this against `content_save.py` `due_date_columns`.
  - **Per-item values on a shared part** (the real open question): these are keyed by (course placement, item path) and variable in number, so they are not columns on one row.
    - *Row per (placement, item)*: a small table `PlacementItemDeadline(placement FK to the course→part ContentCollectionItem, item FK to the part's item row, due_* columns)` with a unique constraint on (placement, item). Pros: real FKs and cascading deletes, integrity enforced by the database, the three columns reuse `DueDateFields` and `DeadlineValue.from_columns`, trivially queryable by "which placements carry dates for this item", and the admin can show them. Sync is a delete-and-recreate or upsert-and-prune per placement.
    - *JSON on the placement row*: `{relative_path: {due_date, ...}}`. Pros: no new table, one write per placement. Cons: no FK integrity (an item path can go stale if the part later renames an item, and nothing flags it), harder to query, and values need re-validation on read. JSON suits an opaque pass-through; here every key is read by the resolver, so it is structured relational data.
    - Recommendation: the row-per-(placement, item) table, because the keys are known, the fields are static, and integrity matters. It also makes the tri-state ("none" vs "no opinion") expressible by row existence plus a nullable bundle or an explicit flag. JSON is acceptable only if the table is judged too heavy; then validate on write and drop stale keys on every sync.
- **Constant query count.** `_defaults_by_course` already does three queries independent of item count: course-level rows, part rows via `collection_id__in`, and time limits. Adding a placement-item table adds exactly one more query, `PlacementItemDeadline.objects.filter(placement__in=<part placement ids>)`, fetched with the part placements already loaded in `top_rows`, then grouped in Python. In the credit loop, a row from a shared part looks up `(placement_for_this_course, row.pk)` before falling back to the row's own columns. No per-item query, and no N+1 across courses. Add an assertion test (`django_assert_num_queries`, or a comparison of counts at 2 and 20 items) that the count is unchanged by item count and course count. If JSON is chosen the extra query disappears, because the value rides on `top_rows`; the trade-off is integrity, as above.
- **Gotcha in the current loop.** The loop credits one part row to every course that places the part with the same `value`. With placement values it must compute the value per (course, row), so the `value` computation moves inside the inner loop. This is the one place a shared-part bug can hide, so write a test with one part in two courses, one with a placement date and one without.

## 4. Idempotent sync where removing a key removes the value

- **Declarative reconcile, not patch-apply.** The file is the full desired state, so each sync computes the desired set of rows for the placement and makes the database equal it: upsert present entries, delete rows for absent ones, and write `NULL` to columns for absent keys. This is the approach Kubernetes `apply` and Terraform take; the rule is already in spec 1 for item columns and `time_limit_days`. (General knowledge; no source fetched.)
- **Do it per placement in a transaction**, so a failed load leaves the previous state. Resolve all names first, collect errors, then write; do not write partial results then fail.
- **Idempotence test.** Load twice and assert no change and no extra rows. Then load with a key removed and assert the value is gone. Also load with the entry's per-item mapping removed entirely and assert every row for that placement is gone.
- **Scope the delete** to the placement being synced. Rows belonging to other courses that place the same part must survive. The idea marks "pruning stale placements" out of scope, so this deletion applies only to the value rows for placements being (re)loaded.
- **Ordering.** The part's items must exist before the course's placement values resolve against them. Either load parts first (the part's own sync runs before the course's) or resolve lazily at the end of the load. State the order in the spec.

## 5. Validating references by path and failing loudly

- Resolve each named path against the part's actual items at load time, normalised the same way as `children:` paths (relative to the part, same slash and extension rules as the existing unknown-child check). Reuse the existing unknown-child error path and message style, so authors see one consistent failure.
- **Fail the whole load, listing all bad paths** (collect, then raise once), rather than stopping at the first. Name the course, the part and the path in the message so an author can find the line. Kustomize's lesson, that a patch with no match must be an error, not a no-op (see section 2), is the reason.
- Reject duplicates (the same item named twice, or one path matching two items after normalisation).
- Reject a placement value on a child kind that cannot carry a date (`ACTIVITY`, `ARTICLE`, per the out-of-scope list) at schema validation time. Do not rely on the resolver ignoring it.
- Reject a part placement that sets a bundle on the part itself (the part is a container and carries no value), unless the shorthand is adopted.
- Run the same schema in the author plugin's validator so errors surface before a load; the idea already requires rewriting `course-files.md`, `topic-files.md`, `form-files.md` and the plugin's validator schema. Per CLAUDE.md the plugin knowledge lives in `fls-content`, not the generic plugins.

## 6. Showing "which value applies and where it came from" in an admin UI

- **Show the winning layer's name next to the value, plus the layers below it.** Familiar patterns: Django Waffle-style "source" columns, GitLab and GitHub inherited settings that show "inherited from <group>", and the Terraform plan's "known after apply" annotations. The Moodle dates report lists dates per activity but not provenance. (General knowledge, no source fetched.)
- **Applied.** The existing override inlines' "Content default" column should show the placement value when set and label the source: "from this course's placement" versus "from the topic's file". The idea names the column but not the label; add the source label, because without it an educator who sees a date differing from the topic file will think the data is wrong. Resolver layers are already (source, value) pairs (`_layer(source, row)` with `DeadlineSource`), so add a `DeadlineSource` member for the placement, say `PLACEMENT`, and the admin renders `source.label` for free.
- **"Default has changed" comparison.** Staff overrides presumably snapshot the content default at the time they were made. That snapshot must be taken from the *effective* content default (placement beats file), so a moved placement value is detected. Test the cases: file default moved while a placement value masks it (should not report a change), placement value moved (should), placement value removed so the file shows through (should, because the effective default changed).
- Show the placement value on the read side of the same row in the content admin so authors can see it on the course→part row, read-only (content is code; the file is the source of truth, and an admin edit would be overwritten at the next sync). Mark it read-only to avoid the lost-edit trap.

## 7. Recommendations for the open questions

| Open question | Recommendation |
|---|---|
| Storage of per-item values | Row per (placement, item) table with unique constraint and the three `due_*` columns. Plus one batched query in the resolver. |
| `overrides` repurposed or retired | Retire for due fields; first-class keys and `extra="forbid"`. Keep or remove the dict separately only if the admin needs it. |
| Shorthand for all items | Not unless requested. Named items only. |
| Placement bundle vs per-field merge | Whole-bundle replacement. Explicit empty value means "no deadline here". |
| Plugin wording | Rewrite the three docs and validator in the same change as the schema, so docs and validation never disagree. |

## Risks

- Silent leakage of the child file's date into a course meant to have none (needs the explicit-none representation).
- Credit loop in `_defaults_by_course` computing one value for all courses (fix with the per-(course, row) value).
- Stale item paths if a part renames an item; the next load of any course placing it fails loudly, which is intended, but the message must say which course.
- A part's own sync order relative to the course's.

## Sources

- https://discourse.gohugo.io/t/is-there-an-elegant-way-to-dynamically-include-a-pages-type-and-or-layout-in-a-params-lookup/47385
- https://gohugo-cn.onrender.com/content-management/front-matter
- https://www.golinuxcloud.com/kubernetes-kustomize/
- https://docs.opencenter.cloud/docs/reference/ref-kustomize
- https://github.com/konrad945/kustomize/blob/master/examples/inlinePatch.md
- https://www.dev.to/romansorin/using-djangos-jsonfield-you-probably-dont-need-it-heres-why-17ck
- https://riptutorial.com/django/topic/1759/django
- https://www.monash.edu/learning-teaching/teachhq/moodle/moodle-setup/how-to/use-the-moodle-dates-report
- https://moodle.org/mod/forum/discuss.php?d=447897

status: ok
