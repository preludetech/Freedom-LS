# The spec roadmap

`spec_dd/1. next/roadmap.md` says what is being built next. It lists every spec in
`spec_dd/1. next/` and `spec_dd/2. in progress/`, grouped by feature, with its state and a
dependency diagram per feature, ordered by the priority file beside it (see "Priority"). `/sdd:roadmap` writes it. `protected/update_roadmap.md` removes a
finished spec. `/sdd:start` reads a spec's precursor, blockers and collisions. `scripts/roadmap.py` normalises
it and draws the diagrams.

It is the *spec* roadmap. `docs/product/roadmap.md` is the product roadmap and is a different file.

## Rules

1. **Name a spec by its directory name, in backticks, everywhere.** Never "spec 6", "6 cohort
   admin", "the second one" or any other shorthand, in bullets, notes or diagrams.
2. **Finished work is not mentioned.** A done spec has no bullet, appears in no `blocked by` list
   and is not discussed in notes. The roadmap is about what comes next.
3. **One bullet per directory.** Every top-level directory in `1. next/` and `2. in progress/` has
   exactly one spec bullet, except an effort parent, which a feature names on its `Parent:` line,
   and `roadmap_diagrams/`, which holds the SVGs. `priority.md` is a file, not a spec. `0. noop/`
   and `3. done/` are not indexed.
4. **Every spec belongs to a feature.** A feature is a `##` section: a cut effort, or a group of
   standalone specs about the same area. A spec that fits nowhere gets a new feature. Efforts
   that together make one larger piece of work share a feature, whose line names every parent:
   ``Parents: `a`, `b`.``
5. **The script owns the derived parts.** `python3 claude_plugins/sdd/scripts/roadmap.py
   "spec_dd/1. next/roadmap.md"` sets each bullet's status from its directory's location, drops
   done specs from bullets, `blocked by` lists and `Collides with` sentences, groups each feature's
   bullets under `###` subheadings by state (`In progress`, `Ready to start`, `Waiting on a
   collision`, `Needs work on main first`, `Blocked`; an empty group gets no heading; bullets keep
   their order inside a group), maintains `priority.md`, orders the feature
   sections and "Up next" by priority, writes each feature's `Priority:` line, regenerates "Up
   next", writes one SVG per feature (every feature, even one with a single spec) and
   `up-next.svg` into `spec_dd/1. next/roadmap_diagrams/` and retires an emptied feature. Run it
   after every edit. A new bullet can go anywhere in the feature's bullets: the script moves it
   into its group. Hand edits go in scopes, `blocked by` lists, `Collides with` sentences,
   precursors, feature intros, notes and `priority.md`.
6. **Notes stay lean.** At most about ten one-line bullets per feature: build order and which specs
   run in parallel, what colliding specs share (the collision itself is a `Collides with`
   sentence on a bullet), decisions and assumptions every spec in the feature
   relies on, open questions with the spec that owns each, one line of out-of-scope and one line of
   references. Only what still matters to an unfinished spec. No restated scope, no history, no
   process narration.
7. **A precursor keeps a spec off "Ready to start".** A precursor is work that has to happen on
   main before `/sdd:start` can branch a worktree off it, such as a cut. Sync writes one for a
   directory that needs a cut (below); a person may write one for any other job.

## Priority

`spec_dd/1. next/priority.md` says what matters most. People edit it; the script keeps it
complete.

```markdown
# Spec priority

<one paragraph on how to use the file>

## High

- `some-effort-parent`
- `some-standalone-spec`

## Medium

## Low

## Priority not set

- `another-effort-parent`
```

- Each `##` heading is a priority level, highest first. The level names are the file's own: rename,
  add or remove levels freely, up to six. `## Priority not set` is fixed and always ranks last.
- An entry is a spec directory or an effort parent (a feature's `Parent:`). A parent entry covers
  every spec in that feature with no entry of its own; in a feature with several parents, the
  highest of their entries does. Order inside a level counts: higher in the
  list is more important.
- **A spec inherits priority from its dependents.** Its effective priority is the highest of its
  own entry, its parent's entry and the effective priority of every spec that lists it, directly or
  through a chain, in `blocked by`. A high-priority spec makes all its prerequisites high too,
  wherever they sit in the file.
- The script creates the file when it is missing, adds every roadmap item it lacks under
  `## Priority not set` (the effort parent for a cut effort, the directory for anything else) and
  drops entries whose directory is gone. Listing a name twice is a `PROBLEM:`.
- The roadmap shows priority in colour: one marker per level (🔴 🟠 🟡 🟢 🔵 🟣 by position, ⚪ for
  not set). Each "Up next" bullet starts with its effective level and names the entry it inherited
  from (`via` …) when that is not its own or its parent's. Each feature gets a derived
  `Priority:` line with its highest level, and features are ordered by it. In the diagrams the box
  fill is still the status and a coloured bar on the left edge is the priority.

## Bullet grammar

```
- `<dir>` — **<status>**[ by `<dep>`, `<dep>`] — <scope>[ Collides with `<dir>`, `<dir>`.][ Before starting: <precursor>]
```

- `<status>` is exactly `in progress`, `ready` or `blocked`. The script sets it.
- `by` lists the dependencies that are not yet done, each a directory name in backticks. The
  script deletes a dependency once it is done, so the list is always the current blockers.
- `<scope>` is one line, at most 20 words: what ships and for whom.
- A collision is the sentence `Collides with `<dir>`, `<dir>`.` after the scope: specs that edit
  the same code and must not be built at the same time. It binds both sides, so naming it on one
  bullet is enough. The script drops a done spec from it and flags an unknown one. A `ready` spec
  that collides with an `in progress` spec is listed under "Waiting on a collision", not "Ready to
  start", and `/sdd:start` asks before starting it.
- A precursor is the sentence starting `Before starting:` at the end of the bullet. A `ready` spec
  with one is listed under "Needs work on main first", not "Ready to start".
- Notes bullets never start with `` `<dir>` — ** ``, so they are never mistaken for spec bullets.

## Classifying a directory

| Kind | Test |
|---|---|
| Effort parent | Its idea begins with the parent blockquote below, or a legacy `spec-order.md` sits in it. |
| Effort child | Its name is `<parent>-N-<slug>` for a known parent, or its idea's first paragraph after the title begins `Spec N of M in the … effort`. |
| Standalone | Anything else. |

Needs a cut: the directory holds more than one `idea*.md`, or nests a subdirectory containing an
`idea.md` or `1. spec.md`, or is empty. Its bullet ends `` Before starting: cut it with
`/sdd:roadmap <dir>` (<reason>). ``

## Skeleton

````markdown
# Spec roadmap

What is being built next, by feature. Maintained by `/sdd:roadmap`; the format is in
`claude_plugins/sdd/resources/roadmap_format.md`. The product roadmap is `docs/product/roadmap.md`.

## Up next

(generated by the script)

## Deadlines

Priority: 🔴 High (generated by the script)

Due dates and course time limits, with pause, reminders and at-risk views. Parent: `deadlines`.

### Ready to start

- `deadlines-3-extensions-and-pause` — **ready** — Staff extend deadlines and pause or resume a learner's course in the admin.

### Blocked

- `deadlines-4-learner-self-pause` — **blocked** by `deadlines-3-extensions-and-pause` — Learners pause their own course within the policy's limits.

![Deadlines](roadmap_diagrams/deadlines.svg)

**Notes**
- `deadlines-4-learner-self-pause` and `deadlines-5-reminders` run in parallel.
- Open: the reminder offsets (owned by `deadlines-5-reminders`).

## Tooling and operations

Developer tooling and deployment.

### Needs work on main first

- `mega-qa` — **ready** — Whole-system QA suite and staging reset. Before starting: cut it with `/sdd:roadmap mega-qa` (three ideas in one directory).
````

The script writes the `###` group headings and places each feature's diagram line after its
bullets. Every feature gets one, even
with a single spec: specs with no dependency sit in a grid under the graph.

## Child idea header

The first paragraph after a child idea's title:

```
Spec N of M in the <effort name> effort. Read the "<effort name>" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.
```

Then `## What`, `## Why`, `## What is settled`, `## Open until the spec`, `## Out of scope`,
`## Resources`. An idea is decision-complete: everything the cut settled that this child needs is
stated as fact under "What is settled", so `/sdd:spec_from_idea` reopens nothing. Inside the idea,
siblings are named by directory name, never by number.

## Parent idea blockquote

Prepended to the parent's idea when it is cut:

```
> This idea has been cut into N specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "<effort name>" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.
```
