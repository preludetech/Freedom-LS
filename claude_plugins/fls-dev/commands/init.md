---
description: Initialise the fls-dev plugin for a project
allowed-tools: Read, Write, Edit, Bash, Glob
---

# Initialize the fls-dev Plugin

Set up the `fls-dev` Claude Code plugin for this project.

## Two rules that override every step below

**Nothing is written before Step 0 finishes.** Step 0 performs every check that can abort this
command, and computes every move/delete/keep verdict the later steps act on. If Step 0 returns STOP,
print the reason and the fix and end — the project is byte-for-byte untouched, so re-running after
the fix is always safe and always starts from a clean state. No step after Step 0 may abort: from
Step 1 onward, a problem is *reported as an outstanding action*, never raised as a bail-out.

This ordering is the whole point. An earlier version of this command renamed a directory and deleted
files in its first two steps, then discovered in a later step that `/ds:init` had not run and aborted
— leaving a mutated project and no clean way back.

**Nothing is force-deleted.** No step may pass `-f` to `git rm`, `-f`/`-r` to `rm`, or `--force` to
any command. If a deletion is refused — by git, by the filesystem, or by a guard in this file — the
file stays where it is and the refusal is reported. A file this command cannot prove is disposable is
not disposable.

## Scope

`fls-dev:init` is **plugin-bootstrap only.** It wires the `fls-dev` plugin into an existing project.
It does NOT scaffold Django project structure — `config/`, `pyproject.toml`, Tailwind config, a
`CLAUDE.md` skeleton, or a `.claude/settings.json` from scratch. Those come from the template repo.

It owns the `fls-dev` slice: its `enabledPlugins` key, its permissions, its `.claude/fls-dev/` config
dir, and its dev/DB wrapper scripts. Into the shared `claude.sh` it adds **only its own**
`--plugin-dir` line.

It has one deliberate reach outside that slice: migrating a legacy `.claude/fls/` config dir splits
its contents between `.claude/fls-dev/` and `.claude/ds/scripts/`, because the pre-split dir held
both plugins' wrappers. Step 2 does that relocation and nothing else in `.claude/ds/`.

`/ds:init` must have run first — Step 0 enforces it.

## Hard requirements — do not regress

- **`.claude/settings.json`** — merge, don't replace. Add missing `fls-dev`-owned `allow` entries and
  `"fls-dev": true` to `enabledPlugins`. Never replace the whole file and **never touch the `hooks`
  section** — the `SessionStart` hook is `ds`-owned. Mutate the file's own parsed object and write it
  back; never rebuild it from a template. Steps 1.4 and 2.3 rewrite *stale path literals* in place —
  that is a rename of an existing entry, not a removal, and it is the only exception. **"Missing" means no byte-identical string is
  already in the list** — never "no entry semantically covers this". A redundant allow entry is
  harmless; removing one is a permission change this command is not entitled to make.
- **`.claude/fls-dev/config.md` / `config.local.md`** — create when absent, otherwise extend. Add any
  option the template defines but the file lacks; preserve every existing value, comment, and
  ordering. Never overwrite or delete existing config.
- **`.gitignore`** — append only the `fls-dev`-owned line. Never remove or reorder, and leave the
  `ds`-owned `.claude/settings.local.json` line alone.
- **Wrapper scripts** — install a template only when the destination does not exist. An existing
  script is never overwritten or regenerated; it is migrated in place per Step 6.
- **Foreign-owned wrapper scripts** — a wrapper whose basename belongs to another plugin's template
  set never enters `.claude/fls-dev/scripts/`. Step 2a sends it from `.claude/fls/scripts/` straight
  to its owner: moved when the owner lacks it, deleted only when the owner already holds a copy
  **and** the legacy file is pristine by the appendix test in
  `${CLAUDE_PLUGIN_ROOT}/resources/wrapper_script_migration.md`, and otherwise kept and handed off. A
  customised file is never deleted. A basename **no** plugin ships is the user's own file — it is not
  foreign-owned, it migrates into `.claude/fls-dev/` like any other file, and nothing ever edits it.

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
4. **Validate before use.** Confirm `<PLUGINS_ROOT>/claude_plugins/fls-dev/` exists, relative to the
   project root. If it does not, **STOP** without writing anything:

   > Cannot find `claude_plugins/fls-dev/` under `PLUGINS_ROOT="<value>"`. Set `PLUGINS_ROOT` in
   > `claude.sh` to the relative path from the project root to the checkout that holds
   > `claude_plugins/`, then re-run this command. Nothing has been changed.

5. **Record it.** Every later step uses this one value. No step re-derives it and no step substitutes
   another.

## Step 0: Preflight — read everything, write nothing

Use only `Read`, `Glob`, and read-only `Bash` (`ls`, `test`, `diff`, `git status --porcelain`,
`git ls-files`). Do not create, modify, move, delete, `chmod`, `git mv`, or `git rm` anything in this
step or before it completes.

| # | Check | Verdict |
|---|---|---|
| P1 | `claude.sh` exists at the project root | **STOP** → "`/ds:init` owns the launcher. Run `/ds:init` first, then re-run `/fls-dev:init`. Nothing has been changed." |
| P2 | `.claude/settings.json` exists and parses as JSON | **STOP** → same message (or "hand-fix the JSON" if it exists but is unparseable) |
| P3 | `"ds": true` is in `enabledPlugins` | **STOP** → "`/fls-dev:init` relocates `ds`-owned wrapper scripts into `.claude/ds/scripts/`, which `/ds:init` must own first. Run `/ds:init`, then re-run `/fls-dev:init`. Nothing has been changed." |
| P4 | Resolve `PLUGINS_ROOT` by the rule above, including its step-4 validation | **STOP** if invalid |
| P5 | Classify `claude.sh` per rule **L0** of `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md` | **STOP** if it has zero, or more than one, non-comment line invoking `claude` (P1 already stopped on an absent file) |
| P6 | **Ownership survey.** For every `.sh` under `.claude/fls/scripts/`, decide whether its basename appears in the `templates/wrapper_scripts/` of this plugin, of some *other* plugin under `<PLUGINS_ROOT>/claude_plugins/` (**foreign-owned** — record the owner), or of none (**the user's own file**) | record |
| P7 | **Customisation survey.** For every `.sh` under `.claude/fls/scripts/` and `.claude/fls-dev/scripts/`, compute the pristine/customised verdict using the appendix of `${CLAUDE_PLUGIN_ROOT}/resources/wrapper_script_migration.md` — judging a foreign-owned file against **its owner's** template — and record whether it is dirty in git | record |
| P8 | **Relocation plan.** For each foreign-owned wrapper, decide `SEND` (absent at the owner), `DROP` (present at the owner and pristine), or `HAND-OFF` (present at the owner and customised), per Step 2a | record |
| P8b | **Legacy-dir survey.** For every remaining path under `.claude/fls/` — everything P8 did not claim — assign exactly one verdict: `MOVE`, `IDENTICAL`, `CONFLICT`, or `KEEP` (Step 2b defines them) | record — never a STOP |
| P9 | `git status --porcelain --` every file **under `.claude/fls/`** that the plan would move or delete | any dirty file downgrades its plan entry to `HAND-OFF` (or `KEEP`); **WARN**. Files outside `.claude/fls/` have no plan entry - `claude.sh` and `.claude/settings.json` are always dirty here because `/ds:init` just wrote them, which is expected and is a WARN only |

P3 is what makes the `ds` → `fls-dev` order enforced rather than merely documented.

## Step 1: Merge `fls-dev` permissions and enabledPlugins

1. Add these `allow` entries if missing (never duplicate):
   - `Skill(fls-dev:*)`
   - `Bash(.claude/fls-dev/scripts/*.sh:*)`
2. Add `"fls-dev": true` to `enabledPlugins`. Do not add or remove another plugin's key.
3. **Do not** add or modify the `SessionStart` hook, the `$CLAUDE_PLUGINS_LOADED` sentinel, or any
   other `hooks` entry — those are `ds`-owned.
4. **Repoint stale script literals.** For every entry in `permissions.allow` and `permissions.deny`
   matching `Bash(.claude/<dir>/scripts/<basename>.sh<separator>*)` — where `<dir>` is exactly one
   path segment (`[^/]+`), `<separator>` is a single `:` or a single space, and `<basename>` is one of
   this plugin's template names in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/`:
   - **First, the liveness guard:** `<dir>` must name a plugin that no longer exists by the test in
     item 5. A `<dir>` matching a currently-installed plugin's name — including this plugin's own — is
     **never** rewritten, so a literal already pointing at the right directory keeps its separator
     untouched. Skipping this guard churns `.claude/settings.json` on every run.
   - Otherwise rewrite it to `Bash(.claude/fls-dev/scripts/<basename>.sh:*)`, normalising a space
     separator to `:`;
   - if the rewritten entry duplicates one already present, keep one and drop the duplicate;
   - otherwise keep it even though `Bash(.claude/fls-dev/scripts/*.sh:*)` subsumes it — a redundant
     allow entry is harmless, and removing one is a permission change this command is not entitled to
     make.
   - **Never rewrite a literal whose basename is not one of this plugin's template names.** Those
     belong to other plugins, whose inits carry the mirror-image rule.
   - **Only a dead plugin's directory is rewritten.** `<dir>` must name a plugin that no longer exists
     by the test in item 5. A `<dir>` matching a currently-installed plugin's name is **never**
     rewritten — including this plugin's own, so a literal already pointing at the right directory is
     left exactly as it is, separator and all. Rewriting it would churn the file on every run.
5. **Report-only.** A plugin name "no longer exists" when no directory under
   `<PLUGINS_ROOT>/claude_plugins/` declares that `name` in its `.claude-plugin/plugin.json`. List
   every surviving `Skill(<old>:*)`, `mcp__plugin_<old>_*`, or `enabledPlugins` key naming such a
   plugin — but **not** a bare `mcp__<name>__*`, which is a directly-configured MCP server rather than
   a plugin-namespaced one and has nothing to do with any plugin - and any `.gitignore` line naming a
   `.claude/<name>/` directory that no longer exists, and point the user at `Skill(sdd:update-claude-project-settings)`. Do not
   remove them — narrowing permissions is the user's decision.
6. Write the mutated object back and report what changed.

## Step 2: Migrate a legacy `.claude/fls/` config dir

The product plugin was renamed `fls` → `fls-dev`, so a project set up by an older `/fls:init` has a
`.claude/fls/` dir. **Do not rename the directory as a unit.** The pre-split dir held both plugins'
wrappers *and* a `config.md` carrying real dev credentials, and its `config.local.md` is gitignored —
unrecoverable if destroyed. Act on the Step 0 verdicts, per path; do not re-derive them.

### 2a. Send foreign-owned wrappers straight to their owner

Do this **first**, straight out of `.claude/fls/scripts/`. Never route these files through
`.claude/fls-dev/scripts/`: a `git mv` into this plugin's directory stages a rename, and a bare
`git rm` then refuses with *"the following file has changes staged in the index"* — which, under the
no-force rule, would strand every one of them forever, carrying a `PLUGIN_DIR` that points at a
directory the split deleted.

A wrapper is **foreign-owned** when its basename appears in the `templates/wrapper_scripts/` of some
*other* plugin under `<PLUGINS_ROOT>/claude_plugins/`, and not in this plugin's. Judge it against
**that owning plugin's** template — this plugin ships no copy of it, so its own templates are not the
comparison basis. A basename in **no** plugin's template set is not foreign-owned and not a generated
wrapper: it is the user's own file. Leave it alone; step 2b moves it into `.claude/fls-dev/` with
everything else, and Step 6 will classify it User-authored and never touch it.

For each foreign-owned wrapper in `.claude/fls/scripts/`, with `<owner>` its owning plugin's config
dir (`.claude/ds/scripts/` for the `django-stack` plugin):

1. **Absent at the owner** — create the directory if needed, then `git mv .claude/fls/scripts/<name>.sh
   <owner>/<name>.sh` (plain `mv` if untracked). Contents are **not** edited: the owner owns that
   file's wording, and this command must not stamp its own header on another plugin's script.
2. **Present at the owner, and the legacy file is pristine** by the appendix test in
   `${CLAUDE_PLUGIN_ROOT}/resources/wrapper_script_migration.md` (judged against the owner's template)
   — the owner already has a working copy, so delete the legacy duplicate with `git rm`, **no `-f`**.
   This works precisely because the file is still at its original, unstaged path.
3. **Present at the owner, and the legacy file is customised** — keep it and report:
   > `.claude/fls/scripts/<name>.sh` carries changes and `<owner>/<name>.sh` already exists. Port your
   > changes into `<owner>/<name>.sh`, then delete the legacy file yourself.
4. Do **not** repoint permission literals for these basenames. Each plugin's own init repoints its
   own template names (Step 1 item 4 does it for this plugin's), and the owner's init has already run
   - P3 enforces that. Rewriting another plugin's literal here would duplicate work its init owns and
   could silently disagree with it.

### 2b. Walk everything else, per path

**MOVE** — no file exists at the same relative path under `.claude/fls-dev/`.
> Create parent directories, then `git mv .claude/fls/<rel> .claude/fls-dev/<rel>` (plain `mv` if
> untracked — this is how the gitignored `config.local.md` moves). Contents are neither read nor
> rewritten here.

**IDENTICAL** — a file exists at the same relative path and the two are byte-identical.
> Delete the legacy copy **only if** `git status --porcelain -- .claude/fls/<rel>` is empty. Use
> `git rm` **without** `-f`, or plain `rm` for an untracked unmodified file. If the status is
> non-empty, or the delete is refused for any reason, **keep the file** and report it.

**CONFLICT** — a file exists at the same relative path and the contents differ.
> Do not merge, overwrite, or delete either side. Copy the legacy file to
> `.claude/fls-dev/<rel>.legacy` — if that name is taken by a copy whose content is **identical** to
> the legacy file, the preservation this branch exists for is already done, so reuse it and write
> nothing; only when the existing `.legacy` differs do you append `.legacy.2`, `.legacy.3`, … . (A
> plain "append if taken" rule would mint a new sidecar on every re-run and never converge.) **Add
> `.claude/fls-dev/*.legacy*` to `.gitignore` if it is not already listed**, leave `.claude/fls/<rel>`
> where it is, and report:
>
> > `.claude/fls-dev/<rel>` and the legacy `.claude/fls/<rel>` differ. The legacy copy is preserved
> > at `.claude/fls-dev/<rel>.legacy`. Compare them, keep whichever values you want, then delete
> > `.claude/fls/<rel>` and the `.legacy` copy yourself. `/fls-dev:init` will not touch either again.
>
> `config.md` and `config.local.md` are the files this hits in practice, and both may hold real dev
> credentials. That is precisely why nothing here writes over either - and why the `.legacy` copy is
> gitignored rather than left for the next `git add -A` to commit those credentials.

**KEEP** — everything else: a path that is a directory on one side and a file on the other, a
symlink, or any file whose `git status --porcelain` is non-empty. Leave both sides untouched and
report.

### 2c. Tidy up

Remove now-empty directories under `.claude/fls/` **bottom-up** with `rmdir`, then `.claude/fls/`
itself — `rmdir` fails rather than recursing, so it can never take a file with it. (`git mv` leaves
the emptied `scripts/` behind, so `.claude/fls/` is never empty until that is removed first.) If any
file remains anywhere under it, leave the directory and list its contents as an outstanding action. A
surviving `.claude/fls/` is a reported outstanding action, never an error and never grounds for
deletion.

**If step 2a moved any file to another plugin's scripts dir, emit this mandatory outstanding action:**

> Moved N script(s) into `<owner>`. Run that plugin's init again to migrate them — it is idempotent,
> and it owns their variable names and header comments.

## Step 3: Create or extend `.claude/fls-dev/config.md`

**Do not prompt the user for these values.** The template carries dev defaults; write it and say
where it is.

1. Ensure `.claude/fls-dev/` exists.
2. If `.claude/fls-dev/config.md` does not exist, copy `${CLAUDE_PLUGIN_ROOT}/templates/config.md`
   verbatim. It ships with dev admin email `demodev@email.com`, the same password, and base URL
   `http://127.0.0.1:8000`.
3. If it exists, add any section or key the template defines but the file lacks, using the template's
   default. Preserve every existing value, comment, and ordering. If it already has everything, leave
   it untouched.
4. Tell the user in the summary to review the dev credentials and base URL — the defaults are only a
   starting point.

## Step 4: Create or extend `.claude/fls-dev/config.local.md`

1. If it does not exist, copy `${CLAUDE_PLUGIN_ROOT}/templates/config.local.md`.
2. If it exists, add any key the template defines but the file lacks. Preserve everything present.

This file carries machine-specific overrides, including the `## Template Repo` section where the user
records the absolute path to their local clone of the concrete-project template repo.
`/update_template_repo` reads that path; leave it blank if they don't maintain it locally.

## Step 5: Update `.gitignore`

1. If `.claude/fls-dev/config.local.md` is not listed, add it.
2. Leave the `ds`-owned `.claude/settings.local.json` line alone.

## Step 6: Wrapper scripts — install missing, then migrate existing

1. Ensure `.claude/fls-dev/scripts/` exists.
2. For each template in `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/`: if a script of that name
   does not yet exist under `.claude/fls-dev/scripts/`, copy it there, replace `__PLUGINS_ROOT__`
   with the resolved value, and `chmod +x`. Never overwrite an existing file.
3. For **every** `.sh` now under `.claude/fls-dev/scripts/`, apply
   `${CLAUDE_PLUGIN_ROOT}/resources/wrapper_script_migration.md`. That procedure touches only files
   whose basename is one of this plugin's own template names and which carry a `PLUGIN_DIR=` line and
   a `# === Project-specific setup ===` marker; everything else it reports and leaves alone. A
   `ds`-owned script Step 2 deliberately kept is therefore never restamped with an `fls-dev` header.

## Step 7: Ensure the `fls-dev` `--plugin-dir` line

Follow `${CLAUDE_PLUGIN_ROOT}/resources/launcher_editing.md`, using the P5 classification and the
resolved `PLUGINS_ROOT`. With `<MAY_CREATE>` false this runs L2, L3, L5 and L7 only — it normalises
the launcher shape, guarantees `PLUGINS_ROOT` exists before any line expands it, and ensures exactly
one `fls-dev` `--plugin-dir` line. It never creates the launcher, retires another plugin's argument,
or touches the sentinel. Write the launcher as **one atomic file replacement** rather than a sequence
of in-place edits.

## Step 8: Validate the setup

1. `fls-dev` is in `enabledPlugins`, and `.claude/settings.json` is valid JSON.
2. `.claude/fls-dev/config.md` exists and contains the dev email, password, and base URL keys.
3. Every wrapper under `.claude/fls-dev/scripts/` is executable and passes `bash -n`.
4. `.claude/fls/` is either gone, or every surviving path is listed in the outstanding actions with a
   per-file reason. For every surviving `.sh` under `.claude/fls/scripts/`, additionally check whether
   its `PLUGIN_DIR` resolves to a directory that exists, and if it does not, say so explicitly in the
   hand-off note: the file is preserved because it carries your changes, **but it will not run as-is**
   until those changes are ported and it is deleted.
5. `.claude/settings.json` contains `Skill(fls-dev:*)` and `Bash(.claude/fls-dev/scripts/*.sh:*)`,
   and no permission literal still points at `.claude/fls/scripts/`.
6. Every wrapper under `.claude/fls-dev/scripts/` classified **Managed** by Step A of the migration
   resource declares
   `PLUGINS_ROOT` with the resolved value — no `__PLUGINS_ROOT__` and no `FLS_PATH` — its header
   comments name `fls-dev` and `fls-dev:init`, and its `PLUGIN_DIR` resolves to a directory that
   exists. Files classified User-authored are exempt and listed as untouched.
7. Every basename under `.claude/fls-dev/scripts/` either appears in this plugin's
   `templates/wrapper_scripts/`, or appears in **no** plugin's — the user's own file, which belongs
   to them and is reported as untouched. A **foreign-owned** basename (one belonging to another
   plugin's template set) must not be here at all: Step 2a sends those to their owner without ever
   routing them through this directory. One surviving here is a defect, not a pass.
8. No `.claude/settings.json` permission literal points at a **foreign-owned** basename under
   `.claude/fls-dev/scripts/`. The `Bash(.claude/fls-dev/scripts/*.sh:*)` glob Step 1 adds is a
   wildcard, not a basename, and is always correct here - do not flag it.
9. Every file Step 2a sent to another plugin's scripts dir is listed in the outstanding actions
   alongside the "run that plugin's init again" instruction, and every `HAND-OFF` it declined to move
   is listed with its reason. Nothing under `.claude/fls/scripts/` was left carrying a foreign-owned
   basename without one of those two entries.
10. `claude.sh` contains exactly **one** `--plugin-dir` line whose final path segment is `fls-dev`,
    and every `--plugin-dir` path in it resolves to a directory that exists.
11. `hooks` in `.claude/settings.json` is unchanged from before this command ran.
12. Report every issue found.

## Step 9: Summary and outstanding actions

Print what was done, then the outstanding actions: every Step 0 WARN, every `CONFLICT` and `KEEP`
from Step 2, every `KEEP-AND-HAND-OFF`, the "run `/ds:init` again" instruction if any file moved, and
every report-only finding from **Step 1, item 5**. Point the user at `.claude/fls-dev/config.md` for the dev
credentials and base URL, and at `.claude/fls-dev/config.local.md` for the optional template-repo
path.
