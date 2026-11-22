# Research: best practices

Scope: facts and practices relevant to the `reference:` idea. No plan. Sources below are from background knowledge of well-known documentation and were not re-fetched in this run, so check the wording before quoting them.

## 1. Declarative content-as-code loaders that reconcile DB state with files

- **Replace (declarative) versus additive sync.** Files are the source of truth in a declarative loader. Applying the same files twice gives the same state (idempotent). An additive loader only creates and updates, so removing something from the files leaves it in the database and the two drift apart. Kubernetes `kubectl apply --prune` and Terraform both reconcile by deleting what the declaration no longer names.
  - kubectl declarative management: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/
  - Terraform plan and apply: https://developer.hashicorp.com/terraform/cli/run
- **Scope the delete to what the run owns.** Prune is safe when it is limited to a selector or owner. Kubernetes prune works within a label selector or ApplySet, and Terraform works within one state. Deleting by "everything not in this load" without a scope is the common cause of accidental data loss. In this idea, replace applies to `CourseReferencePart` rows only for the courses in that load, and the cleanup applies only to the course that lists the part.
- **Prefer deleting derived link rows over content rows.** Replacing a join table (here `CourseReferencePart`) is cheap and loses nothing, because the part and its topics are saved separately. Deleting content rows that carry user data is the risky case. Collection items are referenced by `learner_progress` and deadline overrides, so the deletion needs explicit scoping and reporting.
- **Report destructive changes.**
  - Print each removal by name, grouped, before or as it happens. Terraform's plan output (`- destroy`) and Django's `migrate` / `flush` / `collectstatic --clear` messages are the model.
  - Give counts as well as names, which fits `danger_content_delete`, which already counts and deletes.
  - Make the report part of normal output, not only verbose output, so CI logs show it.
  - Report per course and per item, because that is how an author reads it: "course X: removed placement of part Y (N deadline overrides, M due dates)".
- **Dry run / plan mode.** Good practice is a `--dry-run` or plan that computes the same deletions and prints them without writing. It works best when the apply path and the plan path share one code path (compute a change set, then apply or print it). Use a transaction so a failed load rolls back whole instead of half-applying. Django's `transaction.atomic` and `loaddata` follow this. Git-based CMS and static-content loaders (Hugo, Jekyll data files, Wagtail/Django fixtures) are mostly read-only and idempotent. Django `loaddata` is upsert-only and never deletes, so it is an example of the additive pattern.
  - Django `loaddata`: https://docs.djangoproject.com/en/stable/ref/django-admin/#loaddata
- **Order of operations.** Validate everything first and fail before any write. Then write content, then links, then prune. Idempotence means a re-run after a failure converges.
- **Natural keys and stable identity.** Reconcile on a stable key (path, slug, or UUID in the file). Moving a file then updates instead of delete-and-create, and this matters when child rows hold progress. A `unique(course, course_part)` constraint gives the reconcile step a key to match on.
- **Cascade awareness.** A real FK with `on_delete=CASCADE` stops dangling rows but makes parent deletion a silent mass delete, so deletion counts should include cascaded rows. Django's `Collector` / `NestedObjects` (used by admin's delete confirmation) shows how to count them: https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.get_deleted_objects

## 2. Schema design for optional / supplementary material versus the required path

- **Separate relation instead of a flag on the path.** Two patterns exist.
  - A flag or "kind" on the path item (Moodle's optional/"restricted" activities, Open edX's `graded`/`exclude_from_progress` style attributes). Every consumer of the path must then filter on the flag, and any one that forgets it counts supplementary material as required work.
  - A separate relation (Canvas/Open edX "supplementary" or "resources" areas, SCORM/xAPI "optional" modules held outside the sequencing tree). Consumers of the path cannot see the material by construction. This idea takes the second pattern, to avoid touching about 160 call sites.
  - Open edX content structure (a course tree of sections, subsections, units): https://docs.openedx.org/en/latest/educators/concepts/course_structure.html
- **Completion, progress and gating are defined over the required set.** Percent complete should be computed over a set that excludes optional material, so the cleanest design makes membership in that set exclusive. Having an item in both the required set and the optional set gives contradictory answers, which is why "same part in both lists" is a validation error.
- **One content object, several placements.** Normalised designs reuse the content row and vary the placement row (a join table with ordering). Position (`order`) belongs on the join row. The `(course, course_part)` unique constraint stops duplicate placements. Content shared between courses by path (`../`) works when placement is per course and content is not duplicated.
- **Only the placement carries required-ness.** Due dates, deadlines and gating attach to the placement in the learning path. A reference placement should have no such columns, so the model cannot hold them, and validation rejects them in the files. Constraining at both layers (schema in the file, no column in the table) is the usual belt-and-braces.
- **Explicit list versus auto-discovery.** Auto-discovery from directory layout is convenient for the required path but ambiguous for supplementary material, because a directory name starts to carry meaning. Content-as-code tools usually make ordering and membership explicit in a manifest when order matters (mkdocs `nav`, Docusaurus sidebars, mdBook `SUMMARY.md`). Mixed schemes (manifest wins, directory is a fallback) need a stated rule for the reserved directory name, which here is `reference/` never being read as path content.
  - mkdocs nav: https://www.mkdocs.org/user-guide/configuration/#nav
  - mdBook SUMMARY.md: https://rust-lang.github.io/mdBook/format/summary.html
- **Depth limits.** Fixing "part then topics" (one level) keeps queries and validation simple, because a recursive structure needs recursion in every rule. A rule that rejects nested parts is easier to enforce than one that handles them everywhere.

## 3. Validating cross-file references in a static content repo

- **Two layers.** A per-file schema check (types, required keys, forbidden keys; here a Pydantic model) and a cross-file check that needs the resolved graph (paths exist, targets are the right type, no item in two incompatible lists, no cycles). Per-file checks cannot see cross-file facts, so the rules about "part in both lists" and "child is a Topic" belong to the second layer. The open question of whether "points at a non-part" fails in the schema or in the cross-file rules has this answer: the schema only sees a path string, so type-of-target checks need the resolved file.
  - Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/
- **Resolve relative paths against the declaring file and normalise.** Resolve `../`, compare the canonical resolved path (not the raw string) for "same part" checks, and confine the result to the load root so `../` cannot escape it. mdBook, Hugo and mkdocs all report broken or out-of-root references as build errors, not warnings.
- **Validate beyond the requested subtree when the rule needs it.** When validating a path that holds only part of the graph, rules that compare against a part outside it must parse that part from disk. This is what `_ParsedByPath` does here for parts outside the validated path. The rule "no due keys on topics in a reference part" has the same need, because the topics live in the part directory even when the validated path is the course file.
- **Fail early, collect all errors.** Linters (markdown-link-check, Hugo `--panicOnWarning`, Sphinx `-W` nitpicky) report every broken reference in one run with file and key, so authors fix them in one pass.
  - Sphinx nitpicky mode: https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-nitpicky
- **Same rules on every entry point.** When the DB writer can be called without the CLI validator (fixtures, downstream projects), the check list must run in the writer too. Duplicate check lists drift unless one list is the single source that both call. The idea names two lists (`validate(path)` and `save_content_to_db`), so a test that runs the same bad fixture through both guards against the drift.
- **Error messages name file, key and rule.** For example: `course.md: reference[1] has due_date`.
- **Destructive side effects must not hide behind passing validation.** When a rule passes but the DB would contradict the files (a part in `children:` last load, now in `reference:`), the loader must reconcile or flag it. Passing validation does not mean the database already matches.

## 4. Keeping a hand-synced offline validator in step

- **Duplicated logic drifts.** The offline copy (`claude_plugins/fls-content/validate/`) has no import path to the Django code, so it is a second implementation. Known mitigations, strongest first:
  1. Generate it from the source (export the Pydantic model to JSON Schema with `model_json_schema()`, and ship that). Pydantic: https://docs.pydantic.dev/latest/concepts/json_schema/. Generated schemas cover keys and types but not cross-file rules.
  2. Share a table of test cases (fixtures) that both validators run, each with the expected error. Parity then shows up as a test failure on either side. This is the cheapest check for hand-written cross-file rules.
  3. A parity test that diffs field names of the Pydantic schema against the offline schema (the set of keys on `Course`, `Child`, the due keys), so a new key on one side fails the test.
  4. A checklist in the change process: any edit to `schema.py` or `validate.py` is paired with an edit to the offline copy, enforced in review.
- **Make drift visible.** A version or "synced with" marker in the offline copy, and a CI test that fails when the parity test or shared fixtures disagree, are more reliable than convention alone.
- **Offline rule coverage list.** Each new rule (due key on entry, due key on a topic in a reference part, non-Topic child, part in both lists, and any schema-level shape of `reference:` entries) needs a test on the offline side as well as the Django side, with the same fixture and message intent.
- **Docs are a third copy.** Author docs in `claude_plugins/fls-content/` list the rules in prose, so they drift too. Keep the rule list in one place and link to it, or test that each rule name appears.
- **Concurrent changes.** The idea notes that two sibling specs change `content_save`, the schema and the validator. With three hand-synced places, whichever lands second must re-run the shared-fixture tests after the rebase to catch a half-merged rule.

## Source list

- https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/
- https://developer.hashicorp.com/terraform/cli/run
- https://docs.djangoproject.com/en/stable/ref/django-admin/#loaddata
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.get_deleted_objects
- https://docs.openedx.org/en/latest/educators/concepts/course_structure.html
- https://www.mkdocs.org/user-guide/configuration/#nav
- https://rust-lang.github.io/mdBook/format/summary.html
- https://docs.pydantic.dev/latest/concepts/validators/
- https://docs.pydantic.dev/latest/concepts/json_schema/
- https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-nitpicky

status: ok
