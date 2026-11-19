## Step 3: Upstream-change scan

Resolve `PLUGINS_ROOT` by "The `PLUGINS_ROOT` rule" in
`claude_plugins/sdd/commands/protected/pre_step_rebase.md`. The script is
`<PLUGINS_ROOT>/claude_plugins/sdd/scripts/upstream_change_scan.sh`.

```
mkdir -p .sdd-work
<script-path> <old-base> origin/main "<spec-dir>" > .sdd-work/rebase_upstream_scan.md
```

Delete any `.sdd-work/rebase_upstream_review.md` left by an earlier rebase, by name: a stale review
must never be reused against a different scan.

- exit 0 or 3 → delete `.sdd-work/rebase_upstream_scan.md` by name. `status: ok · rebased: yes`.
  Stop. Exit 3 means every upstream path sits under the spec root: no worker, no pause.
- exit 2 → go to Step 4.
- any other exit → `status: failed · reason: upstream-change scan exited <code>: <its stderr>`.
  The caller stops.

## Step 4: Upstream-change review

If `.sdd-work/rebase_upstream_review.md` exists and ends `status: ok`, this is a resumed run:
reuse it and go to Step 5.

Otherwise spawn **one** `sdd:sdd-worker` as its own solo `Agent` call. Its brief:

- Read `.sdd-work/rebase_upstream_scan.md`, the spec directory's own artifacts (`idea.md`,
  `1. spec.md`, `2. plan.md`, whichever exist; the scan's `[batch N]` commits show how far
  implementation has got), `docs/app_structure.md` and
  `CLAUDE.md`.
- Decide `direction: unchanged` or `direction: changed`. `changed` means the change alters an app boundary in `docs/app_structure.md`, a shared base the spec builds on, a skill or
  convention the spec's plan contradicts, or a finished spec in `spec_dd/3. done/` that took a
  decision this spec reopens. Size alone is never `changed`.
- Write `.sdd-work/rebase_upstream_review.md` in one `Write`:

  ```
  # Upstream-change review: <spec name>

  direction: unchanged | changed

  ## What main gained
  one paragraph per signal that fired, in this project's words

  ## Why it matters for this spec            (only when changed)
  which of the spec's decisions the change undercuts, and the artifact holding each: idea.md,
  1. spec.md, 2. plan.md, or an implemented batch

  ## What to change                          (only when changed)
  one bullet per artifact, concrete enough to edit from

  status: ok
  ```

Per the fan-out recipe, `failed` retries the same worker up to twice with the prior error in the
retry brief; `blocked` supplies the listed `needs` from the scan file or the code, then retries.
Still `failed` or `blocked`:

```
status: failed · reason: upstream-change review <worker reason>
```

Leave `.sdd-work/rebase_upstream_scan.md` and any partial `.sdd-work/rebase_upstream_review.md` in
place on this exit. The next run's Step 3 replaces the scan file and this step resumes from the
surviving review.

## Step 5: Act on the verdict

Read `direction:` from `.sdd-work/rebase_upstream_review.md`.

**`unchanged`** — delete `.sdd-work/rebase_upstream_scan.md` and
`.sdd-work/rebase_upstream_review.md` by name.

```
status: ok · rebased: yes
```

**`changed`** —

1. Move `.sdd-work/rebase_upstream_review.md` to `<spec-dir>/upstream_change_review.md`,
   replacing an earlier one there if one exists.
2. Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/commands/protected/update_todo.md` and
   follow its steps with `<todo-path>` and `add_first:"user|Decide what to change after reading
   upstream_change_review.md, then edit the idea, spec or plan it names"`.
3. Delegate to `sdd:sdd-mechanic`: read `claude_plugins/sdd/resources/commit_and_push.md` and
   follow it with `<summary>`: `record the upstream-change review`, staging
   `upstream_change_review.md` and `todo.md`.
4. Delete `.sdd-work/rebase_upstream_scan.md` by name.

```
status: paused · reason: upstream-change review awaiting a decision
```

Once the human ticks that item by hand, the next pre-step rebase's Pause condition finds no
unticked item naming the file and proceeds. The review file stays in the spec directory beside the
spec, like any research file.
