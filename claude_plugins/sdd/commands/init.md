---
description: Initialise the spec-driven-development (sdd) plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the sdd Plugin

Set up the `sdd` Claude Code plugin for this project. `sdd` provides the portable
spec-driven-development workflow (worker/mechanic agents, workflow commands, authoring skills). It
needs very little per-project config beyond the generic shared bits that `ds:init` creates.

## Two rules that override every step below

**Nothing is written before Step 0 finishes.** Step 0 performs every check that can abort this
command. If Step 0 returns STOP, print the reason and the fix and end — the project is byte-for-byte
untouched, so re-running after the fix is always safe and always starts from a clean state. No step
after Step 0 may abort: from Step 1 onward, a problem is *reported as an outstanding action*, never
raised as a bail-out.

**Nothing is force-deleted.** No step may pass `-f` to `git rm`, `-f`/`-r` to `rm`, or `--force` to
any command. `sdd:init` deletes nothing at all, but the rule stands for any future edit.

## Scope

`sdd:init` is **plugin-bootstrap only.** It merges only **its own** `enabledPlugins` key and
permission and writes only its own `.claude/sdd/` config dir. Into the shared project-root
`claude.sh` it adds **only its own** `--plugin-dir` line; it never touches another plugin's.

The generic, plugin-neutral artifacts — the `claude.sh` skeleton, the `SessionStart` hook, and the
`.claude/settings.local.json` line in `.gitignore` — are created by `ds:init`. This command requires
them to exist (Step 0) and otherwise reports on them.

## Hard requirements — do not regress

- **`.claude/settings.json`** — merge, don't replace. Add `Skill(sdd:*)` if missing and `"sdd": true`
  to `enabledPlugins` (only this key — never another plugin's). **"Missing" means no byte-identical string is
  already in the list** — never "no entry semantically covers this". A redundant allow entry is
  harmless; removing one is a permission change this command is not entitled to make. **Never touch the `hooks` section**;
  the `SessionStart` hook is `ds`-owned. Mutate the file's own parsed object and write it back —
  never rebuild it from a template.
- **`.claude/sdd/config.md`** — create when absent, otherwise extend (add any key the default defines
  but the file lacks; preserve every existing value, comment, and ordering).
- **`.gitignore`** — append its own `.claude/sdd/config.local.md` line only. Never remove or reorder,
  and never touch the `ds`-owned `.claude/settings.local.json` line.

## The `PLUGINS_ROOT` rule

This section is identical in every plugin's init except the directory name in step 4. Edit all copies
together.

`PLUGINS_ROOT` is the relative path **from the project root** to the checkout that holds
`claude_plugins/`. It is baked into `claude.sh` and into every wrapper script so they can find the
plugin directory at runtime. Resolve it exactly like this, in order, stopping at the first step that
yields a value. **Never prompt the user. Never guess a project-specific path.**

1. **The launcher wins.** If `claude.sh` exists at the project root and contains a line matching
   `^PLUGINS_ROOT="(.*)"$`, the captured value is `PLUGINS_ROOT`.
2. **A wrapper script is the second source.** Otherwise, if any `.sh` under `.claude/*/scripts/`
   contains a line matching `^(PLUGINS_ROOT|FLS_PATH)="(.*)"$` whose value is not the literal
   `__PLUGINS_ROOT__`, and every such line agrees, use that value. If two disagree, **STOP** and
   print both — a project cannot have two plugin roots.

   `FLS_PATH` is matched here because it is the pre-split name for this same variable. On a
   pre-split project **every** wrapper still uses it, so omitting it would make this whole step dead
   on exactly the projects that need it — and a project whose checkout is a submodule would silently
   fall through to the `.` default and bake the wrong root into every generated file.
3. **Otherwise the value is `.`** — the project root itself holds `./claude_plugins/`. This is the
   only default, and it is the only candidate any init offers. **No init names a second candidate or
   an example path.** A hint present in one init and absent from another is exactly how two inits
   come to bake different values into the same project.
4. **Validate before use.** Confirm `<PLUGINS_ROOT>/claude_plugins/sdd/` exists, relative to the
   project root. If it does not, **STOP** without writing anything:

   > Cannot find `claude_plugins/sdd/` under `PLUGINS_ROOT="<value>"`. Set `PLUGINS_ROOT` in
   > `claude.sh` to the relative path from the project root to the checkout that holds
   > `claude_plugins/`, then re-run this command. Nothing has been changed.

5. **Record it.** Every later step uses this one value. No step re-derives it and no step substitutes
   another.

## Step 0: Preflight — read everything, write nothing

Use only `Read`, `Glob`, and read-only `Bash`. Do not create, modify, move, delete, or `chmod`
anything in this step or before it completes.

| # | Check | Verdict |
|---|---|---|
| P1 | `claude.sh` exists at the project root | **STOP** → "`/sdd:init` adds its `--plugin-dir` line to a launcher `/ds:init` owns. Run `/ds:init` first, then re-run `/sdd:init`. Nothing has been changed." |
| P2 | `.claude/settings.json` exists | **STOP** → same message. The base settings file is `ds`-owned; this command will not create a partial one. |
| P3 | It parses as JSON | **STOP** → "hand-fix the JSON, then re-run. Nothing has been changed." |
| P3b | `"ds": true` is in `enabledPlugins` | **STOP** → "`/sdd:init` adds a `--plugin-dir` line to a launcher `/ds:init` owns, and cannot repair a launcher that still points at a pre-split plugin. Run `/ds:init` first, then re-run `/sdd:init`. Nothing has been changed." |
| P4 | Resolve `PLUGINS_ROOT` by the rule above, including its step-4 validation | **STOP** if invalid |
| P5 | Classify `claude.sh` per rule **L0** of `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md` | **STOP** if it has zero, or more than one, non-comment line invoking `claude` (P1 already stopped on an absent file) |
| P6 | `SessionStart` hook present and checking `$CLAUDE_PLUGINS_LOADED` | **WARN** → "run `/ds:init` to add or migrate it" |
| P7 | `.claude/settings.local.json` listed in `.gitignore` | **WARN** → "`/ds:init` adds it" |
| P8 | `git status --porcelain --` on `claude.sh` and `.claude/settings.json` | **WARN** if dirty |

P1–P3b are STOPs rather than warnings so this command can never write `.claude/sdd/config.md` and a
`.gitignore` line and *then* discover it cannot finish.

**P3b exists because P1 and P2 are not sufficient.** A pre-split project already *has* a `claude.sh`
and a `.claude/settings.json` — they are just the `fls`-era ones — so file-existence checks pass and
this command would run to completion, adding its own `--plugin-dir` line to a launcher still pointing
at a plugin directory the split deleted. With `<MAY_CREATE>` false it skips L4 and cannot retire that
argument, so it would leave a launcher broken in a way only `/ds:init` can repair. Testing that `ds`
has actually *initialised* — not merely that files exist — is the only check that catches this.

## Step 1: Merge the `sdd` permission and enabledPlugins key

1. Add `"Skill(sdd:*)"` to `permissions.allow` if absent (never duplicate).
2. Add `"sdd": true` to `enabledPlugins`. Do not add or remove another plugin's key.
3. Do not touch `hooks`.
4. Write the mutated object back and report what changed.

## Step 2: Create or extend `.claude/sdd/config.md`

The one thing `sdd` reads at runtime is the **Worktree Scripts** section: the worktree helpers
(`protected/start_worktree.md`, `finish_worktree.md`) look here for the per-worktree setup and
teardown scripts to run. Everything else in this dir exists for parity and future settings.

**Do not prompt the user for these values.** Write blank defaults and say where the file is.

1. Ensure `.claude/sdd/` exists.
2. If `.claude/sdd/config.md` does not exist, write this — the reader helpers locate the values by
   the section and key names, so keep those exact. Surrounding prose may be adapted; the
   `## Worktree Scripts` heading and the two key names may not:

   ```markdown
   # SDD Plugin Configuration

   The spec-driven-development (sdd) workflow is enabled for this project.

   ## Worktree Scripts

   Paths are relative to the project root. Leave a value blank if this project has no such step.

   - Setup script:
   - Teardown script:
   ```

   A **Setup script** runs when a worktree is created (dependency install, per-branch dev DB,
   migrations, seed data); a **Teardown script** runs when one is finished (e.g. dropping that DB).
   Both are blank by default, meaning "this project has no such step". `sdd` is portable and names no
   product here — if another plugin owns those scripts in this project, the user points these keys at
   them.
3. If it already exists, add the `## Worktree Scripts` section and either key only if missing, using
   the blank default. Preserve every existing value, comment, and ordering.
4. Tell the user in the summary to fill in the two paths themselves.

## Step 3: Update `.gitignore`

1. If `.claude/sdd/config.local.md` is not listed, add it.
2. Do **not** add the `.claude/settings.local.json` line — that one is `ds`-owned.

## Step 4: Ensure the `sdd` `--plugin-dir` line

Follow `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md`, using the P5 classification and the
resolved `PLUGINS_ROOT`. With `<MAY_CREATE>` false this runs L2, L3, L5 and L7 only — it normalises
the launcher shape, guarantees `PLUGINS_ROOT` exists before any line expands it, and ensures exactly
one `sdd` `--plugin-dir` line. It never creates the launcher, retires another plugin's argument, or
touches the sentinel. Write the launcher as **one atomic file replacement** rather than a sequence of
in-place edits.

## Step 5: Validate the setup

1. `sdd` is in `enabledPlugins`, and `.claude/settings.json` is valid JSON.
2. `Skill(sdd:*)` is in `permissions.allow`.
3. `.claude/sdd/config.md` has a `## Worktree Scripts` section with both `Setup script` and
   `Teardown script` keys (blank values are valid).
4. `.claude/sdd/config.local.md` is listed in `.gitignore`.
5. `<PLUGINS_ROOT>/claude_plugins/sdd/` exists.
6. `claude.sh` contains exactly **one** `--plugin-dir` line whose final path segment is `sdd`, and
   that line expands `$PLUGINS_ROOT` only if a `PLUGINS_ROOT=` assignment exists in the file.
7. Every `--plugin-dir` path in `claude.sh` resolves to a directory that exists.
8. `hooks` in `.claude/settings.json` is unchanged from before this command ran.
9. Report every issue found.

## Step 6: Summary and outstanding actions

Print what was done, then the outstanding actions: every Step 0 WARN, and anything Step 5 flagged.
Point the user at `.claude/sdd/config.md` to fill in the Worktree Scripts Setup and Teardown paths.
