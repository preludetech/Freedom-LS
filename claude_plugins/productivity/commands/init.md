---
description: Initialise the productivity plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the productivity Plugin

Set up the `productivity` Claude Code plugin for this project. `productivity` provides generic
writing and working skills (`answer`, `unslop`, `writing-for-agents`). It needs no per-project
config beyond the shared launcher it expects to exist.

## Two rules that override every step below

**Nothing is written before Step 0 finishes.** Step 0 performs every check that can abort this
command. If Step 0 returns STOP, print the reason and the fix and end. The project is byte-for-byte
untouched, so re-running after the fix is always safe and always starts from a clean state. No step
after Step 0 may abort: from Step 1 onward, a problem is *reported as an outstanding action*, never
raised as a bail-out.

**Nothing is force-deleted.** No step may pass `-f` to `git rm`, `-f`/`-r` to `rm`, or `--force` to
any command. `productivity:init` deletes nothing at all, but the rule stands for any future edit.

## Scope

`productivity:init` is **plugin-bootstrap only.** It merges only **its own** `enabledPlugins` key and
permission. Into the shared project-root `claude.sh` it adds **only its own** `--plugin-dir` line; it
never touches another plugin's.

The generic, plugin-neutral artifacts (the `claude.sh` skeleton, the `SessionStart` hook, and the
`.claude/settings.local.json` line in `.gitignore`) are created by whatever initialised the
project's shared Claude Code setup. This command requires `claude.sh` and `.claude/settings.json` to
exist (Step 0) and otherwise reports on them.

## Hard requirements: do not regress

- **`.claude/settings.json`**: merge, don't replace. Add `Skill(productivity:*)` if missing and
  `"productivity": true` to `enabledPlugins` (only this key, never another plugin's). **"Missing"
  means no byte-identical string is already in the list**, never "no entry semantically covers
  this". A redundant allow entry is harmless; removing one is a permission change this command is
  not entitled to make. **Never touch the `hooks` section**; `productivity` does not own the
  `SessionStart` hook. Mutate the file's own parsed object and write it back, never rebuild it from
  a template.

## The `PLUGINS_ROOT` rule

This section is shared with every other plugin's init, except the directory name in step 4 and any
legacy variable name a plugin's own migration still accepts. Edit all copies together.

`PLUGINS_ROOT` is the relative path **from the project root** to the checkout that holds
`claude_plugins/`. It is baked into `claude.sh` and into every wrapper script so they can find the
plugin directory at runtime. Resolve it exactly like this, in order, stopping at the first step that
yields a value. **Never prompt the user. Never guess a project-specific path.**

1. **The launcher wins.** If `claude.sh` exists at the project root and contains a line matching
   `^PLUGINS_ROOT="(.*)"$`, the captured value is `PLUGINS_ROOT`.
2. **A wrapper script is the second source.** Otherwise, if any `.sh` under `.claude/*/scripts/`
   contains a line matching `^PLUGINS_ROOT="(.*)"$` whose value is not the literal
   `__PLUGINS_ROOT__`, and every such line agrees, use that value. If two disagree, **STOP** and
   print both — a project cannot have two plugin roots.
3. **Otherwise the value is `.`** — the project root itself holds `./claude_plugins/`. This is the
   only default, and it is the only candidate any init offers. **No init names a second candidate or
   an example path.** A hint present in one init and absent from another is exactly how two inits
   come to bake different values into the same project.
4. **Validate before use.** Confirm `<PLUGINS_ROOT>/claude_plugins/productivity/` exists, relative to the
   project root. If it does not, **STOP** without writing anything:

   > Cannot find `claude_plugins/productivity/` under `PLUGINS_ROOT="<value>"`. Set `PLUGINS_ROOT` in
   > `claude.sh` to the relative path from the project root to the checkout that holds
   > `claude_plugins/`, then re-run this command. Nothing has been changed.

5. **Record it.** Every later step uses this one value. No step re-derives it and no step substitutes
   another.

## Step 0: Preflight (read everything, write nothing)

Use only `Read`, `Glob`, and read-only `Bash`. Do not create, modify, move, delete, or `chmod`
anything in this step or before it completes.

| # | Check | Verdict |
|---|---|---|
| P1 | `claude.sh` exists at the project root | **STOP** -> "`/productivity:init` adds its `--plugin-dir` line to an existing launcher and never creates one. Create the launcher and `.claude/settings.json` with whatever initialises this project's shared Claude Code setup, then re-run `/productivity:init`. Nothing has been changed." |
| P2 | `.claude/settings.json` exists | **STOP** -> same message. The base settings file is shared; this command will not create a partial one. |
| P3 | It parses as JSON | **STOP** -> "hand-fix the JSON, then re-run. Nothing has been changed." |
| P3b | Every `--plugin-dir` argument in `claude.sh` has a path containing the segment `/claude_plugins/` | **STOP** -> "the launcher still points at a plugin directory outside `claude_plugins/`, and `/productivity:init` cannot repair it. Fix the launcher first, then re-run `/productivity:init`. Nothing has been changed." |
| P4 | Resolve `PLUGINS_ROOT` by the rule above, including its step-4 validation | **STOP** if invalid |
| P5 | Classify `claude.sh` per rule **L0** of `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md` | **STOP** if it has zero, or more than one, non-comment line invoking `claude` (P1 already stopped on an absent file) |
| P8 | `git status --porcelain --` on `claude.sh` and `.claude/settings.json` | **WARN** if dirty |

P1-P3b are STOPs rather than warnings so this command can never write one file and *then* discover
it cannot finish.

**P3b exists because P1 and P2 are not sufficient.** A project that predates the `claude_plugins/`
layout already *has* a `claude.sh` and a `.claude/settings.json`, so file-existence checks pass and
this command would run to completion, adding its own `--plugin-dir` line to a launcher still pointing
at a plugin directory that no longer exists. With `<MAY_CREATE>` false it skips L4 and cannot retire
that argument, so it would leave the launcher broken. Checking the arguments themselves, not merely
that files exist, is the only check that catches this.

## Step 1: Merge the `productivity` permission and enabledPlugins key

1. Add `"Skill(productivity:*)"` to `permissions.allow` if absent (never duplicate).
2. Add `"productivity": true` to `enabledPlugins`. Do not add or remove another plugin's key.
3. Do not touch `hooks`.
4. Write the mutated object back and report what changed.

## Step 2: Ensure the `productivity` `--plugin-dir` line

Follow `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md`, using the P5 classification and the
resolved `PLUGINS_ROOT`. With `<MAY_CREATE>` false this runs L2, L3, L5 and L7 only. It normalises
the launcher shape, guarantees `PLUGINS_ROOT` exists before any line expands it, and ensures exactly
one `productivity` `--plugin-dir` line. It never creates the launcher, retires another plugin's
argument, or touches the sentinel. Write the launcher as **one atomic file replacement** rather than
a sequence of in-place edits.

## Step 3: Validate the setup

1. `productivity` is in `enabledPlugins`, and `.claude/settings.json` is valid JSON.
2. `Skill(productivity:*)` is in `permissions.allow`.
3. `<PLUGINS_ROOT>/claude_plugins/productivity/` exists.
4. `claude.sh` contains exactly **one** `--plugin-dir` line whose final path segment is
   `productivity`, and that line expands `$PLUGINS_ROOT` only if a `PLUGINS_ROOT=` assignment exists
   in the file.
5. Every `--plugin-dir` path in `claude.sh` resolves to a directory that exists.
6. `hooks` in `.claude/settings.json` is unchanged from before this command ran.
7. Report every issue found.

## Step 4: Summary and outstanding actions

Print what was done, then the outstanding actions: every Step 0 WARN, and anything Step 3 flagged.
