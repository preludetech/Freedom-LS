# Committing an SDD artifact

Every command that writes or edits an SDD artifact ends by committing and pushing it, unasked.

The caller supplies a `<summary>`: a few words for what it produced, e.g. `write the spec`,
`review the plan for security`.

## Step 1: Check the branch

```bash
git rev-parse --abbrev-ref HEAD
```

If the branch is `main` or `master`, stop. Do not commit and do not push. Say the artifact is
uncommitted and why.

## Step 2: Stage the artifacts

Stage the files this command wrote or changed, by path. Never `git add -A` or `git add .`; the
working tree may hold implementation work that is not yours to commit.

If nothing is staged (the normal outcome of a re-run that changed no files), say so and stop.

## Step 3: Commit

The subject names the spec first, so `git log` reads as a per-spec history:

```
<spec name>: <summary>
```

`<spec name>` is the spec directory's folder name, e.g. `interested_login: write the spec`.

Commit with `uv run git commit`. The `uv run` prefix is required by `CLAUDE.md`: the
pre-commit hooks live in the uv environment.

If a hook rewrites a file, re-stage it and commit again. If a hook fails on something you did not
touch, stop and report it rather than fixing unrelated code.

## Step 4: Push

```bash
git push
```

If the branch has no upstream, use `git push -u origin HEAD`.

If the push is rejected because the remote has moved on, report that and leave it. Never force-push.
