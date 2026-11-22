# Research: reference implementations

Verification note: the dulwich docs page and PyPI pages could not be fetched in this run (404 / bot challenge). Facts below come from prior knowledge of these projects and are marked "(verify)" where a version, licence or exact API matters. Confirm before pinning.

## 1. Existing code in this repo

`freedom_ls/base/git_utils.py` already has a filesystem-only `get_head_commit(base_dir)`: resolves `.git` (including `gitdir:` worktree files), reads `HEAD`, follows `ref:` through loose refs, `commondir` and `packed-refs`. Gaps for this spec:
- It only looks at `base_dir / ".git"`, so a source path that is a subdirectory of a repo returns None. It needs an upward walk to find the repo root (what `git rev-parse --show-toplevel` and every tool below does).
- Does not handle a detached HEAD pointing at an annotated tag, or reftable repos (newer git `extensions.refStorage=reftable`). Both are rare; fail with a clear error rather than guess.
- No dirty-tree check exists. This is the hard part (section 2).

## 2. Detecting a dirty tree without a git binary

### How the tools do it
- **setuptools-scm, versioningit** (pure `git` subprocess): setuptools-scm runs `git status --porcelain --untracked-files=no` (note: ignores untracked files by default) and `git rev-parse HEAD`; dirty adds `.dYYYYMMDD` to the version. versioningit runs `git describe --dirty`-style commands. Both require the git binary, so they are not a model for the "no `git` binary" requirement, but they confirm the semantics: dirty = tracked-modified (plus staged); untracked is a separate opt-in. FLS needs untracked to count, so it must not copy setuptools-scm's `--untracked-files=no`.
  - https://github.com/pypa/setuptools-scm
  - https://github.com/jwodder/versioningit
- **dunamai**: shells out to `git status --porcelain` / `git describe`; `dirty` is a boolean in the output. Same conclusion. https://github.com/mtkennerly/dunamai
- **GitPython** (BSD-3, depends on `gitdb`, and **requires the git executable**): `repo.is_dirty(untracked_files=True)`, `repo.untracked_files`, `repo.head.commit.hexsha`. Ruled out by "does not depend on a `git` binary". https://gitpython.readthedocs.io/
- **dulwich** (Apache-2.0 or GPL-2.0-or-later dual licence (verify); pure Python, optional Rust extensions, only dependency is `urllib3`): no git binary needed. Relevant API:
  - `dulwich.porcelain.status(repo, ignored=False, untracked_files="all")` returns a `GitStatus(staged, unstaged, untracked)`. `staged` is a dict `{"add": [...], "delete": [...], "modify": [...]}` (index vs HEAD tree); `unstaged` is a list of paths whose working file differs from the index (modified or deleted); `untracked` is a list of paths not in the index and not ignored by `.gitignore`.
  - Mechanism: `dulwich.index.get_unstaged_changes(index, root_path)` walks the index entries, `lstat`s each file and compares size/mtime/mode, then hashes content when stat differs; `dulwich.porcelain.get_untracked_paths` / `get_untracked_paths` walks the tree, pruning by `.gitignore` (`dulwich.ignore.IgnoreFilterManager`); `tree_changes` compares index tree to HEAD tree for staged.
  - `Repo.discover(path)` walks upward from a subdirectory to the repo root, matching the "path may be a subdirectory" requirement. `Repo(path).head()` returns HEAD sha, handling packed refs, worktrees and symbolic refs.
  - https://www.dulwich.io/ , https://github.com/jelmer/dulwich , https://www.dulwich.io/docs/api/dulwich.porcelain.html (page 404 at fetch time; module docs also at https://dulwich.readthedocs.io/)
  - Caveat for the spec: dulwich honours `.gitignore`, so a gitignored file under the path is not "untracked". That matches `git status` and is the right behaviour (gitignored build junk should not block a save), but the spec should say so. Another caveat: dulwich's stat-based modified detection is only as good as the index; it is the same as git's racy-index behaviour and is fine.
  - Scoping to a subdirectory: dulwich status is whole-repo. Filter the returned paths by prefix of the source path relative to the repo root. The idea says "nothing under the path may be uncommitted", so changes elsewhere in the repo must not block the save. Note this also means the ignore list (exempt from validate/save but NOT from the clean check, per answers.md) applies to nothing in the git check; do not filter by it.
  - Dependency weight: one pure-Python package plus urllib3 (already ubiquitous). Moderate. The alternative is hand-rolling index parsing (see below), which is not recommended.

### Hand-rolling (the repo's current style)
The existing reader parses `HEAD`/refs by hand. A hand-rolled dirty check needs: parse `.git/index` (binary, versions 2/3/4, extensions, path-prefix compression in v4), stat/hash every file, read HEAD commit's tree (zlib loose objects and packfiles with delta resolution) to compare index to HEAD, plus `.gitignore` and `info/exclude` and global excludes for untracked. That is reimplementing dulwich. Recommendation: use dulwich for the clean check, and either keep `get_head_commit` for HEAD (extended with an upward repo discovery) or use `Repo.discover(path).head()` for both so there is one code path. Using dulwich for both is simpler and covers packed refs/worktrees that the hand-rolled reader handles only partly.

Recommended pinned usage: `Repo.discover(path)`, `porcelain.status(repo)`, flatten staged+unstaged+untracked (decode bytes to str; staged entries are bytes, untracked are str paths on newer versions (verify)), keep those whose repo-relative path starts with the source path's repo-relative prefix, report all of them together.

## 3. Recording the git commit of content

- **Hugo `enableGitInfo`**: runs `git log` per content file to populate `.GitInfo` (hash, abbreviated hash, author, commit date, subject). Per-file, requires binary, not a whole-site HEAD. Confirms that commit-per-content is a normal idea, but FLS records per save and per path, which is simpler. https://gohugo.io/methods/page/gitinfo/
- **Docusaurus**: `showLastUpdateTime` / `showLastUpdateAuthor` shell out to `git log -1 --format=...` per file. Same pattern; a documented gotcha is shallow clones in CI giving wrong results. FLS only reads HEAD so shallow clones are not a problem. https://docusaurus.io/docs/api/plugins/@docusaurus/plugin-content-docs
- **MkDocs `mkdocs-git-revision-date-localized-plugin`** (MIT, uses GitPython): per-page last commit date; falls back to build time when file is untracked; offers a strict mode that errors outside git. Takeaway: tools that silently fall back on dirty or untracked files give false provenance, which is exactly what the spec avoids by refusing dirty trees. https://github.com/timvink/mkdocs-git-revision-date-localized-plugin
- **setuptools-scm / dunamai** embed `HEAD` sha plus a dirty flag into the artifact. The idea refuses dirty trees instead of recording a dirty flag. An alternative worth noting for the spec: record `commit` only after the clean check, and expose that `--generate-uuids` and image manifests make the tree dirty *after* the save, so the recorded commit is the pre-write state, not a commit that contains the written uuids. The spec should say this explicitly: the recorded commit does not contain the uuids written by that same run, so a run with `--generate-uuids` should perhaps record nothing or be flagged (Open question for the spec; the idea does not settle it).

## 4. Validate-then-write

- **Django fixtures `loaddata`**: reads all fixture objects, then saves them inside one `transaction.atomic` with constraints deferred; failure rolls back everything. Covers the DB only; files are not involved. FLS's requirement ("before any write", including source files and file storage) is stricter, so the pattern is: pass 1 parse and collect all errors into one list (no writes), pass 2 write inside `transaction.atomic`. https://docs.djangoproject.com/en/stable/ref/django-admin/#loaddata
- **Django `makemigrations --check` / `migrate --plan`**: a dry-run style that reports without writing; shows an established flag vocabulary (`--check`, `--dry-run`).
- **Terraform plan/apply**: plan computes the full change set with no side effects; apply executes. Plan failures (missing required values) are reported in aggregate. Takeaway for the spec: collect all missing uuids across all paths in the parse pass and raise one `CommandError` listing path + file + entity. https://developer.hashicorp.com/terraform/cli/commands/plan
- **Open edX OLX import / Moodle backup restore**: OLX import (`import_olx` / `import_from_xml`) parses the course tree and writes to the modulestore as it goes, with failures partway leaving partial courses (known weakness); Moodle restore runs a precheck stage (checks the backup and warns) before the execute stage, and executes in a DB transaction. The precheck/execute split is the pattern to copy. https://docs.openedx.org/ , https://docs.moodle.org/en/Restore_course
- **File writes in the same pass**: because write-back of uuids and image manifests touches files, the safe order is validate everything, then DB transaction, then file writes after commit (or write files last, accepting that a crash after DB commit leaves uuid-less files, which a rerun with `--generate-uuids` heals). Writing files inside the transaction with rollback is not possible, so ordering is the only guard. Worth stating in the spec.

## 5. Missing ids and generate-id flags

- **Contentful migrations / Sanity**: Contentful migrations are explicit scripts keyed by content type ids chosen by the author; Sanity requires `_id`s in `sanity dataset import` ndjson, otherwise generates them on import (documents without `_id` get random ones, so re-import duplicates). That is the failure mode the spec avoids. https://www.contentful.com/developers/docs/tutorials/cli/scripting-migrations/ , https://www.sanity.io/docs/cli-reference/dataset-import (verify)
- **Alembic `--autogenerate`, Django `makemigrations`, Rails `rails g`**: ids/files are generated only on an explicit authoring command, never on the deploy command. Maps to `--generate-uuids` (authoring) vs a plain run (load) failing.
- **Terraform `import` / `moved` blocks**: stable identity is declared in source, and the tool refuses to guess. Same principle.
- **Flag convention**: `--generate-uuids` default False, aggregate error list, exit non-zero with `CommandError`. Management commands use `parser.add_argument("--generate-uuids", action="store_true")`.

## 6. Ignore lists: gitignore-style vs exact paths

- **`.dockerignore`**: gitignore-like patterns (globs, `**`, `!` negation), matched against paths relative to the build context; last matching rule wins. Source of many "surprising match" bug reports.
- **`pathspec`** (MPL-2.0 (verify), pure Python, no dependencies, `GitIgnoreSpec` / `PathSpec.from_lines("gitwildmatch", lines)`; used by black, mypy, yamllint (verify)): the standard library for gitignore patterns. Weight: small, pure Python, but MPL-2.0 is file-level copyleft, fine for use as a dependency.
- **Exact paths** (this spec): `ignore: [CLAUDE.md, claude.sh]`, "match exact paths to files and folders". Implementation is trivial and needs no library: normalise each entry (strip leading `./` and trailing `/`, reject absolute paths and `..`), and then a file is ignored if its repo-root-relative POSIX path equals an entry or has an entry as a parent directory (`path == e or path.startswith(e + "/")`). Use `PurePosixPath` parts comparison rather than string prefix to avoid `docs` matching `docs-old`. Recommendation: do not add `pathspec`; exact match is simpler, predictable and was the stated choice. Entries relative to the git repo root (per answers.md), while a source path may be a subdirectory: compute each file's path relative to the repo root before comparing. Wildcards in an entry should be an error (or a literal), not silently a glob; the spec should pick one. Warn or fail on entries that match nothing (typo detection), as `.dockerignore` and gitignore never do, but linters like yamllint do for unused rules.
- Ignored paths are exempt from content validation/saving only, not from the git clean check (answers.md). Dulwich status covers this naturally: do not filter by the ignore list in the git check.

## 7. Recommendations summary

1. Git clean check and HEAD: use dulwich (`Repo.discover`, `porcelain.status`, `repo.head()`), scoped to paths under the source path. No git binary, handles worktrees, packed refs and subdirectories. Dual-licensed Apache-2.0/GPL-2.0+ (verify), pure Python, one dependency (urllib3). Alternative: keep hand-rolled HEAD reader and add upward discovery, but do not hand-roll the dirty check.
2. Two-pass save: parse and validate every path, collect all errors (git dirty paths first, then missing uuids, then duplicate relative paths across paths), raise one aggregated `CommandError`; then DB write in one `transaction.atomic`; write files (uuid write-back, manifests) last.
3. One save record: site, timestamp, one commit per path. Decide what to record when `--generate-uuids` is used (the recorded commit will not contain the written uuids).
4. Ignore list: exact path matching on repo-root-relative POSIX paths, no `pathspec`.
5. Do not copy setuptools-scm's `--untracked-files=no` default; untracked files must fail.

status: ok
