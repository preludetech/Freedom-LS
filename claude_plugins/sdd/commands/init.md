---
description: Initialise the spec-driven-development (sdd) plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the sdd Plugin

Set up the `sdd` Claude Code plugin for this project. `sdd` provides the portable
spec-driven-development workflow (worker/mechanic agents, workflow commands, authoring skills). It
needs very little per-project config beyond the shared launcher it expects to exist.

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
`.claude/settings.local.json` line in `.gitignore` — are created by whatever initialised the
project's shared Claude Code setup. This command requires them to exist (Step 0) and otherwise
reports on them.

## Hard requirements — do not regress

- **`.claude/settings.json`** — merge, don't replace. Add `Skill(sdd:*)` if missing and `"sdd": true`
  to `enabledPlugins` (only this key — never another plugin's). **"Missing" means no byte-identical string is
  already in the list** — never "no entry semantically covers this". A redundant allow entry is
  harmless; removing one is a permission change this command is not entitled to make. **Never touch the `hooks` section**;
  `sdd` does not own the `SessionStart` hook. Mutate the file's own parsed object and write it back —
  never rebuild it from a template.
- **`.claude/sdd/config.md`** — create when absent, otherwise extend (add any key the default defines
  but the file lacks; preserve every existing value, comment, and ordering).
- **`.gitignore`** — append its own `.claude/sdd/config.local.md` line only. Never remove or reorder,
  and never touch the shared `.claude/settings.local.json` line, which `sdd` does not own.

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
| P1 | `claude.sh` exists at the project root | **STOP** → "`/sdd:init` adds its `--plugin-dir` line to an existing launcher and never creates one. Create the launcher and `.claude/settings.json` with whatever initialises this project's shared Claude Code setup, then re-run `/sdd:init`. Nothing has been changed." |
| P2 | `.claude/settings.json` exists | **STOP** → same message. The base settings file is shared; this command will not create a partial one. |
| P3 | It parses as JSON | **STOP** → "hand-fix the JSON, then re-run. Nothing has been changed." |
| P3b | Every `--plugin-dir` argument in `claude.sh` has a path containing the segment `/claude_plugins/` | **STOP** → "the launcher still points at a plugin directory outside `claude_plugins/`, and `/sdd:init` cannot repair it. Fix the launcher first, then re-run `/sdd:init`. Nothing has been changed." |
| P4 | Resolve `PLUGINS_ROOT` by the rule above, including its step-4 validation | **STOP** if invalid |
| P5 | Classify `claude.sh` per rule **L0** of `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md` | **STOP** if it has zero, or more than one, non-comment line invoking `claude` (P1 already stopped on an absent file) |
| P6 | `SessionStart` hook present and checking `$CLAUDE_PLUGINS_LOADED` | **WARN** → "add or migrate it by hand, or with whatever owns the launcher" |
| P7 | `.claude/settings.local.json` listed in `.gitignore` | **WARN** → "add it by hand, or with whatever owns the launcher" |
| P8 | `git status --porcelain --` on `claude.sh` and `.claude/settings.json` | **WARN** if dirty |

P1–P3b are STOPs rather than warnings so this command can never write `.claude/sdd/config.md` and a
`.gitignore` line and *then* discover it cannot finish.

**P3b exists because P1 and P2 are not sufficient.** A project that predates the `claude_plugins/`
layout already *has* a `claude.sh` and a `.claude/settings.json`, so file-existence checks pass and
this command would run to completion, adding its own `--plugin-dir` line to a launcher still pointing
at a plugin directory that no longer exists. With `<MAY_CREATE>` false it skips L4 and cannot retire
that argument, so it would leave the launcher broken. Checking the arguments themselves — not merely
that files exist — is the only check that catches this.

## Step 1: Merge the `sdd` permission and enabledPlugins key

1. Add `"Skill(sdd:*)"` to `permissions.allow` if absent (never duplicate).
2. Add `"sdd": true` to `enabledPlugins`. Do not add or remove another plugin's key.
3. Do not touch `hooks`.
4. Write the mutated object back and report what changed.

## Step 2: Create or extend `.claude/sdd/config.md`

`sdd` reads ten sections here at runtime. **Worktree Scripts**: the worktree helpers
(`protected/start_worktree.md`, `finish_worktree.md`) look here for the per-worktree setup and
teardown scripts to run. **Rebase Hooks**: the pre-step rebase helper
(`protected/pre_step_rebase.md`) looks here for the rebase command and front-end check it follows
before a feature-branch SDD step runs. **Design Hooks**: `/sdd:implement_plan` looks here for the
design check it follows after each slice that builds a designed screen. **Test Hooks**:
`protected/run_test_tier.md` looks here for the file that defines the test tiers. **Vocabulary Sources**: the idea, spec and plan commands look
here for the project's own definitions of its domain words. **Plan Review Hooks**:
`/sdd:plan_from_spec` looks here for project-owned review briefs it spawns after its built-in
review dimensions. **Review Hooks**: `/sdd:implement_plan` looks here for the comment standard and
test standard its implementer reads and its batch review checks. **Documentation Hooks**:
`/sdd:document` looks here for the skills it invokes, in order, after implementation and QA.
They can come from any plugin. **QA Hooks**: `protected/setup_todo_list.md` looks here for the
command that executes the QA plan, and writes it into the checklist. **PR Hooks**:
`/sdd:address_pr_review` looks here for the script that fetches a pull request's review comments.
Everything else in this dir exists for
parity and future settings.

**Do not prompt the user for these values.** Write blank defaults and say where the file is.

1. Ensure `.claude/sdd/` exists.
2. If `.claude/sdd/config.md` does not exist, write this — the reader helpers locate the values by
   the section and key names, so keep those exact. The file holds only this project's values; what each
   key means is documented here, not in the file:

   ```markdown
   # SDD Plugin Configuration

   ## Worktree Scripts

   - Setup script:
   - Teardown script:

   ## Rebase Hooks

   - Rebase command:
   - Front-end check:

   ## Design Hooks

   - Design check:

   ## Test Hooks

   - Test tiers:

   ## Plan Review Hooks

   -

   ## Review Hooks

   - Comment standard:
   - Test standard:

   ## Documentation Hooks

   -

   ## QA Hooks

   - QA command:

   ## PR Hooks

   - Fetch PR comments:

   ## Vocabulary Sources

   -
   ```

   A **Setup script** runs when a worktree is created (dependency install, per-branch dev DB,
   migrations, seed data); a **Teardown script** runs when one is finished (e.g. dropping that DB).
   Both are blank by default, meaning "this project has no such step". `sdd` is portable and names no
   product here — if another plugin owns those scripts in this project, the user points these keys at
   them.

   A **Rebase command** value points at a file that rebases the branch onto main; the pre-step
   rebase reads it and follows its steps inline. A **Front-end check** value points at a file that
   verifies front-end pages after a rebase that changed them. Both are blank by default, meaning
   "this project has no such step" — `sdd` is portable and names no product here either; if another
   plugin owns those files in this project, the user points these keys at them.

   A **Design check** value points at a file that screenshots the running app for the design states
   it is given and returns their paths; `/sdd:implement_plan` then compares those screenshots with
   the design's. Blank means "this project has no such step", and the check is skipped.

   A **Test tiers** value points at a file that defines the test tiers a step can name and how each
   one runs. Blank means "this project has no tier definition", and `protected/run_test_tier.md`
   falls back to the project's plain pytest command. `sdd` is portable and names no product here;
   if another plugin owns that file in this project, the user points this key at it.

   **Plan Review Hooks** is an ordered list of `<label>: <path>` bullets, and **Documentation
   Hooks** an ordered list of `<label>: <skill>` bullets, where `<skill>` is a plugin skill name
   such as `<plugin>:<command>`. `/sdd:document` invokes each with the `Skill` tool, so the hook
   runs with its own plugin root and tool grants. The label is for reporting and the order is the
   contract. An empty list means "this project has no such hooks", and a non-empty list in
   `config.local.md` replaces the whole list. `sdd` is portable and names no product here; if
   another plugin owns those hooks in this project, the user lists them.

   **Review Hooks** is keyed. A **Comment standard** value points at a file that states the
   project's comment rules, and a **Test standard** value points at a file that states its test
   rules. A blank key skips that half of the batch review. `sdd` names no product here either.

   A **QA command** value is a skill name, `<plugin>:<skill>`, that executes a spec's QA plan.
   `protected/setup_todo_list.md` writes it into `todo.md` as the QA step's slash command. Blank
   means "this project has no QA command", and the checklist tells the user to run the QA plan by
   hand. `sdd` names no product here; if another plugin owns that command, the user names it.

   A **Fetch PR comments** value points at a script, run from the project root, that prints a
   pull request's comments as JSON (`issue_comments`, `reviews`, `inline_comments` with an
   `is_outdated` field). Blank means "this project has no such script", and
   `/sdd:address_pr_review` fetches them with `gh` directly.

   **Vocabulary Sources** is what the idea, spec and plan commands consult before coining a word for
   a concept the project already names (see `${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`).
   Write the heading with an empty list; each source later becomes one bullet holding a path, most
   authoritative first. Naming this project's actual sources is the user's job — do
   not guess them by scanning the repo. With the list empty the commands still work: they fall back
   to the code, where model class names and field names are the vocabulary of last resort.
3. If it already exists, add the `## Worktree Scripts`, `## Rebase Hooks`, `## Design Hooks`, `## Test Hooks`,
   `## Plan Review Hooks`, `## Review Hooks`, `## Documentation Hooks`, `## QA Hooks`, `## PR Hooks`
   and `## Vocabulary Sources` sections, and any key only if missing, using the blank default. Preserve every existing value,
   comment, and ordering.
4. Tell the user in the summary to fill in the paths and the vocabulary sources themselves.

## Step 3: Update `.gitignore`

1. If `.claude/sdd/config.local.md` is not listed, add it.
2. Do **not** add the `.claude/settings.local.json` line — that one is shared and not `sdd`'s to add.

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
4. `.claude/sdd/config.md` has a `## Rebase Hooks` section with both `Rebase command` and
   `Front-end check` keys (blank values are valid).
5. `.claude/sdd/config.md` has a `## Design Hooks` section with a `Design check` key (a blank value
   is valid).
6. `.claude/sdd/config.md` has a `## Test Hooks` section with a `Test tiers` key (a blank value
   is valid).
7. `.claude/sdd/config.md` has a `## Plan Review Hooks` section (an empty list is valid).
8. `.claude/sdd/config.md` has a `## Review Hooks` section with both `Comment standard` and
   `Test standard` keys (blank values are valid).
9. `.claude/sdd/config.md` has a `## Documentation Hooks` section (an empty list is valid).
10. `.claude/sdd/config.md` has a `## QA Hooks` section with a `QA command` key (a blank value is
   valid).
11. `.claude/sdd/config.md` has a `## PR Hooks` section with a `Fetch PR comments` key (a blank
   value is valid).
12. `.claude/sdd/config.md` has a `## Vocabulary Sources` section (an empty list is valid).
13. `.claude/sdd/config.local.md` is listed in `.gitignore`.
14. `<PLUGINS_ROOT>/claude_plugins/sdd/` exists.
15. `claude.sh` contains exactly **one** `--plugin-dir` line whose final path segment is `sdd`, and
   that line expands `$PLUGINS_ROOT` only if a `PLUGINS_ROOT=` assignment exists in the file.
16. Every `--plugin-dir` path in `claude.sh` resolves to a directory that exists.
17. `hooks` in `.claude/settings.json` is unchanged from before this command ran.
18. Report every issue found.

## Step 6: Summary and outstanding actions

Print what was done, then the outstanding actions: every Step 0 WARN, and anything Step 5 flagged.
Point the user at `.claude/sdd/config.md` to fill in the Worktree Scripts Setup and Teardown paths,
the Rebase Hooks Rebase command and Front-end check paths, the Design Hooks Design check path, the Test Hooks Test tiers path, the Plan Review Hooks and Documentation Hooks lists, the Review
Hooks Comment standard and Test standard paths, the QA Hooks QA command, the PR Hooks Fetch PR
comments path, and to list the project's Vocabulary Sources.
