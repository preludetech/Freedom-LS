# Content save safety

Spec 1 of 5 in the SACAA content versions and access effort. Read the "SACAA content versions and access" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

`content_save` becomes safe to run against real content. It takes several source paths in one call. It refuses to write anything unless every path is a clean git working tree. It refuses to write anything when a uuid is missing, unless the author passes `--generate-uuids`. In development (`settings.DEBUG`) it creates an `Organisation` that course frontmatter names and that does not exist yet. It records the HEAD commit of each path for the save.

## Why

A content save today writes uuids into the author's files, accepts one path, and takes whatever is on disk, committed or not. For SACAA compliance the question text a learner saw must be traceable to a committed state of the content, and a forgotten uuid must not silently become a new row. The two later specs that change `content_save` (`sacaa-compliance-content-versions-and-access-2-retire-removed-content` and `sacaa-compliance-content-versions-and-access-3-question-versions`) build on this one: retirement needs the command to take every path of a site's source, and question versions read the recorded commit.

## What is settled

### Missing uuids

- `content_save` gains `--generate-uuids`, default False.
- With the flag off, the save fails before any write when any uuid is missing. "Before any write" covers the database, the source files and file storage. All missing uuids are reported together, not one at a time.
- The check covers every entity that gets a uuid written back today: Topic, Activity, Article, Course, CoursePart, Form, FormPage, FormContent, FormQuestion, every `QuestionOption`, and every entry in a `COURSE_CATEGORIES` document (`CourseCategory`).
- With the flag on, behaviour is today's: uuids are written into the source files during the save. This is the authoring workflow.
- Every content item the project ships in `demo_content/` carries all its uuids, so the demo content loads with the flag off.
- The docs and the `fls-content` plugin that say the first `content_save` writes uuids back are changed to say the author runs it with `--generate-uuids`, and that a plain run fails on a missing uuid.

### Several paths

- `content_save` takes one or more source paths and one site. A single path keeps working.
- One call is one save for the site. All paths are parsed, checked and validated before anything is written, so a failure in any path writes nothing.
- Each path has its own image cache manifests, kept under that path as today.

### Git check

- Every path must lie inside a git working tree, and nothing under the path may be uncommitted or untracked. A path may be a subdirectory of the repository, not only its root.
- The check reads the directory only. It does no fetch, push, remote or upstream comparison, and it does not depend on a `git` binary being installed.
- The check is always enforced, with `settings.DEBUG` on or off.
- The check belongs to the command. `save_content_to_db` does not check git, because tests and downstream callers load from temporary directories.
- A save run with `--generate-uuids`, or one that writes image cache manifests, leaves the tree dirty afterwards. That is expected; the author commits the result before the next run.
- The HEAD commit of each path is recorded for the save. `sacaa-compliance-content-versions-and-access-3-question-versions` reads it when it records a question version.
- The git check runs before the uuid check, so a dirty tree is reported first.

### Debug organisations

- When `settings.DEBUG` is on and a course's `organisations` or `shared_with` frontmatter names an organisation slug that does not exist on the site, the save creates the `Organisation`. Its name is derived from the slug.
- With `settings.DEBUG` off, an unknown organisation slug fails the save as it does today.

## Open until the spec

- **Signature of `save_content_to_db`.** Whether it takes the several paths, the flag and the recorded commits, and which of the three the command handles alone. Recommendation: it takes the flag and defaults it to True so existing callers and tests that load uuid-less temporary files keep working; the command passes the flag through, sets it from the command line (default False), does the git check, and hands the commits to the function. Tests of the new default exercise the False path explicitly.
- **Where the recorded commit is stored.** Recommendation: one record per save holding the site, the time, and one commit per path, so a question version can point at the save that wrote it.
- **Where the uuid check sits.** In the validation pass shared with `content_validate`, or only in the save. Recommendation: only in the save path, so `content_validate` and the offline `fls-content` validator keep accepting uuid-less authoring work.
- **Command argument order.** Recommendation: paths first, site name last, so existing single-path invocations keep working.
- **Keying of `file_path` across paths.** `File.file_path` and each model's `file_path` are relative to the one path today. Recommendation: keep them relative to their own path, and fail the save when two paths yield the same relative path for the same site.
- **Name derived from the slug.** Recommendation: replace hyphens and underscores with spaces and capitalise the words of the slug.
- **Reading the commit without `git`.** Recommendation: extend the filesystem-only reader in `freedom_ls/base/git_utils.py` to take a directory, the same way the clean-tree check reads the working tree.

## ignored files

`.fls-content.yaml`

Add an ignore list here. Match exact paths to files and folders.
Eg.

```
ignore:
- CLAUDE.md
- claude.sh
```

## Out of scope

- Retiring content removed from the source, and the rule that one call covers the site's whole source: `sacaa-compliance-content-versions-and-access-2-retire-removed-content`.
- Question versions, and anything that stores or shows them: `sacaa-compliance-content-versions-and-access-3-question-versions`.
- Checking that a path is pushed, has a remote, or is in step with an upstream.
- Changing what `content_validate` checks.

## Resources

- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_content_save_pipeline.md`
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/idea.md`
- `docs/product/content-editing-workflow.md` and the `claude_plugins/fls-content` skills, which describe uuid write-back today.
