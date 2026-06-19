# Research: Wiring "update author plugin" into the SDD Workflow

## 1. Where the Check Belongs

### Candidate Stages

**Option A — `todo.md` checklist item (between "Product documentation" and "Pull request")**

The `todo.md` template in `protected/setup_todo_list.md` is the single source of truth for workflow progression. Adding a `(cmd)` item there gives it parity with every other workflow step: it shows up as a reminder, it ticks itself when done, and it can be skipped (left unchecked and overridden by the user) with zero code change. The downside is that every SDD run gets the item, even those that never touch course-authoring functionality — but a fast skip (see §5) eliminates the cost.

**Option B — Addition to `update_product_docs`**

`update_product_docs` already has the conceptual shape: it reads the spec and plan, decides what changed, and updates documentation. Adding a second branch ("if authoring-relevant, also update the author plugin") keeps related work together. The drawback is coupling two distinct doc targets inside one command, making it harder to maintain and harder to skip independently.

**Option C — A new dedicated `update_author_plugin` command**

A standalone `/update_author_plugin` command would be the cleanest encapsulation, but it adds a third doc-update step into an already long workflow. As a dedicated command it can be called outside of SDD too, which is a mild plus.

**Option D — A skill the workflow invokes**

A skill (`fls-claude-plugin/skills/author-plugin-sync/SKILL.md`) codifies the detection heuristic and update procedure so any command can invoke it. This is primarily a documentation/instruction layer, not an execution layer — the skill must still be called from somewhere (a todo item, a command, or from inside `update_product_docs`).

### Recommendation: `todo.md` checklist item + detection heuristic inline

The lightest viable integration is **a single new checklist item** in the `todo.md` template, placed in a new "10.5" section between "Product documentation" and "Pull request" (or appended to section 10):

```
- [ ] (cmd) Run `/update_author_plugin` to sync the author plugin if course-authoring functionality changed
```

This new `(cmd)` resolves to a small command file (`fls-claude-plugin/commands/sdd/update_author_plugin.md`) that:

1. Runs the detection heuristic (§2) — cheap, reads `git diff main`.
2. If nothing authoring-relevant changed: ticks its own box and exits. No fan-out. No edits.
3. If changes are detected: fans out one worker to draft the update, applies it, ticks the box.

The alternative of extending `update_product_docs` would hide the author-plugin update behind a step that runs regardless of whether the author plugin is relevant, making the step harder to audit and making `update_product_docs` do two things. Keeping it separate makes the "is this authoring-relevant?" decision visible in the workflow checklist.

Trade-offs summary:

| Option | Visibility | Isolation | Zero-cost skip | Ease of invocation outside SDD |
|---|---|---|---|---|
| Checklist item + command | High | Clean | Yes (via skip) | Yes (direct command) |
| Extend `update_product_docs` | Hidden | Mixed | Harder | N/A |
| New command only (no checklist) | Invisible | Clean | N/A | Yes |
| Skill only | N/A | N/A | N/A | Requires caller |

---

## 2. The Detection Heuristic

The heuristic should answer: "Did this SDD branch touch course-authoring functionality?" It should run in seconds without spawning workers.

### Authoring-relevant file patterns

A change is authoring-relevant if `git diff main -- <paths>` produces any output for:

```
freedom_ls/content_engine/schema.py
freedom_ls/content_engine/templates/cotton/*.html
config/settings_base.py           # covers MARKDOWN_ALLOWED_TAGS, ADMONITION_TYPES
freedom_ls/content_engine/management/commands/content_save.py
freedom_ls/content_engine/management/commands/content_validate.py
demo_content/**
```

These cover:
- New or changed content types / frontmatter fields (`schema.py`)
- New or changed `c-*` cotton widgets (`templates/cotton/*.html`)
- Widget tag registration (`MARKDOWN_ALLOWED_TAGS` in `settings_base.py`)
- Ingestion pipeline changes (`content_save.py`, `content_validate.py`)
- Changed demo content conventions (`demo_content/`)

### Implementation

One shell command is sufficient:

```bash
git diff main --name-only | grep -qE \
  '(freedom_ls/content_engine/schema\.py|freedom_ls/content_engine/templates/cotton/|config/settings_base\.py|freedom_ls/content_engine/management/commands/content_(save|validate)\.py|demo_content/)'
```

Exit code 0 = authoring-relevant change found; exit code 1 = no match, skip.

The command file reads the exit code and branches accordingly. No LLM required for detection.

---

## 3. The Update Action

### What the update does

When the heuristic flags a change, the author plugin must be updated so its documentation of:

- content types and frontmatter fields (from `schema.py`)
- the `c-*` widget catalog (from `templates/cotton/` + `MARKDOWN_ALLOWED_TAGS`)
- numbering/organisation conventions (from `demo_content/` and `content_save.py`)
- UUID rules (unchanged but must not drift)

…stays accurate.

### Source of truth

The sources the worker reads, in priority order:

1. `freedom_ls/content_engine/schema.py` — canonical field definitions
2. `freedom_ls/content_engine/templates/cotton/` — canonical widget implementations
3. `config/settings_base.py` (`MARKDOWN_ALLOWED_TAGS`) — which widgets are registered and which attributes each accepts
4. `fls-claude-plugin/resources/markdown_content.md` — existing resource (already kept up to date by the team)
5. `demo_content/` — living examples of numbering and organisation conventions

### Who does the editing

The update action should follow the same fan-out shape as `update_product_docs`:

1. Spawn one `fls:sdd-worker` to read the diff, identify what changed in authoring-relevant files, and produce a draft of the required plugin updates (writing to `.sdd-work/author_plugin_update.md`).
2. Depth-0 synthesis step applies the edits to the author plugin files (the `SKILL.md` and any companion resource files under the new `course-author-plugin/` directory).

The worker is scoped to authoring-relevant changes only by the heuristic output — pass the grep result and the list of changed authoring files in the worker prompt to keep it focused.

### What it must NOT do

- Do not rewrite the whole author plugin. Edit only the sections that correspond to changed files.
- Do not touch plugin files unrelated to the changed content (e.g. do not modify the "UUID rules" section if nothing in `schema.py` changed the UUID handling).
- Do not add implementation details beyond what is expressed in the source of truth files.

---

## 4. Concrete Edits Needed

### A. `fls-claude-plugin/commands/sdd/protected/setup_todo_list.md`

In Step 4's checklist template, insert a new item in section 10 or as a section 10.5 between "Product documentation" and "Pull request":

```markdown
## 10.5. Author plugin sync

- [ ] (cmd) Run `/update_author_plugin` to sync the course-author plugin if authoring functionality changed
```

The existing section numbering in the todo template goes 10 → 11. To avoid renumbering pull-request and cleanup, insert the new section between 10 and 11 with the 10.5 label, or append it to section 10:

```markdown
## 10. Product documentation

- [ ] (cmd) Run `/update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation
- [ ] (cmd) Run `/update_author_plugin` to sync the course-author plugin if authoring functionality changed
```

Both approaches work. A flat sub-item inside section 10 is marginally simpler (no new section header) and avoids the awkward "10.5" numbering. However, a dedicated section makes it easier for `/sdd:next` and humans to locate and skip independently.

**Preferred wording** (dedicated section):

```markdown
## 11. Author plugin sync

- [ ] (cmd) Run `/update_author_plugin` to sync the course-author plugin if authoring functionality changed
```

Then renumber the existing sections 11 → 12 and 12 → 13.

### B. New file: `fls-claude-plugin/commands/sdd/update_author_plugin.md`

Sketch:

```markdown
---
description: Sync the course-author plugin if this SDD run touched course-authoring functionality
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, Agent
---

Update the course-author Claude Code plugin to reflect any changes to course-authoring functionality
made by this SDD run. This command is a **fast no-op** when nothing authoring-relevant changed.

## Step 1: Detect authoring-relevant changes

Run the detection heuristic:

    git diff main --name-only | grep -qE \
      '(freedom_ls/content_engine/schema\.py|freedom_ls/content_engine/templates/cotton/|config/settings_base\.py|freedom_ls/content_engine/management/commands/content_(save|validate)\.py|demo_content/)'

If the grep finds no matches (exit code 1): print "No authoring-relevant changes detected — author plugin unchanged." Then go directly to Step 4 (tick the todo box) and exit.

If the grep finds matches (exit code 0): note the list of changed files and proceed to Step 2.

## Step 2: Draft the plugin update (fan-out)

Spawn one `fls:sdd-worker` to write `.sdd-work/author_plugin_update.md`. Pass in:

- The list of changed authoring-relevant file paths from Step 1.
- Instruction to read those files and identify exactly what changed (new/removed/modified: content types, widget tags, frontmatter fields, `MARKDOWN_ALLOWED_TAGS` entries, convention examples).
- Instruction to produce a concrete, scoped set of edits to the author plugin's skill files (the new `course-author-plugin/` directory — paths TBD once the plugin is built).
- Instruction to base every statement on the actual file contents, not inference.
- Instruction to end the file with `status: ok` on success, `status: failed` + `reason:` on failure, `status: blocked` + `needs:` if inputs are unclear.

Apply the standard resume/retry/blocked recipe from the fan-out recipe.

## Step 3: Apply the edits

Read `.sdd-work/author_plugin_update.md`. Apply each proposed edit to the relevant author plugin file using `Edit`. Use `Write` only if a file is new.

Do not touch sections of the author plugin that the worker did not flag as needing changes.

Delete `.sdd-work/` after all edits are applied.

## Step 4: Tick the todo

Delegate to `fls:sdd-mechanic`: invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory
- `tick:"Run \`/update_author_plugin\` to sync the course-author plugin if authoring functionality changed"`

No new items to add.
```

### C. `fls-claude-plugin/commands/sdd/README.md`

Add a step between "Update product docs" and "Ship it":

```markdown
## Step 8.5: Sync the author plugin (if authoring functionality changed)

Run `/update_author_plugin`. The command detects in under a second whether this SDD run touched course-authoring functionality (content types, widgets, frontmatter, ingestion pipeline, demo content conventions). If nothing changed, it ticks its box and exits immediately. If something changed, it fans out one worker to draft the necessary plugin updates and applies them.
```

### D. Checklist auto-detection in `setup_todo_list.md`

Optionally, add a row to the artifact-detection table so that if `.sdd-work/author_plugin_update.md` already ends with `status: ok`, the checklist item is pre-ticked on resume. This is minor and can be deferred.

---

## 5. Avoiding Heaviness

### The fast-skip guarantee

Step 1 of `update_author_plugin` is a single `git diff main --name-only | grep` pipe — it runs in milliseconds and costs zero tokens. If it returns exit code 1, the command logs one line and ticks its box. The total overhead on non-authoring SDD runs is:

- One Bash call (the grep).
- One mechanic spawn to tick the todo box.

That is comparable to the todo-tick overhead already present in every existing SDD command. There is no worker spawn, no LLM inference, no file writes to `.sdd-work/`.

### Keeping the worker scoped

When the heuristic does fire, the worker's brief includes only the list of changed authoring-relevant files, not the entire diff. The worker reads those specific files, not the whole codebase. This prevents the update from ballooning into a full-plugin rewrite.

### No screenshot lifecycle

Unlike `update_product_docs`, the author plugin is a Claude Code plugin (Markdown files, no visible UI). There is no screenshot step, no dev server, no Playwright.

### No review dimension fan-out

The update is narrow (changed authoring files → changed plugin sections). A single worker producing a concrete diff and a depth-0 synthesis applying it is sufficient. No multi-dimension review fan-out is needed.

---

status: ok
