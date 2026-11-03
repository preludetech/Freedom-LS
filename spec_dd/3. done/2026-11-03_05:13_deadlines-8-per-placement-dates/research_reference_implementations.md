# Research: how reference implementations solve per-placement due dates

Question: the same content (topic, form, part) is placed in several courses with different dates.
Where does the per-placement value live, how does it rank against defaults and per-learner
overrides, and how is it authored? Sources are web search summaries; confidence is noted where thin.

## Summary table

| System | Per-placement value stored | Precedence | Authoring |
|---|---|---|---|
| Open edX relative dates | On the course's own subsection (graded only, self-paced only); default pacing spreads dates when empty | Custom "due in" beats default pacing; offset counts from enrolment or course start, whichever is later | "Due In" box in subsection settings (feature flags) |
| Open edX library v2 (upstream/downstream) | The course holds its own downstream copy of the block; `downstream_customized` lists locally edited fields | Customised fields survive upstream sync, others are overwritten | Edit in course, sync from library |
| Canvas Blueprint | Each associated course holds its own copy of the assignment, with its own due date | Per object, a lock on "due dates" makes the parent win on sync; unlocked and locally changed dates are left alone | Lock toggles on the blueprint, edit dates in each child course |
| Canvas overrides | Assignment override rows (assign to section, group or student) on top of the assignment's due date | Most specific override wins over "Everyone" | Assign To box |
| Moodle | Date lives on the activity instance inside one course; reuse is by copy (backup/restore, import) | Course start date shifts all dates on restore ("roll dates"); not all activity types shift | Edit per course, Dates report |
| Brightspace | Date on the item in each course copy; special access rows per learner | Special access inherits from the parent item's dates, then the course default | Offset dates at copy, Manage Dates bulk tool |
| Blackboard Ultra | Date on the item in each course copy | Copy keeps dates; shifted by a start date or Batch Edit | Course copy start date, Batch Edit |
| Hugo cascade | `cascade` block in an ancestor's front matter, with `target` selecting pages | Page's own value beats cascade; nearest ancestor cascade beats a farther one | Front matter at the section |
| Kustomize | Patches in the overlay, base untouched | Patches applied in the order listed; overlay wins over base | Overlay `kustomization.yaml` with `patches` |
| Kajabi / Teachable | Not researched | n/a | n/a |

## Findings by system

### Open edX
- Relative dates (personalized learner schedules) work only in self-paced courses, on graded
  subsections. A subsection without a custom value inherits default pacing, which spreads dates
  evenly. The offset runs from the learner's enrolment or the course start, whichever is later.
  Switching pacing mode keeps the stored dates. Sources:
  https://docs.openedx.org/en/open-release-sumac.master/educators/references/setting_course_pacing.html ,
  https://docs.openedx.org/en/ulmo/educators/how-tos/course_development/set_course_pacing.html ,
  https://discuss.openedx.org/t/request-for-feedback-personalized-course-content-schedules/1304
- Course reruns copy the course, so the date is simply a copy on the new run's block (no search
  result confirmed rerun date handling; treat as unverified).
- Library v2 and linked blocks: a course block is linked to an upstream library block. Sync
  keeps fields the author customised in the course and overwrites the rest; customised fields
  are tracked in a `downstream_customized` list and drop off it when they stop differing. The
  records say authors cannot always predict which edits survive. Nothing found on due dates in
  library blocks; in Open edX a due date sits on the course structure (subsection), not in the
  reusable block, so the library never carries it. Sources:
  https://git.andalsoftware.com/Andal.LND/edx-platform/commit/e66940094714f26d0e7da81bb2e9eabbf96a89f2 ,
  https://git.andalsoftware.com/Andal.LND/edx-platform/src/branch/master/cms/lib/xblock/upstream_sync_block.py
- Takeaway: the date belongs to the place in the course structure, not to the reusable leaf.
  That is the FLS idea's shape (date on the placement).

### Canvas
- Blueprint: each associated course has its own assignment copy. A blueprint can lock content,
  points, due dates and availability dates per object. A locked date is overwritten on sync.
  Unlocked dates a child course has changed are not overwritten by later parent changes.
  Many institutions leave due dates unlocked because sections need their own. Sources:
  https://support.wharton.upenn.edu/help/blueprint-sites-in-canvas ,
  https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-lock-course-objects-in-a-blueprint-course-as-an/ta-p/1278 ,
  https://community.canvaslms.com/t5/Canvas-Resource-Documents/Blueprint-Sync-Functionalities/ta-p/628548
- Per-learner or per-section dates are assignment overrides layered on the base due date. The
  base is the "Everyone" row.
- Takeaway: a "locked vs unlocked" flag is a Canvas answer to "who wins on resync". FLS answers it
  differently: content load rewrites the placement value every sync (spec 1 rule), so content
  always wins at the content layer and staff overrides sit above it.

### Moodle
- No shared-activity model. Reuse is backup/restore or import. Restore can "roll activity
  configuration dates" by the difference in course start dates; support is uneven by activity
  type, restricted-access dates did not shift, and a template-restore date adjustment request
  was closed as Won't Do. Sources:
  https://docs.moodle.org/310/en/Course_restore ,
  https://lanecc.helpjuice.com/moodle-faculty-course-management/automatically-shift-all-due-dates ,
  https://tracker-old.moodle.org/browse/MDL-31104 ,
  https://tracker-old.moodle.org/browse/MDL-66129
- Takeaway: copy-and-shift gives per-course dates but loses the link to the source. Dates are
  fixed at copy time and drift.

### Brightspace
- Course copy has an offset-dates option, and Manage Dates does bulk offsets after the copy.
  Special access (per-learner) rows inherit date properties from the parent item when it has
  them, else from the course default. Special access and section-based release conditions are
  reportedly not copied. Sources:
  https://wur-lecturer.screenstepslive.com/m/brightspace_manuals_lecturers/l/1184060-offset-dates-in-a-course-copy ,
  https://www.pcc.edu/online/faculty/technical/manage-dates/ ,
  https://community.d2l.com/brightspace/kb/articles/4995-set-release-conditions-for-an-assignment
- Takeaway: the layer order item date, then per-learner special access matches FLS's
  content default then staff override.

### Blackboard Ultra
- Course copy keeps dates and release conditions; a new start date shifts due dates,
  availability dates and date-based release conditions by the same pattern. Batch Edit
  adjusts dates after copy. Sources:
  https://blackboard.niu.edu/blackboard/course-migration/dates.shtml ,
  https://uas.alaska.edu/celt/knowledge-base/course-copy-ultra.html

### Kajabi / Teachable
- Not researched (search did not reach them). Both treat a lesson as belonging to one
  course/product, so the question mostly does not arise; drip is a per-course setting.
  Unverified.

### Content-as-code
- Hugo cascade: an ancestor's `cascade` sets front-matter values for descendants, and
  `target` (path glob, kind, environment) narrows it. A page that defines the field itself is
  not overridden, and a closer ancestor's cascade beats a farther one. Cascade is a
  provider-side default, not a per-include argument. Source: https://gohugo.io/configuration/cascade
  and https://github.com/gohugoio/hugo/issues/6041
- Kustomize: the base stays unchanged; each overlay lists `patches` that target resources by
  kind/name (or selector), applied in listed order. This is the closest match to "a part placement
  names items by path relative to the part and gives each a value": the patch addresses a
  resource by path, and an unmatched target is an error. Source:
  https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/patches
- Jekyll includes pass parameters per include (`{% include x.html p=1 %}`); not searched, from
  general knowledge, unverified. The parameter wins over any default inside the include.

## Patterns relevant to the open questions

1. Storage: the systems that truly share content (Open edX libraries, Canvas Blueprint) end up
   with the date on the consumer's copy or on the course structure, never on the shared leaf.
   Copy-based systems (Moodle, Brightspace, Blackboard) store a per-course copy. FLS shares rows,
   so the value must sit on a per-(course, placement) record. No system stores per-placement
   values inside the shared definition.
2. Precedence is consistently most specific wins: per-learner/section override over item date
   over default/pacing. Placement value slotting between the child file and staff overrides is
   consistent with Brightspace (special access over item) and Canvas (override over base).
3. Resync: Canvas needs lock flags and Open edX needs a `downstream_customized` list because
   edits live in the same field as synced values. FLS avoids this by keeping the placement value
   in its own column/record, rewritten from the files each load, with staff overrides in a
   separate table. No tracking list is needed.
4. Authoring by path: Kustomize patches and Hugo `cascade.target` show the accepted pattern of
   addressing items by path from the including side, and failing on a target that matches
   nothing (Kustomize does). Hugo's silent no-match is the cautionary case.
5. Shorthand "one value for all items": Hugo cascade is exactly that (applies to a whole subtree
   unless a descendant sets it). A part-wide value with per-item exceptions follows that
   precedent: item-named value beats part-wide value beats child file.
6. Relative vs fixed: Open edX relative dates apply only where the subsection is graded and the
   course self-paced; offsets count from the later of enrolment and course start. Useful
   precedent for `due_days_after_registration` being a placement-level choice too.

status: ok
