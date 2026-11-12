---
description: Keep the spec roadmap (spec_dd/1. next/roadmap.md) in sync with the spec directories, or cut a big idea into ordered, dependent specs and add them to it
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill
argument-hint: [<spec-dir to cut>]
---

This command owns the spec roadmap, `spec_dd/1. next/roadmap.md`: what is up next, then every
spec waiting in `spec_dd/1. next/` or in flight in `spec_dd/2. in progress/`, grouped by feature,
with its state, its blockers and a dependency diagram. It runs at **depth 0**.

Read `${CLAUDE_PLUGIN_ROOT}/resources/roadmap_format.md` first. It defines the file's shape, how a
directory is classified, and the bullet grammar. Everything below assumes it. The script
`${CLAUDE_PLUGIN_ROOT}/scripts/roadmap.py` derives statuses, "Up next" and the diagrams; never
write those by hand.

Two modes:

- **No argument: sync.** Reconcile the roadmap with the directories on disk.
- **A directory under `spec_dd/`: cut.** Take one idea or spec that is too big for one SDD run, do
  the research and the questioning it needs, cut it into ordered sibling specs, write one
  decision-complete idea per spec, and add the effort to the roadmap. A cut ends with a sync.

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents (the `claude-code-authoring`
skill explains why).

1. **Start the work; don't ask permission for it.** Never ask the user whether to research, scan
   or fan out: spawn the workers. Subagents can't use `AskUserQuestion`, so bake into each prompt
   everything the worker needs from what the user has already said and what is on disk. Questions
   only the user can answer are asked at depth 0 *while* the workers run: as early as possible,
   batched up to four per `AskUserQuestion`. Never ask what a worker or the code will answer, and
   never hold a worker back for an answer it doesn't need.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`);
   intermediate outputs go in `.sdd-work/` at the project root, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`;
   spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"`
   (or `"sdd:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in
   inputs. Never one worker looping over the batch. Never use the `Workflow` tool for this: it
   puts a permission dialog in front of the owner, which amounts to asking whether to do the work
   they already asked for. The number started at once follows the memory capacity rule in point 4 of `fanout_recipe.md`.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include
   the prior error); `blocked` → supply the listed `needs` from the source, the code or another unit's
   output if they can; ask via `AskUserQuestion` only if they can't. Then re-spawn a fresh worker
   with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step.** Read the output *files* (pass paths, never dump contents into
   the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Once the phase artifact is finalised, delete this command's own scratch
   files **by name**, never the `.sdd-work/` directory itself.

---

# Sync mode

## S1: Read

Read `spec_dd/1. next/roadmap.md`. If it does not exist, start from the skeleton in the format
file. List the top-level directories of `spec_dd/1. next/` and `spec_dd/2. in progress/`, and the
names in `spec_dd/3. done/` (each is `<timestamp>_<name>`; match dependencies on the `_<name>`
suffix).

## S2: Classify

Sort every directory into effort parent, effort child or standalone per the format file, and note
where a *needs a cut* flag applies. An effort child belongs to the feature whose `Parent:` line
names its parent. A standalone spec belongs to the feature about the same area.

## S3: Diff

Work out, without writing anything yet:

- **Bullets to add**: a directory with no bullet (a parent gets a `Parent:` line, not a bullet),
  and the feature each goes in.
- **Bullets to drop**: a bullet whose directory is in neither `1. next/` nor `2. in progress/`.
  Say whether it is now in `3. done/` or is simply gone.
- **Blockers to correct**: a `blocked by` list that misses a prerequisite the spec's idea names,
  or names something that is not one.
- **Precursors to add**: a bullet that needs a cut but has no `Before starting:` sentence.
- **Format to fix**: anything that breaks the format file's rules: a spec named by number or
  shorthand, finished work mentioned, notes that are long, repeated or about done specs.

## S4: Write the new bullets (fan-out)

Each bullet to add needs a scope of at most 20 words, its blockers and any needs-a-cut reason,
read from the directory's idea or spec. When four or more are missing, spawn one `sdd:sdd-worker`
per directory writing `.sdd-work/roadmap_entry_<dir>.md` with:

- `scope:` one line, at most 20 words, in the project's words
  (`${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`), saying what ships and for whom.
- `depends_on:` bare directory names the idea or spec names as prerequisites, matched against the
  list of known directories you bake into the prompt. Anything it names that matches nothing goes
  under `unresolved:` with the sentence that implied it.
- `feature:` the existing feature it belongs to (list them in the prompt), or a proposed new one.
- `needs_cut:` the reason, or `none`.
- `status:` footer.

With fewer than four, read the ideas at depth 0 and write the bullets yourself. A `needs_cut:`
reason becomes the bullet's precursor: `` Before starting: cut it with `/sdd:roadmap <dir>`
(<reason>). ``

## S5: Confirm

Print the diff: adds (with their features), drops, blocker corrections, precursors added, format
fixes and unresolved dependencies. A drop whose directory is neither done nor in progress is
called out on its own line. One `AskUserQuestion`: apply, or stop.

## S6: Edit and run the script

Edit the roadmap per `${CLAUDE_PLUGIN_ROOT}/resources/writing_standard.md`: add and drop bullets,
correct blockers, add a `##` feature section (heading, one-line intro, bullets) for a new feature,
and tighten any notes that break the format rules. Then run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/roadmap.py "spec_dd/1. next/roadmap.md"
```

Fix every `PROBLEM:` it prints and run it again until it prints `status: ok`. If it prints
`effort retired: <parent>`, move that parent to `3. done/` as `/sdd:finish_worktree` Step 4.5
does. Read `roadmap_diagrams/up-next.svg` and each feature SVG you changed as images, and check
the names are readable and nothing overlaps.

## S7: Clean up

Delete this run's `.sdd-work/roadmap_entry_*.md` files by name.

## S8: Commit

Delegate to `sdd:sdd-mechanic`: stage `spec_dd/1. next/roadmap.md` and
`spec_dd/1. next/roadmap_diagrams/`, and commit with
`git commit`, subject `roadmap: sync the spec roadmap`. Push only when the branch is not
`main` or `master`. Roadmap bookkeeping normally happens on `main` with no worktree, as in
`protected/move_spec_to_in_progress.md`, which commits there without pushing.

---

# Cut mode

The argument names a directory holding an idea (and possibly a spec, research files and nested
drafts) that will not fit one SDD run. One spec is one SDD run is one PR. The cut goes by
user-visible outcome, never by line count. The process is the one that produced the educator
interface rebuild: chart a map, research what the code and comparable systems can answer, put the
rest to the product owner, propose the cut, then write the ideas.

## C1: Read the directory

Read everything in it: the idea, the spec if there is one, every sibling `*.md`, every nested
directory. Read the roadmap too, so the cut can depend on efforts and specs that already exist.

If the idea already starts with the parent blockquote it has been cut. Stop and point at its
section of the roadmap.

## C2: Chart the map

Write `.sdd-work/roadmap_map_<dir>.md`, scratch that an interrupted run resumes from: if it already
exists, read it and carry on from the first unfinished item.

- **Destination.** What exists when the cut is done: N ideas under `spec_dd/1. next/`, each
  ready for `/sdd:spec_from_idea` without reopening a design question, and one effort section in
  the roadmap.
- **Notes.** What the source already settles: users, capability list, constraints, what is kept
  and what is thrown away.
- **Decisions so far.** Empty at first; C3 fills it.
- **Not yet specified.** Every question the source leaves open that a boundary or an order depends
  on.
- **Out of scope.** What the source excludes.
- **Research units.** For each "not yet specified" item that the codebase, a comparable system
  or a mechanic can answer: a topic, the question, and the output path
  `<dir>/research_<topic>.md`.
- **Questions for the owner.** Each item that passes the test in C3 and that only the product
  owner can answer: the question, and the research unit (if any) whose findings it waits on.
- **Assumptions.** Defaults taken instead of asking (see C3).

Do not show the map for approval. Go straight to C3.

## C3: Research and ask, together

Research and questioning run at the same time, but no question goes to the owner if research could
answer it.

1. **Fan out now.** Apply the recipe: one `sdd:sdd-worker` per research unit, all spawned in
   parallel in the background, each writing its durable `research_<topic>.md` in `<dir>` with a
   `status:` footer and reference URLs for web-sourced findings. These are the files
   `setup_todo_list.md` already detects, so keep the naming.
2. **Ask early, in batches.** While the workers run, ask every queued question that waits on no
   research unit. Batch them, up to four per `AskUserQuestion`, so the owner answers while the
   research runs. A question that waits on a unit stays queued until that unit lands.
3. **Fold in each research file as it lands.** Read it. Move what it settles into "Notes" or
   "Decisions so far". Strike every queued question it answers or makes moot. Queue the new
   owner-only questions it raises, and ask them in the next batch. For each new question the code
   or a comparable system can answer, add a research unit to the map and spawn it at once.
4. **Record answers as they arrive** under "Decisions so far".

Repeat 2 to 4 until no worker is running and no question is open.

**What earns a question.** Ask only when all three hold:

- The answer changes a boundary between children, their order, or what a child idea settles.
- The source, the code, a finished research file or a still-running unit cannot answer it.
- There is no default the owner would obviously accept. If there is one, take it and record it
  under "Assumptions" in the map, with the reason. It surfaces in the cut proposal (C4), where the
  owner can overrule it, and ends up in the effort's "Assumptions the ideas make".

Never ask whether to research, whether to draft the child ideas, whether the map looks right, to
confirm what the source already says, or anything with one sensible answer. Never ask when or where
to produce something the cut can produce itself, such as a design brief the source asks for:
produce it in the cut (see C5). Each question quotes the source line or research finding that
leaves it open, and offers concrete options with the recommended one first. Name things per
`${CLAUDE_PLUGIN_ROOT}/resources/domain_vocabulary.md`.

## C4: Propose the cut

Write `.sdd-work/roadmap_cut_<dir>.md`:

- The effort name and the parent directory.
- For each child: its future directory name `<dir>-N-<slug>`, one-line scope, blockers (as
  directory names, never numbers), and the `research_*.md` files that move into it.
- Research that stays in the parent because more than one child uses it.
- Superseded drafts in the parent that the cut replaces, listed for the owner to confirm.
- The feature's **Notes**, in the words the roadmap will carry and within the format file's
  limit of about ten one-line bullets: build order and which children run in parallel, collisions
  where two children touch the same files, decisions taken, assumptions the ideas make, open
  questions with the child that owns each, one line of out-of-scope and one line of references.
  Every spec is named by directory name. Detail beyond that goes in the ideas, which are
  decision-complete, or in a sibling file in the parent.

Print it. `AskUserQuestion`: accept, adjust (loop back with the changes), or stop.

## C5: Write the child ideas

One `idea.md` per child at `spec_dd/1. next/<dir>-N-<slug>/`, to the child header and section
list in the format file, written per the writing standard and the rules in
`${CLAUDE_PLUGIN_ROOT}/resources/idea_standard.md`. Each is decision-complete: everything settled in
C3 that the child needs is stated as fact under "What is settled", and nothing claimed by a sibling
is claimed again.

With more than three children, fan out: one `sdd:sdd-worker` per child writing
`.sdd-work/roadmap_idea_<slug>.md`, its prompt carrying the paths of the cut file, the map, the
research files that move into that child, the writing standard, the vocabulary file, and the
sibling scopes. Then, at depth 0, read each draft against the cut and write the final `idea.md`
without the worker's footer. With three or fewer, write them at depth 0 directly.

When the source asks for work done outside an SDD run, such as mockups drawn in a design tool,
write its brief in the same pass as the ideas: `<dir>/design_brief.md` (or a name that fits),
covering every screen and state the children need, in the project's words. It stays in the
parent as a shared reference. The children that build to its output say so under "Resources".

## C6: Move research and mark the parent

Delegate to `sdd:sdd-mechanic`, with the cut file's path:

- `git mv` each research file into the child the cut file names.
- Prepend the parent blockquote from the format file to `<dir>/idea.md`, filled in.
- Delete only the superseded drafts the owner confirmed in C4. Nested directories the cut does not
  cover stay where they are; the feature's notes name each in one line as not yet cut.

## C7: Update the roadmap

Run S1 to S6. The new children classify as effort children from their header lines, the parent
as an effort parent from its blockquote. The parent's old bullet goes: the cut was its precursor.
The new feature section carries the children's bullets and the cut file's Notes.

## C8: Clean up

Delete `.sdd-work/roadmap_map_<dir>.md`, `.sdd-work/roadmap_cut_<dir>.md` and every
`.sdd-work/roadmap_idea_*.md` by name.

## C9: Commit

As S8, staging the child directories, the parent idea, the moved research files and the roadmap.
Subject: `<dir>: cut into N specs and update the spec roadmap`.

---

Neither mode ticks a `todo.md`. The roadmap belongs to the backlog, not to one spec.
