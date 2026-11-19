---
description: Initialise the spec-driven-development (sdd) plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the sdd Plugin

Set up the `sdd` Claude Code plugin for this project.

## Two rules that override every step below

**Nothing is written before Step 0 finishes.** Step 0 performs every check that can abort this
command. If Step 0 returns STOP, print the reason and the fix and end: the project is byte-for-byte
untouched, so re-running after the fix is always safe. No step after Step 0 may abort: from Step 1
onward, a problem is *reported as an outstanding action*, never raised as a bail-out.

**Nothing is force-deleted.** No step may pass `-f` to `git rm`, `-f`/`-r` to `rm`, or `--force` to
any command.

## Scope and hard requirements

`sdd:init` is **plugin-bootstrap only.** It changes only **its own** keys and lines. The
plugin-neutral artifacts (the `claude.sh` skeleton, the `SessionStart` hook, the
`.claude/settings.local.json` line in `.gitignore`) belong to whatever initialised the project's
shared Claude Code setup: Step 0 requires them and otherwise reports on them.

- **`.claude/settings.json`**: merge, don't replace. Mutate the file's own parsed object and write
  it back, never rebuild it from a template. Add only `Skill(sdd:*)`, `"sdd": true` under
  `enabledPlugins`, the `worktree` setting and the allow entries Step 1 names; never another
  plugin's key. **"Missing" means no byte-identical string is already in the list**, never "no
  entry semantically covers this". Never remove an allow entry. **Never touch `hooks`.**
- **`.claude/sdd/config.md`**: create when absent, otherwise extend (add any key the default
  defines but the file lacks; preserve every existing value, comment and ordering).
- **`.gitignore`**: append only the `.claude/sdd/config.local.md` and `.claude/worktrees/` lines.
  Never remove or reorder, and never touch the `.claude/settings.local.json` line.
- **`claude.sh`**: add only the `sdd` `--plugin-dir` line, never another plugin's.

## The `PLUGINS_ROOT` rule

This section is shared with every other plugin's init, except the directory name in step 4 and any
legacy variable name a plugin's own migration still accepts. Edit all copies together.

`PLUGINS_ROOT` is the relative path **from the project root** to the checkout that holds
`claude_plugins/`. It is baked into `claude.sh` and every wrapper script so they can find the plugin
directory at runtime. Resolve it in this order, stopping at the first step that yields a value.
**Never prompt the user. Never guess a project-specific path.**

1. **The launcher wins.** If `claude.sh` exists at the project root and contains a line matching
   `^PLUGINS_ROOT="(.*)"$`, the captured value is `PLUGINS_ROOT`.
2. **A wrapper script is the second source.** Otherwise, if any `.sh` under `.claude/*/scripts/`
   contains a line matching `^PLUGINS_ROOT="(.*)"$` whose value is not the literal
   `__PLUGINS_ROOT__`, and every such line agrees, use that value. If two disagree, **STOP** and
   print both, because a project cannot have two plugin roots.
3. **Otherwise the value is `.`**, the project root itself holding `./claude_plugins/`. This is the
   only default and the only candidate any init offers. **No init names a second candidate or an
   example path**: a hint present in one init and absent from another is how two inits come to bake
   different values into the same project.
4. **Validate before use.** Confirm `<PLUGINS_ROOT>/claude_plugins/sdd/` exists, relative to
   the project root. If it does not, **STOP** without writing anything:

   > Cannot find `claude_plugins/sdd/` under `PLUGINS_ROOT="<value>"`. Set `PLUGINS_ROOT` in
   > `claude.sh` to the relative path from the project root to the checkout that holds
   > `claude_plugins/`, then re-run this command. Nothing has been changed.

5. **Record it.** Every later step uses this one value. No step re-derives or substitutes it.

## Step 0: Preflight — read everything, write nothing

Use only `Read`, `Glob`, and read-only `Bash`. Do not create, modify, move, delete, or `chmod`
anything in this step or before it completes.

| # | Check | Verdict |
|---|---|---|
| P1 | `claude.sh` exists at the project root | **STOP** → "`/sdd:init` adds its `--plugin-dir` line to an existing launcher and never creates one. Create the launcher and `.claude/settings.json` with whatever initialises this project's shared Claude Code setup, then re-run `/sdd:init`. Nothing has been changed." |
| P2 | `.claude/settings.json` exists | **STOP** → same message. The base settings file is shared; this command will not create a partial one. |
| P3 | It parses as JSON | **STOP** → "hand-fix the JSON, then re-run. Nothing has been changed." |
| P3b | Every `--plugin-dir` argument in `claude.sh` has a path containing the segment `/claude_plugins/` | **STOP** → "the launcher still points at a plugin directory outside `claude_plugins/`, and `/sdd:init` cannot repair it. Fix the launcher first, then re-run `/sdd:init`. Nothing has been changed." |
| P4 | Resolve `PLUGINS_ROOT` by the rule above, including its step-4 validation | **STOP** if invalid |
| P5 | Classify `claude.sh` per rule **L0** of `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md` | **STOP** if it has zero, or more than one, non-comment line invoking `claude` (P1 already stopped on an absent file) |
| P6 | `SessionStart` hook present and checking `$CLAUDE_PLUGINS_LOADED` | **WARN** → "add or migrate it by hand, or with whatever owns the launcher" |
| P7 | `.claude/settings.local.json` listed in `.gitignore` | **WARN** → "add it by hand, or with whatever owns the launcher" |
| P8 | `git status --porcelain --` on `claude.sh` and `.claude/settings.json` | **WARN** if dirty |

## Step 1: Merge the `sdd` permission and enabledPlugins key

1. Add `"Skill(sdd:*)"` to `permissions.allow` if absent (never duplicate).
2. For every `.sh` under `${CLAUDE_PLUGIN_ROOT}/scripts/`, add these three `allow` entries if
   absent, with `<path>` = `<PLUGINS_ROOT>/claude_plugins/sdd/scripts/<name>.sh` and no `./`
   prefix on `<path>` when `PLUGINS_ROOT` is `.`:
   - `Bash(<path>:*)`
   - `Bash(bash <path>:*)`
   - `Bash(./<path>:*)`

   "Absent" means no byte-identical string is already in the list. Never remove or rewrite an
   entry here. For each Python script the commands call by name (`measure_prompt_size.py`, `full_run_record.py`, `check_diagrams.py`), add
   `Bash(python3 <PLUGINS_ROOT>/claude_plugins/sdd/scripts/<name>.py:*)` if absent, with no `./`
   prefix on the path when `PLUGINS_ROOT` is `.`. Same absent rule; same reason.
3. Merge `"worktree": {"baseRef": "head"}` at the top level of `.claude/settings.json` when the
   `worktree` key is absent; never overwrite an existing `worktree` object.
4. Add these `allow` entries if absent: `Bash(git worktree list*)`,
   `Bash(git worktree remove --force --force .claude/worktrees/*)`, `Bash(git cherry-pick *)`.
5. Add `"sdd": true` to `enabledPlugins`. Do not add or remove another plugin's key.
6. Do not touch `hooks`.
7. Write the mutated object back and report what changed.

## Step 2: Create or extend `.claude/sdd/config.md`

**Do not prompt the user for these values.** Write blank defaults and say where the file is.

1. Ensure `.claude/sdd/` exists.
2. If `.claude/sdd/config.md` does not exist, write this. The reader helpers locate the values by
   the section and key names, so keep those exact. The file holds only this project's values; the key meanings are below:

   ```markdown
   # SDD Plugin Configuration

   ## Worktree Scripts

   - Setup script:
   - Teardown script:
   - Parallel batches:
   - Memory capacity:
   - Batch memory (MB):
   - Worker memory (MB):

   ## Rebase Hooks

   - Rebase command:
   - Front-end check:

   ## Design Hooks

   - Design check:

   ## Test Hooks

   - Test tiers:
   - Pre-test rebuild:
   - Flaky test guide:

   ## Plan Review Hooks

   -

   ## Review Hooks

   - Comment standard:
   - Test standard:

   ## Documentation Hooks

   -

   ## QA Hooks

   - QA command:
   - Playwright MCP:
   - Screenshot directory:
   - Port finder:
   - Dev server start:
   - Dev server stop:
   - Branch badge:
   - Diff scoping:
   - Data helper guide:
   - Screenshot prep:
   - Layout regions:

   ## QA Login

   - Admin email:
   - Admin password:
   - Base URL:

   ## QA Dev Data

   - Content reset:
   - DB drop:
   - DB create:
   - Migrate:

   ## Testing Skills

   -

   ## Rule Files

   -

   ## Vocabulary Sources

   -
   ```

   A **Setup script** (read by `protected/start_worktree.md`) runs when a worktree is created (dependency install, per-branch dev DB,
   migrations, seed data); a **Teardown script** (read by `finish_worktree.md`) runs when one is finished (e.g. dropping that DB).
   Both are blank by default, meaning "this project has no such step". If another plugin owns those scripts, the user points these keys at
   them.

   **Parallel batches** is read by `/sdd:implement_plan`. Blank or `1` runs batches one at a time
   in the feature worktree. `n` of two or more lets it run up to `n` independent batches in batch
   worktrees under `.claude/worktrees/`, each of which runs the Setup script before and the
   Teardown script after its work. The Setup script must not depend on gitignored files, or the
   project lists them in `.worktreeinclude`; the Teardown script must be safe to run twice.

   **Memory capacity** is a command that takes a unit size in MB and prints how many units of that
   size fit in free memory now. **Batch memory (MB)** is the size of one batch: its subagent, Setup
   script and targeted test run. **Worker memory (MB)** is the size of one fan-out worker.
   `/sdd:implement_plan` starts no more batches than `Memory capacity` prints for `Batch memory (MB)`,
   and fan-out commands start no more workers than it prints for `Worker memory (MB)`. A blank
   `Memory capacity` or a blank size means no check.

   A **Rebase command** value points at a file that rebases the branch onto main; the pre-step
   rebase reads it and follows its steps inline. A **Front-end check** value points at a file that
   verifies front-end pages after a rebase that changed them. Both are blank by default, meaning
   "this project has no such step"; if another plugin owns those files, the user points these keys at them.

   A **Design check** value points at a file that screenshots the running app for the design states
   it is given and returns their paths; `/sdd:implement_plan` then compares those screenshots with
   the design's. Blank means "this project has no such step", and the check is skipped.

   A **Test tiers** value points at a file that defines the test tiers a step can name and how each
   one runs. Blank means "this project has no tier definition", and `protected/run_test_tier.md`
   falls back to the project's plain pytest command. If another plugin owns that file, the user points this key at it.

   A **Pre-test rebuild** value points at a script that rebuilds generated assets (dependencies,
   compiled CSS) the tests read. `/sdd:finish_worktree` runs it before its own full test run, when
   no rebase already rebuilt and tested the branch. Blank means "this project has no such step".

   A **Flaky test guide** value points at the file `/sdd:finish_worktree` hands the sub-agent that
   fixes a flaky test. Blank means the sub-agent works without a guide.

   **Plan Review Hooks** is an ordered list of `<label>: <path>` bullets, and **Documentation
   Hooks** an ordered list of `<label>: <skill>` bullets, where `<skill>` is a plugin skill name
   such as `<plugin>:<command>`. `/sdd:document` invokes each with the `Skill` tool, so the hook
   runs with its own plugin root and tool grants. The label is for reporting and the order is the
   contract. An empty list means "this project has no such hooks", and a non-empty list in
   `config.local.md` replaces the whole list. If another plugin owns those hooks, the user lists them.

   **Review Hooks** is keyed. A **Comment standard** value points at a file that states the
   project's comment rules, and a **Test standard** value points at a file that states its test
   rules. A blank key skips that half of the batch review.

   A **QA command** value is a skill name, `<plugin>:<skill>`, that executes a spec's QA plan.
   `protected/setup_todo_list.md` writes it into `todo.md` as the QA step's slash command. Blank
   means "this project has no QA command", and the checklist tells the user to run the QA plan by
   hand.

   **Playwright MCP** is the tool-name prefix of the browser server the QA command drives. Blank
   means the QA command stops `blocked`. **Screenshot directory** is where that server writes
   screenshots, relative to the project root. Blank means screenshots are collected from the spec
   directory only. **Port finder** is a command that prints a free port. **Dev server start** and
   **Dev server stop** are shell commands with `<PORT>` and `<PROJECT_ROOT>` placeholders that the
   QA command substitutes literally, for example `<command> <PORT>`. If the port finder or either
   server command is blank, the QA command stops `blocked` and names the key. **Branch badge** is
   the element id that names the served branch. Blank means the branch check is skipped. **Diff
   scoping** is a file of diff classification rules. Blank means every diff is `FULL`. **Data helper
   guide** is a file of the project's data-creation conventions that `sdd:qa-data-helper` reads.
   Blank means it works from the codebase. **Screenshot prep** is a one-line instruction the QA
   command carries out before each screenshot, to clear dev tooling (a debug toolbar, a cookie
   banner) that would cover the page. Blank means no prep. **Layout regions** is a JSON object mapping
   a region name to a CSS selector, for the QA command's layout probe: `header` and `content` are
   checked for alignment and every region for overlap. Blank means the probe checks overflow only.

   A blank **QA Login** value skips the login step and makes a test that needs a login PARTIAL. A
   blank **QA Dev Data** value removes that rung of the reset ladder. **Testing Skills** is a list
   of `<plugin>:<skill>` names, one per bullet, that the QA bug fixer loads before writing a test.
   An empty list means none. A section whose list is a lone `-` is empty.

   **Rule Files** is a list, not keyed. Each bullet is `<scope>: <path>`: a few words naming what
   the file's rules cover (a brand's visual system, its voice, one UI framework's pages) and the
   project file holding them. A file holds rules that hold across its whole scope; one feature's
   details stay in that feature's spec. `sdd:capture-feedback` writes each rule into the file whose
   scope fits it best, and the QA command walks the `## Visual checklist` section of every file listed.
   An empty list means feedback is not captured, and the skill says so.

   **Vocabulary Sources** is what the idea, spec and plan commands consult before coining a word for
   a concept the project already names (see `${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`).
   Write the heading with an empty list; each source later becomes one bullet holding a path, most
   authoritative first. Do not guess the sources by
   scanning the repo; naming them is the user's job. With the list empty the commands fall back to the code, where
   model class names and field names are the vocabulary of last resort.
3. If it already exists, add every section and every key of the template above that is missing
   (for instance `Flaky test guide` under `## Test Hooks`, and `Parallel batches`, `Memory capacity`,
   `Batch memory (MB)` and `Worker memory (MB)` under `## Worktree Scripts`), using the blank
   default. Preserve every existing value, comment, and ordering.
4. Tell the user in the summary to fill in the paths and the vocabulary sources themselves.

## Step 3: Update `.gitignore`

1. If `.claude/sdd/config.local.md` is not listed, add it.
2. If `.claude/worktrees/` is not listed, add it.
3. Do **not** add the `.claude/settings.local.json` line; that one is shared and not `sdd`'s to add.

## Step 4: Ensure the `sdd` `--plugin-dir` line

Follow `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md`, using the P5 classification and the
resolved `PLUGINS_ROOT`. With `<MAY_CREATE>` false this runs L2, L3, L5 and L7 only: it normalises
the launcher shape, guarantees `PLUGINS_ROOT` exists before any line expands it, and ensures exactly
one `sdd` `--plugin-dir` line. It never creates the launcher, retires another plugin's argument, or
touches the sentinel. Write the launcher as **one atomic file replacement**, not a sequence of
in-place edits.

## Step 5: Validate the setup

1. `sdd` is in `enabledPlugins`, and `.claude/settings.json` is valid JSON.
2. `Skill(sdd:*)` is in `permissions.allow`, and so are the three entries from Step 1 item 2 for
   every `.sh` under `${CLAUDE_PLUGIN_ROOT}/scripts/`, plus the `python3` entry from Step 1 item 2
   for each Python script the commands call by name.
3. `.claude/sdd/config.md` has a `## Worktree Scripts` section with the `Setup script`,
   `Teardown script`, `Parallel batches`, `Memory capacity`, `Batch memory (MB)` and `Worker memory (MB)` keys (blank values are valid).
4. `.claude/sdd/config.md` has a `## Rebase Hooks` section with both `Rebase command` and
   `Front-end check` keys (blank values are valid).
5. `.claude/sdd/config.md` has a `## Design Hooks` section with a `Design check` key (a blank value
   is valid).
6. `.claude/sdd/config.md` has a `## Test Hooks` section with `Test tiers`, `Pre-test rebuild`
   and `Flaky test guide` keys (blank values are valid).
7. `.claude/sdd/config.md` has a `## Plan Review Hooks` section (an empty list is valid).
8. `.claude/sdd/config.md` has a `## Review Hooks` section with both `Comment standard` and
   `Test standard` keys (blank values are valid).
9. `.claude/sdd/config.md` has a `## Documentation Hooks` section (an empty list is valid).
10. `.claude/sdd/config.md` has a `## QA Hooks` section with the keys `QA command`, `Playwright MCP`,
   `Screenshot directory`, `Port finder`, `Dev server start`, `Dev server stop`, `Branch badge`,
   `Diff scoping`, `Data helper guide`, `Screenshot prep` and `Layout regions`, a `## QA Login` section with `Admin email`, `Admin
   password` and `Base URL`, a `## QA Dev Data` section with `Content reset`, `DB drop`, `DB create`
   and `Migrate`, and a `## Testing Skills` section (blank values and an empty list are valid).
11. `.claude/sdd/config.md` has a `## Rule Files` section (an empty list is valid).
12. `.claude/sdd/config.md` has a `## Vocabulary Sources` section (an empty list is valid).
13. `.claude/sdd/config.local.md` and `.claude/worktrees/` are listed in `.gitignore`.
14. `<PLUGINS_ROOT>/claude_plugins/sdd/` exists.
15. `claude.sh` contains exactly **one** `--plugin-dir` line whose final path segment is `sdd`, and
   that line expands `$PLUGINS_ROOT` only if a `PLUGINS_ROOT=` assignment exists in the file.
16. Every `--plugin-dir` path in `claude.sh` resolves to a directory that exists.
17. `hooks` in `.claude/settings.json` is unchanged from before this command ran.
18. `worktree.baseRef` is present in `.claude/settings.json`, and so are the three entries from
   Step 1 item 4.
19. Report every issue found.

## Step 6: Summary and outstanding actions

Print what was done, then the outstanding actions: every Step 0 WARN, anything Step 5 flagged,
and each worktree setting, allow entry or ignore line that was not merged. Point the user at
`.claude/sdd/config.md` to fill in every blank key above and to list the project's Vocabulary Sources.

If `claude.sh` has no `--plugin-dir` line whose final segment is `productivity`, list
`run /productivity:init` as an outstanding action. This command never adds that line.
