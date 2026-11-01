# Research: UX patterns for per-placement due dates

Scope: authoring shape in `children:`, unknown-path errors, provenance display in admin, change badges.
Web evidence was thin in places; where a source did not confirm a claim it is marked "unverified".

## What exists today (local)

- `freedom_ls/deadlines/admin.py`: inlines have a "Content default" column (`content_default_for`, `_value_text`),
  an "Effective" column, and a "Default has changed" note: `"Default has changed since this override was set
  (was X, now Y)"`, shown only when `replaced_value != beneath`. Re-stamped only when a value field changes
  (editing the reason alone does not clear it). `SOURCE_LABELS` already names layers: "Content default",
  "Cohort override", "Learner override".
- `claude_plugins/fls-content`: `topic-files.md` / `form-files.md` say "write due dates in the child file, not in
  `children:`"; `course-files.md` says a course takes no `due_date`. `validate/schema.py` has `DueDateFields`
  (due_date, due_time quoted "HH:MM", due_days_after_registration; mutually-exclusive checks with
  `{file_path}: ...` messages). These three docs and the validator are what the spec rewrites.

## 1. YAML authoring shapes

Options for a part placement naming its items' dates:

A. Inline on the entry, fields beside `path` (settled for topics/forms):
```yaml
children:
  - path: week-1/intro
    due_date: 2026-03-14
    due_time: "17:00"
  - path: shared-part
    due_days_after_registration: 14      # shorthand: every item (if allowed)
    items:                                # named items, path relative to the part
      - path: quiz-1
        due_date: 2026-03-20
```
B. Nested map keyed by relative path:
```yaml
  - path: shared-part
    items:
      quiz-1: {due_date: 2026-03-20}
      project: {due_days_after_registration: 30}
```

Trade-offs:
- A (list of `{path, ...fields}`) reuses the existing `Child` shape and `DueDateFields` unchanged, so one
  mental model and one validator at every level, and order is preserved. Costs a little more indentation.
- B is terser but a map key cannot carry duplicates silently (YAML parsers keep the last or error), and the
  value type differs from the entry type, so two schemas to document.
- Recommendation: A, recursive: a part entry's `items` is a list of the same entry shape (path relative to the
  part + due fields). One schema (`Child` with due fields), one error format.
- Shorthand "one value for every item": common in config tooling as a default plus exceptions (CSS-style
  cascade; GitHub Actions `defaults:` then per-job override; Canvas "Everyone else" base with narrower
  overrides). If allowed, define precedence explicitly: named item beats part-wide shorthand beats child file.
  Risk: a part-wide `due_date` on the part entry is easily confused with a date for the part itself, and a
  part has no date (out of scope). Safer if included: give it a distinct key name (e.g. `items_default`) or
  reject bare due fields on a part entry with a message pointing to `items`. Omitting it is the smaller,
  clearer v1; a spec can add it later.
- Reuse the mutual-exclusion rules verbatim, and keep "quote due_time" guidance in the docs since YAML reads
  `17:00` as a number.
- Provenance of removal: keep the established rule (a key deleted from the entry removes the value on next
  load), and say so in the doc as it already does for child files.

## 2. Error messages for unknown paths

Established practice: report the offending key and where it is, and offer the nearest valid names.
- Pydantic `extra="forbid"` yields `extra_forbidden` with a dotted location, but no suggestion; "did you mean"
  has to be custom (difflib), as OpenViking did: https://github.com/volcengine/OpenViking/pull/856 ;
  forbidding misplaced keys at load rather than ignoring them: https://github.com/pyobs/pyobs-core/pull/762 .
  Pydantic defaults to `extra="ignore"`, so a misspelled `due_dat` is silently dropped unless the schema forbids
  it; confirm `Child`/entry models forbid extras.
- Suggested message shape, consistent with the existing `{file_path}: ...` style:
  `course.md: children[2] (shared-part): items path "quizz-1" matches nothing in this part; did you mean "quiz-1"?
  Items in this part: quiz-1, project, week-2/reading.`
  Include: file, entry index and its path, the bad relative path, closest match(es), and the full list when
  short (cap at ~10). Collect all bad paths in one failure rather than stopping at the first (the load already
  fails as an unknown child does today). Also flag duplicates (same item named twice) and a path naming a
  non-dated type (ACTIVITY/ARTICLE) with its own message, since those are out of scope.
- Fail the whole load, not warn: a silently missing deadline is worse than a failed import.

## 3. "Which layer applies" provenance displays

Prior art:
- VS Code Settings editor: a colored bar marks a setting that differs from default, a User/Workspace scope
  toggle shows each scope's value, and `@modified` filters to explicitly set values; narrower scope overrides
  broader. https://code.visualstudio.com/docs/configure/settings . (An "also modified in" cross-scope hint
  was not confirmed by sources; unverified.)
- Chrome `chrome://policy`: each row shows a Source (Platform / Cloud / Enterprise default / Not set) and
  Status notices; docs state device-level policies take precedence by default.
  https://support.google.com/chrome/a/answer/9024365 ;
  https://chromium.googlesource.com/chromium/src/+/e57486c901b4616d7c883b10249e2a625475fcd7/components/policy/resources/webui/policy_row.ts
  (Status column details unverified).
- Canvas Assign To: a base "Everyone"/"Everyone else" box carries the course default, narrower boxes (section,
  student) carry overrides, and when several apply the latest due date wins.
  https://community.canvaslms.com/docs/DOC-2642 ; known pitfall: API `due_at` returns the "Everyone else" date
  or null, i.e. consumers of a single flattened value get the wrong layer
  https://community.canvaslms.com/t5/Known-Issues/Canvas-assignment-dueAt-iso8601-returns-the-Everyone-Else-date/ta-p/635501
  . Lesson: always show the effective value plus the layer it came from.
- GitHub: org default vs repo setting, repo change overrides org default; config file beats UI toggle
  (https://docs.github.com/en/code-security/how-tos/secure-at-scale/configure-organization-security/establish-complete-coverage/configure-global-settings).
  I found no explicit "inherited from" badge there (unverified).

Patterns to adopt in the FLS inlines:
1. Show the value and its source layer together, e.g. `2026-03-20 17:00 (from placement: Course A > Part X)`
   versus `(from file)`; the existing "Content default" column should get a source suffix or a second small
   column "Default from" with values `Placement` / `Content file` / `None`. Use plain words matching
   `SOURCE_LABELS`.
2. Order layers visibly beneath the override (override > placement > file) and put that ordering in the
   column help text or the inline description once, not per row.
3. Distinguish "no value" from "value inherited": use an explicit "none" for no deadline, not blank.
4. When the same item is placed in two courses, the admin row is per cohort/registration so the course is
   already unambiguous; state the course in the provenance text so staff can find the `children:` entry.
5. Offer a path back: name the file to edit (`course.md`, `children[n]`) in the source text; do not make the
   placement value editable in admin (it is content-owned and overwritten on sync).
6. Mark overrides that equal the layer beneath as redundant (optional, low priority).

## 4. Change-detection badges

Existing behavior is a good base: stamp `replaced_value` when an override's value is saved, compare to the
current value beneath, and display only when different. Adjustments for placement values:
- The "beneath" value must be the same function the resolver uses (placement first, then file), so a
  placement edit triggers the note and a file edit under an active placement value does not (the file value is
  no longer what applies). Test both directions.
- Wording is already clear; add the layer when it differs: `Default has changed since this override was set
  (was 2026-03-14, now 2026-03-20; now from placement)`. A switch of layer with the same date is not a change.
- Use a visual warning (yellow, text label as well as color, for accessibility) in the changed state and
  nothing otherwise; avoid a permanent "up to date" badge, which adds noise.
- Offer a list filter "Default has changed" on the override changelist (staff can find stale overrides across
  cohorts); keep scoped to the existing inlines unless asked, per "don't build what is not requested".
- Preserve the existing rule that editing only the reason does not clear the note.
- Removing the placement value (key deleted) is a change too: `now <file value or nothing>`.

## Recommendations summary

1. Author shape: list-of-entries, recursive `items:` for part placements; same `DueDateFields`; no map keyed by
   path; shorthand deferred or given a distinct key.
2. Unknown path: fail the load, list all errors, include file, entry, bad path, nearest match, valid list.
3. Admin: add provenance (Placement / Content file) to "Content default"; no editing of placement values there.
4. Change note: same stamped-compare mechanism over the placement-aware default, naming the layer on change.

status: ok
