# Research: reference implementations for retiring content removed from the source

Date: 2026-11-24. Adds to `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md` (prior art), which already covers: Moodle hides an in-use question instead of deleting it; Questionmark retire keeps items referenceable; Canvas copy-on-edit; Open edX overwrite-in-place; every surveyed import is additive (never prunes). Not repeated here beyond what is needed.

Labels: (a) stated in a source read, (b) forum or secondary claim, (c) my inference, (?) not found.

## 1. What the survey adds

### 1.1 Moodle: "delete" on an in-use question becomes hide
- (a/b) The dev tracker ticket MDL-76757 gives the confirmation text: questions that cannot be deleted because they are in use "will be hidden in the question bank unless you select 'Show old questions'". https://tracker-old.moodle.org/browse/MDL-76757
- (b) A forum answer says deleting an in-use question just makes it hidden, with a restore button that unhides it. https://moodle.org/mod/forum/discuss.php?d=87799 (and the question bank docs https://docs.moodle.org/405/en/Question_bank)
- (b) Quiz attempts keep referencing the hidden question; staff recovered who got the deleted question from the attempt-state tables.
- (b) Hidden is a separate flag from delete: hidden questions are still exported by Moodle XML export (MDL-82875, https://tracker-old.moodle.org/browse/MDL-82875). Lesson for FLS: decide for every read path (export, reports) whether retired is in or out; the default "everything sees it unless filtered" leaks.
- (c) Design take: Moodle's rule is "delete if unused, else hide". FLS's idea is stricter and simpler: never delete, always retire. The un-hide (restore) is a manual staff action in Moodle; FLS un-retires automatically on uuid return, which is a new behaviour with no precedent here.
- (c) Moodle makes retirement a staff decision. FLS makes it a consequence of absence from the source, so the source of truth (the repo) and the displayed state cannot drift.

### 1.2 django-safedelete (closest code-level analogue)
- (a) Default manager hides soft-deleted rows. `all_with_deleted()` and `deleted_only()` exist; separate managers `all_objects` and `deleted_objects` are provided. https://django-safedelete.readthedocs.io/en/latest/managers.html
- (a) Visibility modes: `DELETED_INVISIBLE` is the default. A deleted object stays reachable through a ForeignKey or OneToOne from the other side, but drops out of the reverse relation of its parent. i.e. children keep pointing at it; the parent's reverse manager hides it. Source: same page.
- (a) No dedicated undelete: `update_or_create()` revives a soft-deleted match by resetting the deleted field to None. `created` stays False for a revived row unless `SAFE_DELETE_INTERPRET_UNDELETED_OBJECTS_AS_CREATED = True`. This is the same shape as FLS's un-retire on a later upsert by uuid. Source: same page.
- (b, from library docs not read in full) Policies include `SOFT_DELETE`, `SOFT_DELETE_CASCADE`, `NO_DELETE`, `HARD_DELETE`. The fetch did not return the policy page, so this is unverified. Repo: https://github.com/makinacorpus/django-safedelete
- (c) Design takeaways for FLS:
  1. The hard part is not the flag but that the default manager is changed everywhere. FLS cannot change a default manager (sites use `SiteAwareManager`, and audit code such as the cohort report must still reach retired rows through PROTECT relations). Safer: an explicit queryset method such as `.live()` plus tests that every learner-facing read goes through it. safedelete's own reverse-relation hiding is the exact leak the idea names ("every learner-facing query walks the relations and finds the row"); it is the thing to test.
  2. A timestamp field (`deleted`) is the library's choice too, matching the `retired_at` answer.
  3. Reviving through the upsert path is the established pattern: `update_or_create` plus reset flag. In FLS the content update and un-retire must be the same write, so a row is never "updated but still retired".
  4. Note that safedelete's cascade policy would also soft-delete children. FLS should not cascade: a child with its own uuid is retired only when its own uuid is absent. Consider and state explicitly what happens to a child still present in the source whose parent `Topic`/`Form` is retired (the child is unreachable through the outline anyway; the spec should say whether it gets `retired_at` set or is only hidden by its parent).

### 1.3 Terraform: removed from config is destroy by default, with an explicit "forget" escape
- (a) Deleting a resource block normally plans to destroy the real resource. A `removed` block with `lifecycle { destroy = false }` stops managing it without destroying it, and `plan` previews this ("will no longer be managed by Terraform, but will not be destroyed"). https://developer.hashicorp.com/terraform/language/block/removed , https://developer.hashicorp.com/terraform/language/state/remove
- (c) Same declarative model as `content_save` (desired set in files, state in a store, diff on absence). Terraform's lesson: absence-means-destroy is the dangerous default, so it gives a plan preview and an explicit opt-out. For FLS the equivalent is: absence means retire (the safe action), and a preview of what a run would retire is cheap insurance against a partial source (a wrong path set retires everything). Candidate for the spec: a dry-run count before the atomic save, or a refusal threshold. The idea states only "report counts in output"; a count printed after the fact does not protect a mistaken run, though the atomic save and un-retire-on-return limit the damage (nothing is deleted, the next correct run restores).
- (c) Un-retire on a later run is the Terraform "import back into state" analogue, except automatic.

### 1.4 Kubernetes: prune is the dangerous part of declarative sync, and its failures are about scope
- (a) `kubectl apply --prune` deletes "previously applied objects that are not in the set passed to the current invocation". Which are pruned depends on `--prune-allowlist`, `--selector` and `--namespace`, and "this can lead to objects being unexpectedly deleted or retained". Still alpha for usability, correctness and performance. https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/
- (a) Scope warning: run prune against the root directory only. "Running against sub-directories can cause objects to be unintentionally deleted if they were previously applied, have the labels given (if any), and do not appear in the subdirectory." Same page.
- (a) The replacement, ApplySet, tracks membership explicitly in a server-side parent object (a Secret by default) with a `part-of` label. Each object belongs to at most one set; use a unique set name per directory. Same page. KEP-3659 says label-based prune is "very difficult to use correctly": two directories sharing labels delete each other's objects. https://kubernetes.io/blog/2023/05/09/introducing-kubectl-applyset-pruning/ , https://www.kubernetes.dev/resources/keps/3659/
- (c) Direct mapping to FLS: "single source per site" is the ApplySet rule "each object belongs to at most one set". The label-prune failure ("a partial run deletes what it did not see") is exactly the risk of `content_save` being run with a subset of paths. The spec for save-safety (spec 1) must guarantee the path set is complete before this spec's retire step runs. ApplySet shows the robust answer is an explicit record of what the source is (a named set) rather than inferring it from the current invocation. Possible FLS analogue (c): record per Site which paths make up the source and refuse to retire when a run's paths are a strict subset of the previous run's. Not in the idea; flag as a question for the spec, not a recommendation to build.
- (c) Kubernetes also recommends explicit delete over prune, as safer. FLS equivalent: `danger_content_delete` stays the explicit delete.

### 1.5 Open edX
- (b) A runbook says learner state (`StudentModule`) stays in the LMS and reconnects to restored content without manual action; an MIT runbook says deleted `StudentModule` state is lost for good while `StudentModuleHistory` is not auto-deleted. https://engineering.ol.mit.edu/runbooks_post_mortems/openedx_clear_user_grades/ , https://openedx.atlassian.net/wiki/spaces/COMM/pages/3966795804
- (b) Block deletion in the API memo is a subtree delete by OLX `url_name`; handling of learner rows not stated. https://openedx.atlassian.net/wiki/spaces/COMM/pages/3696066564
- (?) Whether course re-import removes blocks missing from the OLX, and what happens to `StudentModule` rows, was not found. Learner state keyed by a usage key that survives re-creation of a block with the same key is consistent with the idea's "un-retire when the uuid returns" (c).
- (c) Open edX has no retired state for blocks: a removed block is deleted from the course structure. FLS is stricter.

### 1.6 Canvas / QTI imports
- (b) Canvas re-import of the same QTI zip does not make a third copy, and repeated migrations use "smart merging" for question bank content; nothing found about what happens to questions removed from the source. https://developerdocs.instructure.com/services/canvas/resources/content_migrations , https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Quiz-doesn-t-update-via-content-import/m-p/518720
- (c) Match key on re-import in Canvas is the package's `migration_id` (from background knowledge, not verified here), the same role as the uuid. Imports are additive, so no retire precedent exists; this confirms the prior-art note that FLS's prune-by-absence is novel in the LMS space.

### 1.7 Questionmark retire (supplement)
- Nothing new beyond the prior-art note (vendor marketing: retire keeps a question in the bank "unused" and referenceable). It is a manual author action in Questionmark, not derived from a source.

## 2. Patterns that match the idea's settled points

| Idea point | Precedent |
|---|---|
| Retire, never delete, because learner rows reference content | Moodle in-use delete becomes hide; Questionmark retire; safedelete soft delete |
| Nullable timestamp, retired when set | safedelete `deleted` field |
| Un-retire in the same write as the content update | safedelete `update_or_create` revival; Terraform re-adopting a resource |
| Single source per Site | ApplySet: object belongs to one set; label-prune cross-directory deletion is the failure |
| Filter before shuffle/draw | Moodle: hidden questions are excluded from drawing, but still exported (leak on the side paths) |
| Retired visible to educators, marked | Moodle "Show old questions" toggle, restore button |
| Pinned in-progress attempts keep the paper | Moodle (attempt pins version), Canvas (attempts begun keep the old item) |

## 3. Gaps and pitfalls the references expose (inputs for the spec)

1. **Side paths leak.** Moodle's hidden questions still appear in XML export. FLS needs a list of read paths beyond the learner pages: exports, reports, admin, search, progress totals, `ContentCollectionItem` walks. The idea covers learner pages; the "Course progress excludes retired children" answer covers totals. A test that enumerates reverse relations from every retired-able model would catch the safedelete-style reverse-relation leak.
2. **Partial-source retirement.** Kubernetes prune and Terraform destroy-on-absence are the cautionary tales: a run that sees a subset retires the rest. Atomic save and reversible retire limit the harm, but a mistaken run still blanks the live site until the next run. Ask the spec to say: dry-run or count threshold, or accept and document.
3. **Parent retired, child present.** safedelete soft-deletes by policy (cascade or not); FLS needs an explicit rule. Retiring only the absent uuid is the minimal rule; the child is hidden through its parent's outline. State whether a child directly addressed by URL while its parent is retired is served (it should not be).
4. **Un-retire is automatic in FLS, manual in Moodle.** Auto un-retire means an accidental removal and re-add flips content back with no human step. That matches the idea ("kept learner data is live again") but is the one behaviour with no precedent in the references; worth a test and a line in command output when rows are un-retired (already settled: counts).
5. **File without uuid.** No reference helps: Open edX `url_name` and QTI `identifier` are explicit ids; path-keyed assets are matched by path in general. The idea's path-key recommendation is reasonable; moving a file renames the key and so retires the old path and creates a new `File` row (c). Flag as a known consequence.
6. **Retire versus revise.** Moodle and Canvas separate "hidden/retired" from "new version"; the idea does the same (spec 3 owns versions). Keep the two flags independent so a question can be retired, and a retired question can be revised in the source and return as a new version on un-retire. Spec 3 must define what un-retire of a changed question means.

## 4. Sources

- https://tracker-old.moodle.org/browse/MDL-76757
- https://tracker-old.moodle.org/browse/MDL-82875
- https://moodle.org/mod/forum/discuss.php?d=87799
- https://docs.moodle.org/405/en/Question_bank
- https://django-safedelete.readthedocs.io/en/latest/managers.html
- https://github.com/makinacorpus/django-safedelete
- https://developer.hashicorp.com/terraform/language/block/removed
- https://developer.hashicorp.com/terraform/language/state/remove
- https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/
- https://kubernetes.io/blog/2023/05/09/introducing-kubectl-applyset-pruning/
- https://www.kubernetes.dev/resources/keps/3659/
- https://engineering.ol.mit.edu/runbooks_post_mortems/openedx_clear_user_grades/
- https://openedx.atlassian.net/wiki/spaces/COMM/pages/3966795804
- https://openedx.atlassian.net/wiki/spaces/COMM/pages/3696066564
- https://developerdocs.instructure.com/services/canvas/resources/content_migrations
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Quiz-doesn-t-update-via-content-import/m-p/518720

status: ok
reason: Moodle, django-safedelete, Terraform, Kubernetes prune and ApplySet read; Open edX and Canvas re-import deletion behaviour not found in sources, safedelete delete policies not read
