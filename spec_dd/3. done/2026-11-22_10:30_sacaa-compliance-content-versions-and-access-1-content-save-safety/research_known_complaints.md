# Research: known complaints about this kind of work

Scope: what users complain about in tools that gate on a clean git tree, read git state in pure Python, write ids back into source files, fail on missing ids, import all-or-nothing, and use ignore lists. Each section ends with the mitigation for `content_save`, which must leave its own image cache manifests and generated uuids uncommitted after a run.

Evidence quality: only three web searches were run in this pass. Items marked (sourced) rest on a fetched result. Items marked (general knowledge) are well-known git behaviour I did not re-verify here; treat them as lower confidence.

## 1. Clean-tree gates: false positives

- **Line endings / autocrlf / .gitattributes (sourced).** Files show as modified straight after clone because a `.gitattributes` `text`/`text=auto` rule (even in a subdirectory) overrides client `core.autocrlf`, or because CRLF is stored in the index and gets re-normalised. Diagnosis is `git diff -w` and `git ls-files --eol`; the fix is `git add --renormalize .`. Tools disagree: one GUI showed modified files that command-line status did not.
  - https://support.atlassian.com/bitbucket-data-center/kb/git-status-shows-as-files-modified-directly-after-clones/
  - https://docs.github.com/en/get-started/git-basics/configuring-git-to-handle-line-endings?platform=windows
  - https://lore.kernel.org/git/20220421143931.o53dm2qnfcpsido7@tb-raspi4/
  - Mitigation: a filesystem-only reader that hashes working files must apply the same clean filters (eol conversion per `.gitattributes`/`core.autocrlf`) as git, or it will report false dirt on Windows checkouts. Either implement that conversion or, when a mismatch is found, compare content after normalising line endings and say so in the message. The failure message should name each file and the reason (modified / untracked / deleted), so an author can tell a real edit from a line-ending artefact.
- **File mode (general knowledge).** `core.fileMode=false` on Windows/WSL/mounted volumes; the exec bit differs between checkout and index. Mitigation: honour `core.fileMode` from repo config, otherwise ignore mode-only changes.
- **Stat-cache staleness (general knowledge).** The index stat data (mtime, size, inode) goes stale after a copy, container mount or `touch`; a reader that trusts stat data wrongly reports dirty, one that never re-hashes wrongly reports clean. Mitigation: when stat differs, re-hash content and compare to the index entry before declaring dirty; never use stat equality alone to declare clean when the check is a compliance gate.
- **Gitignored files and tool-written caches (general knowledge, applies directly).** Users of lint/format/CI gates complain when the tool's own output (caches, `.pyc`, build dirs) trips the gate, or conversely when an ignored file silently changes content. Mitigation here: the image cache manifests the command writes must either be committed by the author as expected (spec's stated behaviour) or sit under a path the `.gitignore` covers; the check must run before any write, so the command never trips on its own output within one run. Decide explicitly whether gitignored files count (git's own `status` ignores them); the answers say an ignored FLS path is still checked, so the message must distinguish "ignored by `.fls-content.yaml`" from "ignored by git".
- **Submodules, worktrees with a `.git` file, shallow clones, detached HEAD (general knowledge).**
  - Worktree and submodule checkouts have `.git` as a file (`gitdir: ...`), not a directory; naive `Path(".git").is_dir()` code fails. Mitigation: parse the `gitdir:` pointer, follow `commondir` for worktrees, and resolve HEAD and index from the right gitdir. This repo itself is a linked worktree, so this is a live case.
  - A submodule path inside a source tree shows as one entry whose state depends on the submodule's HEAD; a pure-Python reader often mishandles it. Mitigation: treat submodule entries as unsupported with a clear message, or skip them.
  - Shallow clones: HEAD is still readable from refs; only history is missing. The command needs only the HEAD sha, so it works, provided the reader does not walk parents. CI checkouts of a detached HEAD must be accepted: read HEAD as a sha when it is not `ref: ...`. Packed refs (`packed-refs`) must be read too.
  - Mitigation for all: test against a fixture matrix (plain repo, subdirectory path, linked worktree, detached HEAD, packed refs, submodule, shallow).

## 2. Dulwich / pure-Python status slow or wrong

- **Slow (partly sourced).** No benchmark of current dulwich `porcelain.status` was found. A Klaus maintainer said dulwich was an order of magnitude slower than native git when first used, with no current numbers; the dvc project also tracked a dulwich git performance issue.
  - https://www.github.com/jonashaag/klaus/issues/258
  - https://lightrun.com/answers/iterative-dvc-git-performance-issue-in-dulwich
  - https://github.blog/engineering/improve-git-monorepo-performance-with-a-file-system-monitor/ (why native status is slow on big trees: it must walk the whole worktree)
  - Mitigation: scope the check to the source path, not the repo root, as the idea already does; use the index entries to skip hashing when stat matches and size is equal; benchmark on a content repo of realistic size before choosing. Content trees (markdown plus images) are small, so this is low risk unless the path is a whole monorepo.
- **Wrong (general knowledge).** Pure-Python implementations historically diverged on: eol filters, sparse checkout, `index` v4 / split index / untracked cache extensions, and `.gitignore` edge cases (negation, nested ignore files, `core.excludesFile`, `.git/info/exclude`). Mitigation: fail closed on an index version or extension the reader does not understand rather than guessing; document supported cases.
- The existing `freedom_ls/base/git_utils.py` filesystem reader should get the same treatment: untracked detection needs ignore rules, and ignore rules are the part most likely to be wrong.

## 3. Tools that write ids back into source files

General knowledge (no fetched source): complaints are consistent across tools that annotate source (Jupyter cell ids, translation catalogs, Obsidian/Notion-style frontmatter ids, ORM fixtures).
- **Noisy diffs / forgotten commits.** Authors run the tool, ids appear, and they forget to commit; a teammate then runs the tool and generates different ids for the same item. Mitigation: this spec's design (fail on missing id unless `--generate-uuids`, then dirty tree forces a commit before the next save) addresses it. Print a summary at the end: "N uuids written to files X, Y; commit them before the next save".
- **Merge conflicts.** Two branches each add an item and each generated ids in adjacent frontmatter lines; or two authors generate ids for the same item. Mitigation: write the id at a stable position (top of frontmatter, one line, one key per line) so diffs are one-line and conflicts are rare; never rewrite or reformat the rest of the file (preserve comments, key order, quoting, line endings); make writing idempotent and byte-stable.
- **Duplicated ids from copy/paste.** An author copies a file to make a new one and keeps the uuid. Mitigation: detect duplicate uuids across all paths in the validation pass and report all of them together.
- **Formatter/line-ending churn.** Writing back with a YAML round-trip can reformat the file and produce a diff far larger than the id. Mitigation: textual insertion, or a round-trip-preserving library, plus a test that only the id line changes.
- **Cache manifests.** The image cache manifest is a tool-generated artefact in the author's tree; users dislike committing generated files. Mitigation: keep manifests deterministic (sorted keys, no timestamps) so re-runs without image changes produce no diff, and document that they are to be committed.

## 4. Missing-id failures that are hard to fix

General knowledge from validators that report one error at a time or without location.
- Complaints: error names the model but not file and line; stops at the first; tells the author to "add a uuid" without saying how.
- Mitigation: report all missing ids together (already in the idea), each as `path:entity-kind:title` (for nested things like `QuestionOption` and `COURSE_CATEGORIES` entries include parent and position), and end with the exact remedy: "run again with `--generate-uuids`, review, and commit". Group by file. Exit non-zero with nothing written, and say so ("no files, database rows or storage were changed").

## 5. All-or-nothing imports that hide the failing item

- Complaint pattern (general knowledge): a transaction rolls back and the user sees only the final exception, often a database integrity error, with no pointer to the source item. Related: validation finds only the first error, so fixing takes many round trips.
- Mitigation: validate every path fully before writing and collect all errors with file path and item; wrap the write phase in one transaction and, on failure, re-raise with the item being processed; keep file storage writes after the database write or make them undoable so "refuses to write anything" holds for storage too. Multi-path adds a new complaint: which path failed, so prefix every message with the path argument as the author typed it. The duplicate relative `file_path` across paths case must name both paths.

## 6. Ignore-list semantics surprises

- **Regex vs glob (sourced).** pre-commit style `exclude` is a regex with search semantics (matches anywhere unless anchored with `^`/`$`), so an exclude can catch far more than intended; patterns are relative to the config's directory, which is not always the repo root; `check-useless-excludes` exists because patterns that match nothing go unnoticed. Explicitly passed files can bypass an exclude (the Black/Ruff `force-exclude` complaint).
  - https://prek.j178.dev/reference/configuration/
  - https://github.com/psf/black/issues/438
  - https://sources.debian.org/src/pre-commit/4.5.1-1/pre_commit/meta_hooks/check_useless_excludes.py
  - https://www.scivision.dev/pre-commit-exclude-files/
- **Directories, relative-to-what, gitignore-style (general knowledge).** Users expect `.gitignore` semantics (trailing slash for dirs, `*` globs, anchoring) and are surprised by exact-only matching; they are equally surprised when an ignored directory entry does not cover files under it, or when paths are relative to the cwd rather than the repo root. Windows separators and case sensitivity cause misses.
- Mitigation for `.fls-content.yaml`: the answers fix entries as exact paths relative to the repo root holding the source path, matching files and folders. Make that unambiguous:
  - a folder entry ignores everything beneath it (state this in docs and test it);
  - normalise `/` separators, strip a leading `./` and a trailing `/`, and reject entries with `..`, absolute paths or glob characters with a clear message rather than treating them as literal;
  - fail (or warn) on an entry that matches nothing, as `check-useless-excludes` does, so typos do not silently stop ignoring;
  - state in the success output how many paths were ignored;
  - say plainly that ignore exempts a path from FLS validation and saving only, not from the git clean-tree check (per answers.md), and make the dirty-tree message for an ignored path say "ignored by `.fls-content.yaml` but still must be committed", otherwise it will be reported as a bug;
  - one reader for the file shared by `content_save`, `content_validate` and the offline validator, so all three agree (answers.md requires this), and a missing file is an empty list in Django while still required offline.

## Summary mitigations specific to the dirty-after-run requirement

1. Run the git check first, before any write, so the command never fails on its own output within a run.
2. Print what was written and tell the author to commit it; consider a `--dry-run` style report only if later asked for (not requested here).
3. Make generated output byte-stable and minimal so the commit is small and re-runs produce no diff.
4. Record the HEAD sha as it was when the check passed, and say in docs that it identifies the content before generated writes, so uuids committed afterwards belong to a later commit (worth deciding explicitly in the spec; a question version traceable to a commit that lacks the uuid is a likely audit complaint).

status: ok
