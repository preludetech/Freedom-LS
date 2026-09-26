# The spec roadmap

`spec_dd/1. next/roadmap.md` is the index of every spec that is waiting or in flight: one row per
directory under `spec_dd/1. next/` and `spec_dd/2. in progress/`, with what it delivers, what it
depends on and where it stands. A row leaves when its spec is done. This file is the single
definition of the roadmap's shape. `/sdd:roadmap` writes it, `protected/update_roadmap.md` edits
single rows and keeps the two start lists current, and `/sdd:start` reads a row's dependencies and
precursor.

It is the *spec* roadmap. `docs/product/roadmap.md` is the product roadmap and is a different file.

## Rules

1. **One row per directory.** Every top-level directory in `1. next/` and `2. in progress/` has
   exactly one row, except an effort parent (below), which has a `Parent:` line instead.
   `spec_dd/0. noop/` and `spec_dd/3. done/` are not indexed.
2. **Status comes from location.** `next` for `1. next/`, `in progress` for `2. in progress/`.
   Nothing else is a status.
3. **Dependencies live here and nowhere else.** The Depends on cell is the only edge list. A child
   idea carries a pointer line to its effort's section and says nothing about order. A dependency
   is met when the named directory is in `3. done/` (its name there is `<timestamp>_<name>`).
4. **Derived text is regenerated, never edited by hand.** "Ready to start", "Needs work on main
   first", every Status cell and every graph are computed from the tables by `/sdd:roadmap`.
   Between syncs, `protected/update_roadmap.md` keeps the two lists true as specs start and
   finish, so neither list ever names a spec that has already started. Status cells and graphs
   change only through sync or that helper's row edits. Hand edits go in the Scope, Depends on
   and Notes cells and in an effort's `####` subsections.
5. **A cut is an effort.** A big idea cut by `/sdd:roadmap <dir>` becomes an effort: a `###`
   section holding its children's table, its graph and the material every child needs
   (ordering and parallelism, decisions already taken, assumptions, unknowns resolved inside a
   spec, out of scope for all, shared references). The parent directory keeps the original idea,
   the mockups and any research more than one child uses; it is not itself a spec.
6. **When the last child finishes**, the effort's section is archived to
   `<parent>/spec-order.md` and the parent directory moves to `3. done/`, so the pointers in
   the done children still lead to the record.
7. **A precursor keeps a spec off "Ready to start".** A precursor is work that has to happen on
   main before `/sdd:start` can branch a worktree off it. A row has one when its Notes cell
   starts with `Before starting:`. Sync writes that note for a directory that needs a cut (below).
   A person writes it by hand for any other job, such as a spec that has to be merged first or a
   draft that has to be split. A `next` row whose dependencies are all done goes under "Needs
   work on main first" if it has a precursor, and under "Ready to start" if it does not.
   Improving an idea (`/sdd:improve_idea`) happens on main without starting the spec, so it
   changes neither list.
8. **The two lists partition the startable rows.** "Ready to start" lists every `next` row with
   all dependencies done and no precursor. "Needs work on main first" lists every `next` row with
   all dependencies done and a precursor. A row is never in both, and an `in progress` row is in
   neither.

## Classifying a directory

`/sdd:roadmap` sorts each directory into one of three kinds, and adds a *needs a cut* note where
one applies.

| Kind | Test |
|---|---|
| Effort parent | Its idea begins with the parent blockquote below, or a legacy `spec-order.md` sits in it. |
| Effort child | Its name is `<parent>-N-<slug>` for a known parent, or its idea's first paragraph after the title begins `Spec N of M in the … effort`. |
| Standalone | Anything else. |

Needs a cut: the directory holds more than one `idea*.md`; or it nests a
subdirectory that contains an `idea.md` or `1. spec.md`; or it is empty. It is noted in the Notes
cell as a precursor: `` Before starting: cut it with `/sdd:roadmap <dir>` (<reason>). ``, followed by
any other notes.

## Row grammar

The grammar a mechanic edits by, with no judgement needed:

- One row per line. The Directory cell is the bare directory name in backticks, no path.
- Depends on is `none` or a comma-separated list of backticked directory names, each of which
  must be a Directory cell somewhere in the file or a name in `3. done/`.
- Status is exactly `next` or `in progress`.
- An effort is a `###` heading followed by a line starting `Parent:` with the parent directory
  in backticks. Its `####` subsections are hand-authored and preserved by every sync.
- The Standalone specs table has a Notes cell; effort tables do not, so only a standalone row can
  carry a precursor.
- A precursor is a Notes cell that starts with `Before starting:`. The precursor text runs to the
  end of that sentence.
- "Ready to start" and "Needs work on main first" hold one bullet per line, sorted
  alphabetically by directory name. A Ready bullet is `` - `<dir>` ``. A Needs work bullet is
  `` - `<dir>`: <precursor text> ``, with the `Before starting:` prefix dropped. An empty list
  holds the single line `None.`

## Skeleton

````markdown
# Spec roadmap

Every directory under `spec_dd/1. next/` and `spec_dd/2. in progress/` has one row here. A row
is removed when its spec finishes (`/sdd:finish_worktree`). A dependency names a directory and
is met when that directory is in `spec_dd/3. done/`. `/sdd:roadmap` reconciles this file with
the directories; `/sdd:roadmap <dir>` cuts a big idea into ordered specs and adds them here.
The rules and row grammar are in `claude_plugins/sdd/resources/roadmap_format.md`. This is the
spec roadmap. The product roadmap is `docs/product/roadmap.md`.

## Ready to start

Status `next`, every dependency done, and nothing to do on main first. Regenerated by
`/sdd:roadmap`; `/sdd:start` and `/sdd:finish_worktree` keep it current between syncs.

- `file-scanning`

## Needs work on main first

Status `next` and every dependency done, but something has to happen on main before `/sdd:start`.
Each bullet says what.

- `mega-qa`: cut it with `/sdd:roadmap mega-qa` (three `idea_*.md` in one directory).

## Efforts

### Educator interface rebuild

Parent: `educator-interface-full-polish` (source idea, mockups, two shared research files).
Cut 2026-09-24 into twelve specs. Read this section before starting any of them.

| # | Directory | Scope | Depends on | Status |
|---|---|---|---|---|
| 1 | `educator-interface-1-panel-framework-core` | Panel, tab and action API rework … | none | in progress |
| 2 | `educator-interface-2-panel-framework-tables` | Table layer moves into the framework … | `educator-interface-1-panel-framework-core` | next |

```
1 core ──┬── 2 tables
         └── …
```

#### Ordering and parallelism
#### Decisions already taken
#### Assumptions the ideas make
#### Unknowns resolved inside a spec
#### Out of scope for all
#### Shared references
#### Not yet cut

## Standalone specs

| Directory | Scope | Depends on | Status | Notes |
|---|---|---|---|---|
| `file-scanning` | Scan applicant uploads for malware … | none | next | |
| `mega-qa` | Staging reset, whole-system QA suite … | none | next | Before starting: cut it with `/sdd:roadmap mega-qa` (three `idea_*.md` in one directory). |

```
retry-sent-emails ── user-communication
```
````

## Child idea header

The first paragraph after a child idea's title:

```
Spec N of M in the <effort name> effort. Read the "<effort name>" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.
```

Then `## What`, `## Why`, `## What is settled`, `## Open until the spec`, `## Out of scope`,
`## Resources`. An idea is decision-complete: everything the cut settled that this child needs is
stated as fact under "What is settled", so `/sdd:spec_from_idea` reopens nothing.

## Parent idea blockquote

Prepended to the parent's idea when it is cut:

```
> This idea has been cut into N specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "<effort name>" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.
```
