# Research: UX patterns for `content_save` safety (CLI)

Scope: the "UI" is the `content_save` management command, run by authors, often through an AI agent, and in deployment.
Provenance: the `content_save` / `content_validate` findings come from reading the repo. Findings about other tools come from my knowledge of them, except cargo, which one web search partly confirmed (the flag, and that the error lists files; exact wording not confirmed). Check wording against a live run before quoting it in a spec.

## 1. How the existing commands speak (fit recommendations to this)

Read from `freedom_ls/content_engine/management/commands/content_save.py` and `content_validate.py`, and `freedom_ls/content_engine/validate.py`.

- Both are `djclick` (click) commands. `content_validate` is `@click.argument("path")` and calls `validate(path)`. `content_save` is `@click.argument("path")`, `@click.argument("site_name")`, then `validate(path)` and `save_content_to_db(path, site_name)`.
- Failure style: functions raise `ValueError` with a multi-line message. Messages start with `\n❌ ` (e.g. `❌ Path does not exist: ...`, `❌ Category slug 'x' in <relative path> already belongs to ...`). They name the offending file and, where possible, the fix ("give this file `uuid: <id>`; to add a new one, choose a different slug"). djclick turns an uncaught exception into a traceback and a non-zero exit; there is no `ClickException` use.
- `validate()` is already collect-all: it keeps going past a bad file, then raises one report: a line of 80 `=`, `❌ Validation failed: N problem(s):`, 80 `=`, each message followed by an 80 `-` rule. Cross-file passes append `(path, message)` too. Messages carry the file path as given on the command line (often absolute or `../bloom_content/...`), not a source-root-relative path. Placement errors in `save_content_to_db` are joined with `"\n"` and raised as one `ValueError`.
- Success style: `click.echo` lines such as `Created <type> file: <relative path>`, an indented image-decision line, `Wrote N and removed M file(s) under .fls-image-cache/. Commit them alongside the content change, or every other clone pays the full encode again.` (this is already a "tell the author to commit" pattern), then `✓ Successfully saved all content for site: <site>` and `Images: N seen (...)`. Per-entity detail goes to `logger.info`, which is not shown by default.
- Existing relative paths: slug-collision messages and `File.file_path` use paths relative to the source root. Validation messages do not.
- Uuid write-back today has no console message of its own (only `logger.info`). The author finds out from `git status`.
- Docstring example: `python manage.py content_save  ../bloom_content Bloom`.

Fit: new refusals should reuse the `❌` prefix, the count-and-list shape of the `validate()` report, and "name the fix" phrasing. The existing "Commit them alongside ..." wording is the model for the post-write message.

## 2. Refusing on a dirty tree

Patterns seen in other tools:

| Tool | Behaviour |
|---|---|
| `cargo publish` | Refuses. Error names the count, lists each uncommitted/untracked file path (relative to the package), then says to pass `--allow-dirty` to proceed. Override is a flag named for the risk. Source: cargo docs https://doc.rust-lang.org/cargo/commands/cargo-publish.html (flag); error shape from cargo's test suite and memory. |
| `npm version` | Refuses with `Git working directory not clean.` In recent npm versions it also prints the `git status` style list of files. Override is `--force`. Terse; the file list was added later because the bare message was not enough. Docs https://docs.npmjs.com/cli/commands/npm-version |
| `setuptools-scm` | Does not refuse. A dirty tree changes the output (version gets a `.dDATE` suffix). Mark-not-block. Docs https://setuptools-scm.readthedocs.io/ |
| `poetry` / `poetry build` | No dirty-tree check in core; only plugins (e.g. poetry-dynamic-versioning) mark or fail on dirty. |
| `helm` / `terraform` | No git check; they act on the files on disk. Terraform and helm show diff/plan output rather than refusing. Not a useful precedent for refusal. |
| `pre-commit` / `git commit` hooks | Print the files a hook changed and exit 1, so the user restages and reruns. Relevant to the post-write message. |

Common elements worth copying:
1. Say what was found and why it blocks, in one sentence, before the list. E.g. `❌ Refusing to save: 3 paths have uncommitted changes. A save must come from a committed state.`
2. List the dirty files, grouped by source path, as paths relative to the git repo root (the same root `.fls-content.yaml` is read from). Mark the kind (`modified`, `untracked`, `deleted`) as `git status --short` does, so an agent can map each line to an action.
3. Cap long lists. Cargo lists everything; npm historically lists nothing. A middle course: show the first N (suggest 20) per path, then `... and 137 more`. Always show the total count. Do not cap uuid or validation lists (see 4).
4. Name the fix: `Commit or stash these changes, then rerun.` Do not suggest an override flag, because the spec says the check is always enforced and has no bypass. That is a deliberate difference from cargo (`--allow-dirty`) and npm (`--force`). Say so in the docs so authors do not look for one.
5. State what was NOT done: `Nothing was written.` This matters because the command's whole promise is "before any write" (DB, source files, file storage).
6. Report every dirty path in one run (all paths checked, not first-failing path), same reasoning as validation.
7. Ignored paths: per the answers, an `ignore:` entry exempts a path only from content validation/saving, not from the git check. Say in the message when a dirty file is an ignored one (e.g. `CLAUDE.md (listed under ignore: in .fls-content.yaml, but still must be committed)`). Otherwise an author will be confused that an "ignored" file blocks the save.
8. Non-git path: a separate, short message: `❌ <path> is not inside a git working tree.` Distinct from dirty; do not fold into the dirty list.
9. Ordering: the spec says git check first, then uuid check. Because a clean tree is a precondition for the uuid listing to be actionable (the author is told to commit, then rerun), print only the git failures if both apply, and do not also print uuid problems. An alternative (print both) saves a round trip but contradicts "a dirty tree is reported first". Recommend following the spec and ending the git message with no uuid noise.

## 3. Many errors at once, grouped by file

- Collect-all is the norm for linters and validators (ruff, eslint, mypy, `terraform validate`, django `check`). First-failure is the norm for runtime errors in a pipeline. Missing uuids and dirty files are check-style results, so collect all (the idea already says so).
- Group by file, then list entries inside the file. Eslint/ruff show `path:line:col: message` lines; mypy prints one per line. For uuid problems there is usually no line number available from the parser, so give the entity identity instead: `<relative/file.md>: Topic "Title" is missing a uuid`, and for nested ones the position, e.g. `<file>.yaml: FormQuestion "slug" option 2 ("value") is missing a uuid`, `courses/categories.yaml: COURSE_CATEGORIES entry 3 (slug "x") is missing a uuid`. Include the entity type because the check covers 11 kinds (Topic, Activity, Article, Course, CoursePart, Form, FormPage, FormContent, FormQuestion, QuestionOption, CourseCategory).
- Paths relative to the source root, not the CWD or an absolute path. This keeps output stable between a dev machine and a deploy, and matches `File.file_path`. With several source paths, prefix each group with the source path as the user typed it (a header line), so two roots with the same relative path (the spec fails the save on that) are distinguishable. Suggested shape:

```
❌ Refusing to save: 4 uuids are missing in 2 files. Nothing was written.

<source path as given>
  topics/intro.md: Topic "Intro" has no uuid
  forms/quiz.yaml: FormQuestion "q1" has no uuid
  forms/quiz.yaml: FormQuestion "q1" option 2 has no uuid
  courses/main.yaml: CoursePart "Week 1" has no uuid

To write the missing uuids into these files, rerun with --generate-uuids,
then commit the changed files.
```
- Put the count in the summary line, and the fix last (the line a human or agent reads last is the one they act on). The existing `validate()` banner uses `=` rules; reuse it for consistency, or the plainer shape above. Either is fine; do not invent a third.
- Uuid and validation errors: a very long list is still useful, since an agent can fix them in bulk. Rather than capping, group by file and optionally collapse "all N entities in file X are missing a uuid" when the whole file is new. Recommended: no cap for uuids, cap for dirty files (where only the count and a sample are needed).
- Validation across several paths: keep the collect-all behaviour of `validate()` across all paths, and label each problem with its source path. Do not stop at the first bad path.

## 4. Opt-in write-back flags

- Names in use elsewhere: `--fix` (ruff, eslint: apply fixes in place), `--write` (prettier, `terraform fmt` writes by default and uses `-check` to not), `--allow-dirty`/`--force` (override safety), `--generate-*` (e.g. `--generate-hashes` in pip-compile, `--generate-schema`). `--generate-uuids` (already in the idea) is accurate and matches the `--generate-*` convention; it names the action, not a vague "fix". Keep it.
- Default is the read-only/refuse behaviour; the flag opts in. This matches ruff (`--fix` is opt-in) and prettier (`--check` vs `--write`).
- Tell the user which files were changed: ruff prints `Found 12 errors (10 fixed, 2 remaining).`; prettier lists written files; pre-commit lists modified files. Recommendation for `--generate-uuids`: after a successful save, print `Wrote N uuids into M source file(s). The tree is now dirty; commit these files before the next run:` then the changed files, grouped by source path and relative to the source root, with a per-file count. Today this information only exists in `logger.info`, which a default run does not show. An agent will likely run `git add` / `git commit` from this list, so make it one path per line, with no decoration inside the path.
- Combine with the image cache manifest message: both leave the tree dirty. One closing block "Files changed by this save" covering uuid writes and the existing `.fls-image-cache/` manifests, rather than two unrelated messages, makes the "commit these" instruction clear. The existing `Wrote N and removed M file(s) under .fls-image-cache/` line can stay as is if changing it is out of scope.
- When the flag is passed but nothing is missing, say so (`No uuids were missing.`) rather than stay silent, so a user running `--generate-uuids` by habit is not left wondering.
- When the flag is not passed and uuids are missing, the refusal message is what teaches the flag (see the template above). The docs/`fls-content` skills must say the same wording.
- Atomicity: file writes should occur only after every path has parsed and validated, and DB writes should stay inside the transaction. If the DB step fails after uuids were written to files, the author has a dirty tree and no rows; the message on failure should say the files were already changed. Worth a decision in the spec (write files last, after the DB commit succeeds, or write them first and say so). Not decided by the idea; flag it.

## 5. Several paths with a trailing required positional

- Existing call: `content_save <path> <site>`. New: `content_save <path>... <site>`.
- Click supports `nargs=-1` for a variadic argument followed by a fixed required argument (`@click.argument("paths", nargs=-1, required=True)` then `@click.argument("site_name")`): click's parser allocates the trailing fixed arguments from the end. Argparse (`nargs="+"` then a positional) also handles this. Prior art: `cp SRC... DEST`, `mv`, `git add -- paths`, `docker cp`. So paths-first-site-last is the Unix norm and old two-argument calls keep working unchanged (one path plus site), as the idea recommends.
- Failure mode to design for: a user who forgets the site (`content_save ../a ../b`) has the last path read as the site name and gets `Site matching query does not exist` (current behaviour for a bad site is `Site.objects.get(name=...)` raising `DoesNotExist`). Likewise a mistyped site passes as the site, and a single argument gives a click "missing argument" usage error (exit 2). Mitigation: resolve and report the site first or with a hint, e.g. `❌ No site named "../b". The last argument is the site name; the paths are everything before it.` and list the existing site names, as `_resolve_organisations` already lists valid organisation slugs. This also helps an agent.
- Do not add a `--site` option as an alternative unless asked (project rule: no unrequested functionality).
- Duplicate paths, nested paths (one path inside another), and the same repo given twice are all plausible agent mistakes. Report them as their own refusal before the git check. The spec covers the same relative path from two paths, but not a path that is the parent of another; it will double-scan. Flag for the spec.
- Docstring and `--help` text must show the multi-path form: `python manage.py content_save ../bloom_content ../bloom_extra Bloom`. Keep the `@click.command()` docstring (it is the `--help` text) updated.

## 6. Exit codes

- Convention: 0 success; 1 operational failure; 2 usage error (click/argparse give 2 for bad arguments). Tools that "check" (`black --check`, `terraform plan -detailed-exitcode`, `git diff --exit-code`) use non-zero for "would change". For a refusal (dirty tree, missing uuids, validation failure) non-zero is required, and the same code for all refusals is enough; agents branch on the message, not the number. Recommendation: one non-zero code (1) for every refusal; leave 2 to click for bad arguments.
- Today uncaught `ValueError` produces a traceback. For refusals this is noisy and puts the useful text under stack frames. Prefer `click.ClickException` (or djclick's `CommandError`) so the user sees `Error: <message>` and no traceback, exit 1. This changes existing behaviour for validation errors; confirm that is wanted, or limit the cleaner path to the new refusals. Note `save_content_to_db` is called directly by tests and downstream projects, so it should keep raising `ValueError`/an exception subclass; the command translates at the boundary.
- Write refusal text to stderr (`click.echo(..., err=True)` or via the exception) and the success summary to stdout, so a pipeline or agent can capture them separately.

## 7. Making output readable to an AI agent

- State the verdict first and the count: `❌ Refusing to save ... Nothing was written.` An agent reading the tail of a long log sees the verdict; put the verdict at the top and repeat a one-line summary at the end if the list is long.
- One fact per line, stable format, path first: `<relative path>: <Entity> "<title or slug>" <problem>`. Greppable, no wrapping, no ANSI colour or progress spinners (the repo does not use colour; keep it that way, and avoid emoji beyond the existing `❌`/`✓` since they are already the project convention).
- Give the exact next command, copy-pasteable, with the user's arguments echoed back: `Rerun: python manage.py content_save <paths as given> <site> --generate-uuids`. Agents tend to follow a literal command exactly. Also state what to do after: `git add <files>` / commit, then rerun without the flag.
- Say explicitly what is and is not an option: no override for the dirty tree. Otherwise an agent will look for `--force` or run `git stash`/`git commit -a` on its own to get past it. If agents are expected to commit on the author's behalf, say it in the `fls-content` skill; the command itself should only say "commit or stash".
- Do not print the same problem twice (once from `validate()` and once from the save path). `validate(path)` runs in the command and again in `save_content_to_db`'s placement checks today; with several paths, make sure one failing path is not reported by both.
- Keep the success output short and ending with a clear final line; the `✓ Successfully saved all content for site: <site>` line already does this. Add the recorded commit per path to the success output (`<path>: saved at commit <short sha>`), because the later question-version spec reads it, and it gives the agent proof the save came from a committed state. Use the short sha plus path.
- Machine-readable output (`--format json`) is a common agent aid but is not requested; do not add it. Note it as a possible later improvement only.
- Docs and skills must carry the same message strings as the command, because agents read `claude_plugins/fls-content` first. Keep one wording per refusal.

## 8. Specific recommendations for the spec

1. Refusal order and shape: unusable arguments (site unknown, duplicate/nested paths) -> not-a-git-tree -> dirty tree (all paths, all files, capped list with total) -> parse/validate (all paths, collect-all) -> missing uuids (all, grouped by file, uncapped) -> write. Every refusal ends with `Nothing was written.` and a next step.
2. Use the existing `❌` prefix and `N problem(s)` count phrasing; paths in the new messages are relative to the source root (or repo root for git lines), prefixed by a per-source-path header.
3. `--generate-uuids` stays (matches `--generate-*` convention); on success print which files were changed and tell the author to commit them; also print the recorded commit per path.
4. Order arguments `paths... site`; add a site-not-found message that says the last argument is the site and lists valid sites.
5. Command raises click-level errors (non-zero, no traceback, stderr); `save_content_to_db` keeps raising ordinary exceptions for tests and downstream callers.
6. No `--allow-dirty`/`--force`. State it in the docs.
7. Decide in the spec: whether uuid files are written before or after the DB commit; whether nested/duplicate paths are refused; the cap size for dirty-file lists; whether existing `validate()` tracebacks are to become clean errors.

## References

- Cargo `publish` flags (`--allow-dirty`): https://doc.rust-lang.org/cargo/commands/cargo-publish.html
- npm `version` (clean tree check, `--force`): https://docs.npmjs.com/cli/commands/npm-version
- setuptools-scm (dirty marks the version): https://setuptools-scm.readthedocs.io/
- ruff `--fix` and fix summary output: https://docs.astral.sh/ruff/linter/
- prettier `--check` / `--write`: https://prettier.io/docs/cli
- Terraform `-detailed-exitcode` and `fmt -check`: https://developer.hashicorp.com/terraform/cli/commands/plan
- Click variadic arguments (`nargs=-1`): https://click.palletsprojects.com/en/stable/arguments/
- Click exceptions and exit codes: https://click.palletsprojects.com/en/stable/exceptions/
- Repo: `freedom_ls/content_engine/management/commands/content_save.py`, `.../content_validate.py`, `freedom_ls/content_engine/validate.py` (`validate()`), `freedom_ls/base/git_utils.py`.

status: ok
