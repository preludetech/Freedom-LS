# Research: best practices for content save safety

Sources: prior knowledge of git internals and the dulwich/pygit2/GitPython projects, plus a read of `freedom_ls/base/git_utils.py` (not web-fetched this run; no URLs were verified live). Reference URLs are for the reader to confirm.

## 1. Reading git state from disk

Existing code: `freedom_ls/base/git_utils.py` already resolves `.git` (file or dir), `commondir`, loose refs, packed refs and `get_head_commit(base_dir)`. So the HEAD part is largely done; the gap is the clean-tree check.

Facts to handle:
- `.git` may be a file `gitdir: <path>` (linked worktree, submodule). Path may be relative to the file's directory. Linked worktree gitdir has `commondir` pointing at the main `.git`; refs/packed-refs live in commondir, but `HEAD` and `index` live in the per-worktree gitdir. Submodule gitdir lives at `<super>/.git/modules/<name>`.
- HEAD is either `ref: refs/heads/x` or a bare SHA (detached). Lookup order: loose ref file, then `packed-refs` (lines `<sha> <ref>`, `^` lines are peeled tags, `#` header). Unborn branch (ref absent): treat as an error, not "clean".
- SHA-256 repos exist (64 hex); do not hardcode 40.
- The path given may be a subdirectory: walk upward to find `.git`; the repo root is where `.git` was found. Index paths are relative to the worktree root, so convert the subdirectory to a prefix.
- `GIT_DIR`/`GIT_WORK_TREE` env vars and `core.worktree` can redirect; decide explicitly to ignore them and say so.
- `git status` semantics also depend on `.git/info/exclude`, `core.excludesFile`, nested `.gitignore` files, `core.autocrlf`, `core.filemode`, sparse checkout, `assume-unchanged`/`skip-worktree` bits. A hand-rolled check will not match all of these.

## 2. Dulwich vs hand-rolled

- **dulwich** (pure Python, Apache-2.0/GPL-2+): `dulwich.porcelain.status(repo)` returns staged changes, unstaged changes, and untracked files; `dulwich.repo.Repo(path)` handles `.git` files, worktrees, packed refs, `repo.head()`. `porcelain.status` honours gitignore via `dulwich.ignore`. It is optional-C-extension, installs without a git binary. Trade-offs: new dependency; dulwich status does stat/index comparisons and has had edge-case bugs (symlinks, filemode, line-ending normalisation); `Repo(path)` discovers only at the given path unless `Repo.discover` is used (use `discover` or `porcelain.open_repo_closing` with a walk-up).
- **pygit2** needs libgit2 (binary wheels exist) - accurate `status()` but a native dependency; **GitPython** shells out to `git`, ruled out by the requirement.
- **Hand-rolled**: parse index v2-4 (header `DIRC`, entries with ctime/mtime/dev/ino/mode/uid/gid/size/sha/flags, v4 path prefix compression, extensions, trailing checksum), hash each working file as a blob (`sha1("blob <len>\0"+content)`) and compare with index sha, then walk the tree for untracked files while applying ignore rules. The ignore-rule engine (wildmatch, negation, directory-only patterns, precedence) is the hard part. Also needs "index vs HEAD tree" comparison to detect staged-but-uncommitted changes, which needs reading tree objects from loose/packed (delta-resolved) objects. That is a lot of code for an audit-critical check.
- **Recommendation**: for audit-grade correctness use dulwich (porcelain.status or index + `dulwich.index.get_unstaged_changes` + `dulwich.ignore.IgnoreFilterManager`), wrapped in one small function in `git_utils.py`, keeping the existing hand-rolled HEAD reader or replacing it with `Repo.head()`. If a new dependency is refused, hand-roll only the conservative version below and document the limits.

### Conservative hand-rolled design (fail closed)
Principle: when unsure, report dirty/error, never clean.
1. Index entries vs HEAD tree: every index sha must equal the HEAD tree entry (catches staged changes). Requires tree-object reading; if objects are in packfiles, needs pack parsing: this is the expensive part. Cheaper stand-in: not possible without objects, so this alone favours dulwich.
2. Working file vs index: compare content hash, not just mtime/size. Stat data is a cache (git's "racily clean" problem: files modified in the same timestamp tick as the index write); a stat match does not prove clean, a stat mismatch does not prove dirty (touch, checkout). For audit use, hash everything under the path (content small) and ignore stat cache entirely. Also compare mode (executable bit) unless `core.filemode=false`; symlinks hash their target text.
3. Untracked: any file under the path not in the index. Whether gitignored untracked files count: see section 3.
4. Deleted tracked files and files in index with intent-to-add/conflict stages (stage != 0) are dirty.

## 3. Dirty-check semantics

- Git's own `git status --porcelain` treats gitignored files as clean (not reported without `--ignored`). Matching that is the least-surprising default, but it opens a hole: an ignored file under the content tree that the loader reads (e.g. a `.md` matched by a stray `.gitignore` rule) would be loaded yet not be in the committed state. Best practice for traceability: after the dirty check, verify that every file the loader will read is tracked in the index (and matches HEAD). That closes the gap regardless of ignore rules and removes the need for a full ignore engine for loaded files. Ignored non-content files (build artefacts, `__pycache__`) can then be tolerated or not, as a choice.
- The idea's `ignore:` list (exempt from loading, not from the git check, per answers.md) is a different thing from `.gitignore`: do not conflate them. Exact paths relative to repo root, normalised (posix separators, strip `./`, trailing `/`), match file or directory prefix by path component (so `docs` does not match `docs2`). Fail on entries that do not exist or on non-string/absolute/`..` entries to catch typos silently ignoring nothing. Reject path traversal and symlinks escaping the root.
- Untracked directories containing only empty dirs are invisible to git; ignore empty directories.
- Case-insensitive filesystems and Unicode normalisation (macOS) can make index paths differ from disk names; compare with the filesystem's actual names.
- Submodules inside the tree: a submodule shows as a gitlink entry (mode 160000); its inner dirtiness is separate. Decide: treat a gitlink as opaque, or recurse. State it.
- Report all offending paths together (capped, with count), grouped as modified / staged / deleted / untracked, so the author fixes in one pass.
- Scope: check the whole working tree or only the given subdirectory? The idea says "nothing under the path"; check only under the path prefix (plus verify HEAD exists), noting a dirty file elsewhere in the repo does not affect the content.

## 4. All-or-nothing across several paths

- Validate-then-write: phase 1 per path and all paths: git check, parse, uuid-missing scan, schema validation, cross-path collision checks (same relative `file_path` for the same site), organisation lookup. Collect errors into one list across all paths; raise once. Phase 2: writes. This matches the idea ordering (git before uuid).
- DB: one `transaction.atomic()` around the whole save for all paths, so any exception in phase 2 rolls back the DB. Use `ATOMIC_REQUESTS`-independent explicit atomic; careful with `select_for_update`/long locks on the site.
- Non-DB side effects (file storage, writing uuids back into source files, image cache manifests) are not rolled back by the DB transaction. Established patterns: (a) defer them until after DB success via `transaction.on_commit` (runs only if the outer atomic commits; failure inside on_commit callbacks does not roll back, so they must be idempotent and retry-safe); (b) stage to temporary names/paths and atomically publish (`os.replace` is atomic within one filesystem; write temp file in the same directory, fsync, then rename); (c) for storage, upload content-addressed or under a save-id prefix so a failed run leaves only orphans that are harmless and garbage-collectable, never overwriting live files.
- With `--generate-uuids`: generate all uuids in memory first, validate, write DB, then write files last (or via temp + replace), since source files are the one thing that can leave a dirty tree. Note the idea accepts a dirty tree afterwards.
- Avoid a TOCTOU gap between git check and read: read each file once, hash it, and compare to the index/HEAD blob hash at load time, or re-run the clean check after parsing and before commit. Cheap and strong: record per-file blob hashes during load and confirm HEAD unchanged at the end.
- Test the failure modes: error in path 2 leaves nothing from path 1 (DB rows, files, storage); mid-write exception rolls back DB.

## 5. Stable identifier hygiene (content-as-code)

- Identity must live in the content (frontmatter uuid), never in the path or title, so renames/moves do not create new rows. Same approach as Sphinx-intl/Hugo `uuid` or Docusaurus `id`, Open edX OLX `url_name`, and Moodle/IMS CC identifiers.
- Generate only in an explicit authoring step (the `--generate-uuids` flag is that), and prefer random UUIDv4 (or v7); never derive from title so edits don't change identity.
- Detect: duplicate uuids across files (copy-paste of a file duplicates identity, the most common failure), uuid format validity, a uuid reused for a different entity type. Report all, fail the save.
- Detect "uuid changed" cases: uuid present in DB for a path that now has a different uuid is a silent fork. Retirement (spec 2) handles removal; a check for rename detection is useful.
- Pre-commit/CI lint that rejects uuid-less content so missing uuids are caught before review, and a `git` hook is not required for the command.
- Report missing uuids with file path plus entity type and a location (title or line) for each, all at once.

## 6. Audit traceability records

- One immutable save record: site, started/finished UTC time, per-path: path as given, repo-root-relative subpath, HEAD commit sha (full), branch or detached marker, remote URL optional (explicitly out of scope), the `.fls-content.yaml` ignore list used, flags used (`generate_uuids`), tool version, executing user (`getpass`/Django user if available), and counts of created/updated rows.
- Record the full 40/64-char sha, never a branch name (branches move). Consider recording the tree sha too, which identifies content independent of commit metadata, and per-file blob shas for the loaded files to prove each loaded file equals the committed one.
- Make records append-only (no update/delete in admin, model `save` guard, or DB permission) because they are audit evidence. Link content rows and, later, question versions to the save record by FK (matches the idea's recommendation).
- If `--generate-uuids` or manifests dirty the tree, the recorded commit does not contain the written uuids; mark the save record accordingly (e.g. `generated_uuids=True`) so an auditor knows the loaded state differs from HEAD, or better, refuse to treat such a save as audit-grade until the author commits and re-runs clean. Strong practice: audit-grade saves run only with the flag off.
- Write the record inside the same DB transaction as the content so a rolled-back save leaves no record and a committed save always has one.

## 7. Suggested decisions for the spec

1. Use dulwich for dirty-check and HEAD, behind a single `git_utils` wrapper, unless a dependency is unacceptable; otherwise hand-roll fail-closed with content hashing and explicit documented limits.
2. Do not rely on stat cache; compare content hashes. Treat staged, modified, deleted, conflicted and untracked as dirty.
3. Additionally require every loaded file to be tracked and equal to HEAD, which sidesteps gitignore ambiguity.
4. Handle `.git` file, commondir, packed refs, detached HEAD, unborn HEAD (error), subdirectory paths.
5. Two-phase save, single `atomic()`, file/storage side effects after DB success via `on_commit` or temp-and-replace; collect all errors across all paths.
6. Strict `ignore:` parsing (exact normalised paths, component-wise, error on unknown/escaping entries).
7. Save record with full sha per path, flags, ignore list, append-only, created in the same transaction.

## Reference URLs
- https://git-scm.com/docs/index-format
- https://git-scm.com/docs/gitrepository-layout
- https://git-scm.com/docs/git-worktree
- https://git-scm.com/docs/gitignore
- https://git-scm.com/docs/racy-git
- https://www.dulwich.io/docs/
- https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit
- https://docs.python.org/3/library/os.html#os.replace

status: ok
