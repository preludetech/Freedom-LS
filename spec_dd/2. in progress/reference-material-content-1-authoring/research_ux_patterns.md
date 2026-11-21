# Research: UX patterns for authoring `reference:`

Scope: authors writing `course.md`, running `content_save` and the offline validator, and admins using an inline. Facts only. In-repo facts were read from `freedom_ls/content_engine/management/commands/content_save.py` and `freedom_ls/content_engine/validate.py`. External pattern URLs were NOT fetched in this run; they are cited from prior knowledge of those docs and are marked as such.

## 1. House style in the repo

### 1.1 Authoring syntax today
- `children:` is a list of entries each with a `path` (a `Child`, with optional due keys and a nested `children:` for parts). Paths resolve through `resolve_author_path(file_path, path)`, relative to the declaring file, `../` allowed.
- `collection_children(collection)` is the one rule for "what a collection holds": listed entries, else auto-discovered files (which have no entry). Shared by the validator and the loader so they never disagree. A `reference:` equivalent would follow that shared-function pattern.
- Absent-key semantics are explicit in the loader: an absent `tags:` or `price:` leaves stored values alone; `categories` and `organisations`/`shared_with` are replace (`.set(...)`) so the file is the single source. `reference:` is specified as replace.

### 1.2 Validation error style (validate.py)
- Each problem is a block starting `"\n❌ <header> in <file_path>"`, then `Content type: <TYPE>`, blank line, then:
  ```
    • Field: children[2]
      Problem: this child is named twice
      Given value: 'x/topic.md'
      Resolved to: ...        (optional)

      <fix sentence>
  ```
  Built by `_reference_error` / `_placement_error` (headers such as "Broken widget reference", "Invalid children list").
- Fields are named by key path with index: `children[3]`, `children[1].children[0]`. A `reference[i]` field name fits this.
- Problem text is a short noun phrase ("the part has no child at this path", "this child is a FORM", "a due date on a X placement"); fix is an imperative sentence, often listing the valid options ("The part's children are: a.md, b.md. Paths are relative to the part's directory.").
- Cross-file rules return `list[str]` (all errors, never first only); `validate()` appends them as `failed_files` and prints one report: a `=`*80 banner, `❌ Validation failed: N problem(s):`, each block followed by a `-`*80 rule.
- `save_content_to_db` re-runs the same list functions (`validate_children_lists`, `validate_due_date_placements`, `validate_question_sections`) and raises one `ValueError("\n".join(errors))` before any write. The idea's "both check lists" matches this.
- Loader-side defence errors use a one-line form: `ValueError("Unknown dashboard_category 'x' in <path>: no CourseCategory with this slug is declared.")`; slug-collision errors name the owner uuid and give both remedies ("To edit that category, give this entry `uuid: ...`; to add a new one, choose a different slug.").
- Pydantic failures render as `❌ Validation failed in <location>` / `Content type:` / `Errors found:` with `• Field: a -> b`, `Problem:`, `Given value:`.

### 1.3 CLI output style (content_save)
- Output is `click.echo`; most progress is `logger.info` (silent by default). Visible lines today:
  - per file: `Created|Updated <type> file: <relative_path>` plus indented (two spaces) detail lines for images (`  PNG 800x600 -> WebP lossless ...`, `  5.1 MB -> 118 KB (-97.7%), optimised.`);
  - cache line: `Wrote N and removed M file(s) under <dir>/. Commit them alongside the content change, or ...` (a count line that ends with an instruction);
  - end: `✓ Successfully saved all content for site: <site>` then `Images: N seen (a x, b y).`
- No existing removal/reconciliation line for DB rows is echoed: reconciliation of `CoursePartChildDueDate` rows and category membership is silent; `moved_children`/`carry_placement_due_dates` and the `collection_items_synced` signal are also silent in `content_save`. The only existing "removed" wording is the image-cache count. Counts use `N file(s)`.
- The whole load is `@transaction.atomic`; errors raise `ValueError` (djclick prints it). Removal output would appear before the final `✓` line only if echoed during the run; a rollback after echoing would leave misleading text (the image-cache comment in the file already notes this ordering concern for notices).

## 2. External patterns: a second list beside a primary list in frontmatter

(From prior knowledge; not fetched.)
- MkDocs: `nav:` is the explicit ordered list; files not in `nav` still build and the CLI emits an INFO line listing pages not included. https://www.mkdocs.org/user-guide/configuration/#nav
- Sphinx: `toctree` lists documents in order; a document in no toctree gets a "document isn't included in any toctree" warning; a `:hidden:` option and the separate `orphan` file-metadata exist for deliberately unlisted pages. https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-toctree
- Hugo: separate named menus in front matter (`menus:`/`menu:` with `weight` for order) and taxonomies are parallel keys, each its own list, rather than one list with a flag. https://gohugo.io/content-management/menus/
- Docusaurus: sidebars are separate named lists (`sidebars.js`), an item may be an explicit path id, and a document can appear in several. https://docusaurus.io/docs/sidebar
- Common shape: sibling top-level keys (`children:` / `reference:`), each an ordered list of path entries, the list order is display order; membership in exactly one list is enforced as a validation error rather than silently resolved (Sphinx warns on duplicates across toctrees).
- Entry shape: bare path strings versus mappings with a `path` key. FLS `children:` uses mappings; a list that allows only `path` is the minimal form.

## 3. External patterns: directory conventions for supplementary material

(From prior knowledge; not fetched.)
- Underscore or reserved-name directories are excluded from the main walk: Jekyll `_drafts`, `_includes` (https://jekyllrb.com/docs/structure/); Sphinx `_static`, `_build` and `exclude_patterns` (https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-exclude_patterns); Hugo `static/`, `assets/`, `archetypes/` (https://gohugo.io/getting-started/directory-structure/).
- Hugo "leaf bundle" vs "branch bundle" (`index.md` vs `_index.md`): a directory name signals whether it is read as content (https://gohugo.io/content-management/page-bundles/).
- Convention in the idea: a course directory's `reference/` is never auto-discovered as learning path; every part is listed. This is the "explicit list wins, directory name is a hint to humans" pattern. Sharing across directories by `../` mirrors FLS `children:`.

## 4. External patterns: reporting destructive reconciliation

(From prior knowledge; not fetched.)
- Terraform plan/apply: one line per resource with a symbol (`+`, `~`, `-`) and the resource address, then a totals line `Plan: 1 to add, 0 to change, 2 to destroy.` https://developer.hashicorp.com/terraform/cli/commands/plan
- Django `migrate`/`makemigrations`: per-item lines under a verb group (`Applying app.0002_x... OK`; `- Remove field x from y`); `flush`/`loaddata` print an object count (`Installed N object(s) from M fixture(s)`). https://docs.djangoproject.com/en/stable/ref/django-admin/
- rsync `--delete` / `--itemize-changes`: `deleting <path>` one per line, no grouping. https://download.samba.org/pub/rsync/rsync.1
- Alembic/Kubernetes apply: `<kind>/<name> deleted|configured|created`, grouped by action implicitly through verb suffix. https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/
- Common properties: names the thing removed (not just a count); states why/which source made it stale; keeps an action verb at a fixed position so output is greppable; ends with a totals line; indents detail beneath a parent line (same as the image detail in `content_save`).
- Grouping options seen: per parent (course, then removed items under it), or per action (all removed, then all added). In FLS terms the removal is naturally scoped by course because the cleanup "applies only to the course that lists the part".

## 5. Admin inline

- Repo convention is the `fls-dev:admin-interface` skill (`SiteAwareModelAdmin`); Django's own pattern is `TabularInline` with an ordering field for ordered related rows (https://docs.djangoproject.com/en/stable/ref/contrib/admin/#inlinemodeladmin-objects). Not re-researched here.

## 6. Open points these patterns bear on (not decisions)

- Wording of the removal line: existing `content_save` echoes use `Verb noun: detail`, `N x(s)` counts, 2-space indented detail, and a trailing instruction in the cache line.
- Validation messages for the three new rules map onto the existing `Field / Problem / Given value / fix` block, with `reference[i]` as the field name and a new header such as "Invalid reference list" alongside "Invalid children list".
- The "part in both lists" error is a cross-list conflict: precedent is `_NAMED_TWICE` for the same-list duplicate (problem + "Name each child once.").

status: ok
