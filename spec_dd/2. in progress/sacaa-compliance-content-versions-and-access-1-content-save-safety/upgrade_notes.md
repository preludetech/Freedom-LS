---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: true
changed_packages:
  - "dulwich>=0.24.0"
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: content save safety

## Breaking changes

**`content_save` refuses content that is not committed to git.** Every source path must sit inside
a git working tree with at least one commit, and every file under it must be committed: modified,
staged, deleted and untracked files all block the save. Every file the save reads, and the
`.fls-content.yaml` at the content repo root, must be in the git index; a gitignored content file
is refused. The command exits 1 with a `CommandError` listing the files and writes nothing.
Deploy scripts or CI jobs that run `content_save` on a checkout with local changes, or on content
copied out of git (for example a tarball or a Docker layer without `.git`), now fail.

**`content_save` refuses content without uuids unless `--generate-uuids` is passed.** A plain run
used to write missing uuids back into the source files. Now it lists every item, question option
and category entry that lacks a uuid and stops. Run `content_save --generate-uuids <path> <site>`
once on new content, commit the changed files, then run plain `content_save` from then on.

`content_save <path> <site>` keeps its argument order. It now also accepts several source paths
before the site: `content_save <path1> <path2> <site>`. A path equal to or inside another is
refused.

Calling `save_content_to_db` directly is unaffected: it still defaults to `generate_uuids=True`,
performs no git check, and accepts a single path as before. The new `ignore=` keyword on `validate`,
`get_all_files`, `collection_children` and related functions in
`freedom_ls/content_engine/validate.py` defaults to an empty set.

## Manual steps

1. Run `uv sync` to install the new `dulwich` dependency.
2. Run `uv run manage.py migrate`. Migration
   `freedom_ls/content_engine/migrations/0015_contentsave_contentsavesource.py` adds the
   `ContentSave` and `ContentSaveSource` tables, which record each successful `content_save` run
   and the HEAD commit of every source path it loaded.
3. Check every place your project runs `content_save` (deploy scripts, CI, Makefiles, docs):
   - run it from a clean git checkout of the content repo, with `.git` present;
   - if content may still lack uuids, run once with `--generate-uuids` and commit the result
     before the deploy run.
4. Optional: list files and folders `content_save` and `content_validate` should leave out under
   `ignore:` in the `.fls-content.yaml` at the content repo root. Entries are exact POSIX paths
   relative to that root (no globs, no `..`). Ignored files still have to be committed.
5. With `settings.DEBUG` on, `content_save` now creates an `Organisation` for any unknown slug in
   a course's `organisations` or `shared_with` frontmatter. With `DEBUG` off it fails on an
   unknown slug as before. No action needed.
