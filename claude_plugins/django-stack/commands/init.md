---
description: Initialise the django-stack (ds) plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the django-stack (ds) Plugin

Set up the `ds` Claude Code plugin for this project. `ds` is a portable Django-stack plugin — it
carries zero product-specific knowledge and depends on no other plugin. This command wires `ds` into
an existing project and creates the generic launcher/hook/gitignore artifacts a project needs to load
Claude Code plugins at all — but only when they are missing.

## Two rules that override every step below

**Nothing is written before Step 0 finishes.** Step 0 performs every check that can abort this
command. If Step 0 returns STOP, print the reason and the fix and end — the project is byte-for-byte
untouched, so re-running after the fix is always safe and always starts from a clean state. No step
after Step 0 may abort: from Step 1 onward, a problem is *reported as an outstanding action*, never
raised as a bail-out.

**Nothing is force-deleted.** No step may pass `-f` to `git rm`, `-f`/`-r` to `rm`, or `--force` to
any command. If a deletion is refused — by git, by the filesystem, or by a guard in this file — the
file stays where it is and the refusal is reported. A file this command cannot prove is disposable is
not disposable.

## Scope

`ds:init` is **plugin-bootstrap only.** It wires the `ds` plugin into an existing project. It does
NOT scaffold Django project structure (`config/`, `pyproject.toml`, Tailwind config, a `CLAUDE.md`
skeleton) — those come from the project template. Run `ds:init` after the project already exists.

`ds:init` writes its **own** slice — the `ds` `enabledPlugins` key, `ds` permissions, the
`.claude/ds/` config dir, and the `ds` wrapper scripts. Alongside that it creates a few **generic,
plugin-neutral** artifacts a Claude Code project needs regardless of which plugins are installed, and
only when they are absent:

- the root **`claude.sh`** launcher,
- the **`SessionStart`** sentinel hook in `.claude/settings.json`,
- **`.gitignore`** itself when absent, plus its `.claude/settings.local.json` line.

`claude.sh` is a shared file: `ds:init` ensures **its own** `--plugin-dir` line is present and never
touches any other. If additional plugins are installed, each of their inits adds its own line the
same way.

## Hard requirements — do not regress

- **`.claude/settings.json` → `permissions`** — merge, don't replace. Add missing `allow`/`deny`
  entries and `"ds": true` to `enabledPlugins` (only this key — never another plugin's). Never
  replace the whole file, and never remove an entry that already exists. **"Missing" means no
  byte-identical string is already in the list** — never "no entry semantically covers this". Two
  entries that overlap (`Bash(npm run tailwind_build)` and `Bash(npm run tailwind_build:*)`) both
  stay; a redundant allow entry is harmless, and removing one is a permission change this command is
  not entitled to make.
- **`.claude/settings.json` → `hooks`** — this command owns exactly one thing: the sentinel-check
  entry inside the `SessionStart` event. It may create the `hooks` object, create the `SessionStart`
  array, append its own entry, and rewrite its own entry in place. Nothing else.
  - Every hook event that is not `SessionStart` — `PreToolUse`, `PostToolUse`, `Stop`,
    `UserPromptSubmit`, `SessionEnd`, and any event a future Claude Code version adds — is
    **read-only for this command**. Copy it through byte-for-byte. In particular, a `PreToolUse`
    matcher that denies reading `.env` files is a project security control; preserving it exactly is a
    requirement of this command, not a courtesy. **This command deletes no hook, ever.**
  - Inside `SessionStart`, an entry is this command's own only if its `command` string contains
    `printf` **and** either the token `CLAUDE_PLUGINS_LOADED` or the legacy sentinel name **preflight
    P4 recorded** (`L0`'s *sentinel* fact). Preflight reads the launcher, so that name is known before
    Step 1 runs — do not wait for Step 4, which runs later. Every other `SessionStart` entry belongs to
    someone else and is copied through.

    Getting this wrong is not cosmetic: on a project whose hook still checks a legacy sentinel, failing
    to recognise the entry as your own means appending a *second* one. Step 4 then renames the
    sentinel, the stale entry's variable is never set again, and its `"continue": false` aborts every
    future session.
  - **Implementation is prescribed:** start from the file's own parsed object, mutate only
    `permissions.allow`, `permissions.deny`, `enabledPlugins["ds"]`, and this command's own
    `SessionStart` entry, then write that object back. Never construct the output from the template
    and copy the project's values into it — that is how a `PreToolUse` hook goes missing.
- **`.claude/ds/config.md`** — create when absent, otherwise extend: add any key the template defines
  but the file lacks, preserving every existing value, comment, and ordering. Never re-prompt for
  options the file already has.
- **`.gitignore`** — create it if absent; otherwise add missing entries only, never removing or
  reordering existing lines. Place a new entry next to its siblings if a `# Claude` block already
  exists, otherwise append at the end.
- **Wrapper scripts** — install a template only when the destination does not exist. An existing
  script is never overwritten or regenerated; it is migrated in place per Step 5.
- **`deny` is belt-and-braces with the `PreToolUse` hook.** `Read(.env)` / `Read(.env.*)` in `deny`
  and the hook cover the same ground on purpose. Do not "simplify" either away.

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
4. **Validate before use.** Confirm `<PLUGINS_ROOT>/claude_plugins/django-stack/` exists, relative to
   the project root. If it does not, **STOP** without writing anything:

   > Cannot find `claude_plugins/django-stack/` under `PLUGINS_ROOT="<value>"`. Set `PLUGINS_ROOT` in
   > `claude.sh` to the relative path from the project root to the checkout that holds
   > `claude_plugins/`, then re-run this command. Nothing has been changed.

5. **Record it.** Every later step uses this one value. No step re-derives it and no step substitutes
   another.

## Step 0: Preflight — read everything, write nothing

Use only `Read`, `Glob`, and read-only `Bash` (`ls`, `test`, `git status --porcelain -- <path>`,
`git ls-files`). Do not create, modify, move, delete, `chmod`, `git mv`, or `git rm` anything in this
step or before it completes.

Gather the facts below, then evaluate every **STOP** condition **before** proceeding. Record every
**WARN** — it goes in the Step 8 summary, not into an abort. Carry the facts forward: later steps act
on Step 0's verdicts and never re-derive them.

| # | Check | Verdict |
|---|---|---|
| P1 | Resolve `PLUGINS_ROOT` by the rule above, including its step-4 validation | **STOP** if invalid |
| P2 | Read `.claude/settings.json` if present and parse it as JSON | **STOP** if present but unparseable: "hand-fix the JSON, then re-run. Nothing has been changed." |
| P3 | **Snapshot the parsed `hooks` object verbatim.** Validation item 8 deep-compares against it | record |
| P4 | Read `claude.sh` if present; classify it per rule **L0** of `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md`. **Record the sentinel name** — Step 1's hook-ownership test needs it | **STOP** only if the file exists and has zero, or more than one, non-comment line invoking `claude`. An absent launcher is never a STOP — creating it is this command's job |
| P5 | Read `CLAUDE.md` line 1 and test it against the exact legacy-line shape in Step 6 | record verdict |
| P6 | Glob `.claude/ds/scripts/*.sh`; classify each per Step A of `${CLAUDE_PLUGIN_ROOT}/resources/wrapper_script_migration.md` | record |
| P7 | `git status --porcelain --` each file this run may rewrite (`claude.sh`, `.claude/settings.json`, `CLAUDE.md`, each `.claude/ds/scripts/*.sh`) | **WARN** listing any that are dirty: "uncommitted edits will be rewritten in place; commit first if you want a rollback point". Running the plugin inits back to back before committing is normal, so say so rather than alarming the user |
| P8 | `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/*.sh` exist and are executable | **WARN** only — these live inside the plugin checkout, not the project, so this command does not fix them |

`ds` never STOPs for a missing project artifact — creating those is its job.

## Step 1: Merge permissions and the SessionStart hook into `.claude/settings.json`

1. Read `${CLAUDE_PLUGIN_ROOT}/templates/settings.json` for the recommended `ds` baseline.
2. If `.claude/settings.json` exists (P2 parsed it):
   - Add any missing `allow` rule and any missing `deny` rule. Never duplicate, never remove.
   - Add `"ds": true` to `enabledPlugins`. Do not add or remove another plugin's key.
   - Merge the `SessionStart` sentinel hook per the Hard requirements above: create `hooks` /
     `SessionStart` if missing; if this command's own entry (by the ownership test above) is absent,
     append it; if present but checking a legacy sentinel, rewrite that one entry. Copy every other
     event and every other `SessionStart` entry through untouched.
   - Write the mutated object back.
3. If `.claude/settings.json` doesn't exist, create it from the template.
4. **Repoint stale script literals.** For every entry in `permissions.allow` and `permissions.deny`
   matching `Bash(.claude/<dir>/scripts/<basename>.sh<separator>*)` — where `<dir>` is exactly one
   path segment (`[^/]+`), `<separator>` is a single `:` or a single space, and `<basename>` is one of
   this plugin's template names in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/` other than
   `claude.sh`:
   - **First, the liveness guard:** `<dir>` must name a plugin that no longer exists by the test in
     item 5. A `<dir>` matching a currently-installed plugin's name — including this plugin's own — is
     **never** rewritten, so a literal already pointing at the right directory keeps its separator
     untouched. Skipping this guard churns `.claude/settings.json` on every run.
   - Otherwise rewrite it to `Bash(.claude/ds/scripts/<basename>.sh:*)`, normalising a space
     separator to `:`;
   - if the rewritten entry now duplicates one already in the list, keep one and drop the duplicate;
   - otherwise keep it even though `Bash(.claude/ds/scripts/*.sh:*)` subsumes it — a redundant allow
     entry is harmless, and removing one is a permission change this command is not entitled to make.
   - **Never rewrite a literal whose basename is not one of this plugin's template names.** Those
     belong to other plugins, whose inits carry the mirror-image rule.
   - **Only a dead plugin's directory is rewritten.** `<dir>` must name a plugin that no longer exists
     by the test in item 5. A `<dir>` matching a currently-installed plugin's name is **never**
     rewritten — including this plugin's own, so a literal already pointing at the right directory is
     left exactly as it is, separator and all. Rewriting it would churn the file on every run.
5. **Report-only.** A plugin name "no longer exists" when no directory under
   `<PLUGINS_ROOT>/claude_plugins/` declares that `name` in its `.claude-plugin/plugin.json`. List
   every `enabledPlugins` key, `Skill(<old>:*)`, or `mcp__plugin_<old>_*` entry naming such a plugin —
   but **not** a bare `mcp__<name>__*`, which is a directly-configured MCP server rather than a
   plugin-namespaced one and has nothing to do with any plugin — and point the user at `Skill(sdd:update-claude-project-settings)`. Do not
   remove them — narrowing permissions is the user's decision.

   Also report every literal Step 1 item 4 repointed **to a different directory** where the original
   path still exists on disk (skip this when the rewrite only normalised a separator within the same
   directory — there is nothing to port to, the paths name the same file):

   > Repointed `<old literal>` → `<new literal>`, but `<old path>` still exists. If you customised it,
   > port your changes into `.claude/ds/scripts/<name>.sh` — the permission now points there.
6. Report what was added or changed.

## Step 2: Create or extend `.claude/ds/config.md`

1. Ensure `.claude/ds/` exists.
2. If `.claude/ds/config.md` does not exist, copy `${CLAUDE_PLUGIN_ROOT}/templates/config.md`
   verbatim.
3. If it exists, add any section or key the template defines but the file lacks, using the template's
   default. Preserve every existing value, comment, and ordering.
4. **Do not prompt for these values.** Tell the user in the summary where the file is and that they
   should review the base URL, the dev credentials, the Alpine CSP-build flag, and the two admin
   flags — the defaults assume plain Django admin with no django-guardian and no dev login, which is
   wrong for any project that has them.

## Step 3: Update `.gitignore`

1. If `.gitignore` does not exist at the project root, create it.
2. If `.claude/ds/config.local.md` is not listed, add it.
3. If `.claude/settings.local.json` is not listed, add it.

Place each new entry next to its siblings if a `# Claude` block already exists; otherwise append.

## Step 4: The launcher

Follow `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md` end to end, using the P4 classification
and the resolved `PLUGINS_ROOT`. That procedure creates the launcher when absent, normalises a
one-line launcher so a standalone `"$@"` line exists, inserts `PLUGINS_ROOT=` before any line that
expands it, retires a pre-`claude_plugins` argument, guarantees exactly one `django-stack`
`--plugin-dir` line, and migrates the sentinel.

Write the launcher as **one atomic file replacement** at the end of the procedure, not as a sequence
of in-place edits. L2–L6 pass through intermediate states in which the sentinel the launcher sets and
the sentinel the hook checks disagree; an interruption mid-sequence would leave a project that
hard-fails every session.

## Step 5: Wrapper scripts — install missing, then migrate existing

1. Ensure `.claude/ds/scripts/` exists.
2. For each template in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/` other than `claude.sh`: if
   a script of that name does not yet exist under `.claude/ds/scripts/`, copy it there, replace
   `__PLUGINS_ROOT__` with the resolved value, and `chmod +x`. Never overwrite an existing file.
3. For **every** `.sh` now under `.claude/ds/scripts/`, apply
   `${CLAUDE_PLUGIN_ROOT}/resources/wrapper_script_migration.md` — including the ones just created
   (where every rule will be a no-op) and any a previous run or another plugin left behind. That
   procedure decides on its own which files it may touch.

## Step 6: Retire the legacy `CLAUDE.md` plugin-check line

An older init **prepended** one line telling Claude to check the plugin-loaded sentinel each session;
the `SessionStart` hook does that now. But this is the user's own `CLAUDE.md`, so remove the line only
on an exact structural match.

1. Read `CLAUDE.md` at the project root. If absent, skip.
2. Consider **line 1 only**. It qualifies only if, after collapsing runs of whitespace to a single
   space, it matches this shape exactly:

   ```
   If ${NAME} is unset, stop and tell the user to run `./claude.sh` instead of `claude`.
   ```

   where `${NAME}` is `$` followed by an identifier, optionally brace-wrapped. Nothing else
   qualifies. A line that merely *mentions* the sentinel, a line documenting the launcher, a line the
   user wrote — none match this shape, and none is removed.
3. If line 1 qualifies: delete line 1. Then delete line 2 **only if** line 2 is blank. If line 2 is
   not blank, leave it and delete nothing further. **Report the deletion explicitly in the Step 8
   summary, quoting the removed line** — this is the only edit this command makes to a file the user
   authored, and it must never be silent.
4. If a line matching that shape appears anywhere **other than line 1**, do **not** delete it.
   Report: "`CLAUDE.md:<n>` looks like a leftover plugin check but is not line 1 — left alone; delete
   it yourself if it is stale."
5. If a line elsewhere merely mentions the sentinel name, say nothing — that is normal documentation.

## Step 7: Validate the setup

Run these checks and report results. A failure here is reported, never fixed silently.

1. `ds` is in `enabledPlugins` in `.claude/settings.json`, and the file is valid JSON.
2. `claude.sh` exists at the project root, is executable, uses `CLAUDE_PLUGINS_LOADED=1`, declares
   `PLUGINS_ROOT`, and carries exactly **one non-comment `--plugin-dir` argument** whose final path
   segment is `django-stack`. Count arguments, not lines containing the string — the template's own
   header comment mentions `--plugin-dir` and must not be counted.
3. Every `--plugin-dir` path in `claude.sh` resolves to a directory that exists.
4. Every wrapper script under `.claude/ds/scripts/` is executable and passes `bash -n`.
5. The `SessionStart` hook in `.claude/settings.json` checks `$CLAUDE_PLUGINS_LOADED`.
6. Every wrapper under `.claude/ds/scripts/` classified **Managed** by Step A of the migration
   resource declares `PLUGINS_ROOT`
   with the resolved value — no `__PLUGINS_ROOT__` and no `FLS_PATH` — and its `PLUGIN_DIR` resolves
   to a directory that exists. Files classified User-authored are exempt and listed as untouched.

   Header comments are checked separately and are **not** a hard failure: migration rules 2 and 3 only
   fire when the file carries a recognisable header line or prose block, so a hand-written wrapper can
   legitimately have neither. If a Managed file's header does not name the `django-stack (ds)` plugin
   and `ds:init`, report it as an outstanding action ("no recognisable header line to migrate — fix by
   hand if you want it to track the template"), not as a validation failure with no remedy.
7. `CLAUDE.md` line 1 is not a legacy plugin-check line.
8. **`hooks` is intact.** Compare against the P3 snapshot: every event other than `SessionStart` is
   present and deep-equal, and every `SessionStart` entry that is not this command's own is present
   and deep-equal. Any difference is a defect — report it and tell the user to restore from git.
9. `.claude/ds/config.md` has a `## Project Settings` section with a `Dev base URL` key, a
   `## Dev Credentials` section with `Admin email` and `Admin password` keys (blank values are
   valid), an `## Alpine.js` section with a `CSP build` value, and an `## Admin` section with both
   `Admin theme` and `Object permissions (django-guardian)` values.
10. Report every issue found.

## Step 8: Summary and outstanding actions

Print what was done, then the outstanding actions: every Step 0 WARN, every file a step declined to
touch and why, and every report-only finding from **Step 1, item 5**. Point the user at
`.claude/ds/config.md` for the base URL, dev credentials, Alpine CSP-build flag, and admin flags. If
`PLUGINS_ROOT` resolved to `.` but this project holds `claude_plugins/` elsewhere (e.g. a submodule),
tell them to edit `PLUGINS_ROOT` in `claude.sh` and re-run.

**If any plugin under `<PLUGINS_ROOT>/claude_plugins/` has no `--plugin-dir` line in `claude.sh`,
this is the most consequential outstanding action and must be listed first** - always, not only when
the launcher step retired a pre-split argument. A plugin without a line is simply not loaded, and
nothing else in the session will hint at why.

Count a plugin only when it actually wires itself into the launcher: it must ship
`commands/init.md` **and** that file must mention `--plugin-dir`. A plugin whose init does something
else entirely — scaffolding a config file, installing a validator's dependencies — is not a
launcher-loaded dev plugin, and telling the user to run it would be wrong advice that repeats on every
future run. Skip those silently. Take the command prefix from `.claude-plugin/plugin.json`'s `name`,
never from the directory name. `claude.sh` now loads only `django-stack`. List every
other plugin under `<PLUGINS_ROOT>/claude_plugins/` and tell the user to run each one's init to
restore it. **Take the command prefix from each plugin's `.claude-plugin/plugin.json` `name` field,
not from its directory name** — the directory `django-stack` holds the plugin named `ds`, so the
command is `/ds:init`, and `/django-stack:init` does not exist — until they do, those plugins are not loaded, and any config dir
they own is left exactly as it was for their own init to migrate.
