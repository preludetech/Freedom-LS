# Splitting big specs into multiple coordinated specs

## Problem

Some specs end up covering enough ground that they would land best as multiple PRs. The current SDD pipeline treats every spec as a single PR — there is no mechanism to break a spec into independently-shippable child specs, and no standard way to record the dependencies between them.

## Goal

Add a mechanism that:

1. **Decides whether a spec should be split — by outcome.** The criterion is "does this work deliver more than one distinct user-visible outcome?" — not LOC, not app count, not phase count. Mechanical PR-shape concerns (diff size, layered vs vertical, etc.) are explicitly out of scope.
2. **Performs the split when triggered.** Each child becomes its own SDD-tracked entity at `spec_dd/1. next/<child-name>/` with its own idea/spec/plan/PR lifecycle. A manifest file at `spec_dd/manifests/<parent-name>.md` records what was split and how the children join together. The decomposed parent itself does not go through SDD — no worktree, no PR.
3. **Records dependencies between children** in `spec_dd/manifests/<parent-name>.md`, so humans (and tooling) can see which children can ship in parallel and which must be sequenced.

## Trigger commands

Two new slash commands. Both do the same kind of work — propose a split, get user confirmation, perform the split — but they run at different stages, and one is automatic.

### `/decompose_spec`

Run manually at idea or spec time. Reads the current artifact, decides whether there are multiple distinct outcomes, and if so proposes a split — names for each child, a one-line description of what each one delivers, and the dependencies between them. The user is asked to confirm, adjust, or reject. On approval the command creates child directories under `spec_dd/1. next/`, writes the manifest at `spec_dd/manifests/<parent-name>.md`, and adds the `manifest:` frontmatter pointer to each child. The user is not asked to manually create directories or files afterwards.

### `/decompose_plan`

Same job, applied at plan time. Invoked **automatically** — most likely as the final step of `/plan_from_spec`, so the user does not have to remember to run it. Catches the case where the implementation plan reveals multiple distinct outcomes that the spec didn't separate cleanly.

When the heuristic fires, the user is still asked for feedback before anything is committed — automatic invocation just means the check happens every time, not that the split happens silently. When the heuristic does not fire, the command exits quickly and quietly with no prompt.

The split criterion is the same as `/decompose_spec`: outcomes, not LOC or phase count. The spec and plan in the parent dir both become reference data after the split; each child inherits the relevant slice when its own SDD lifecycle starts.

## Disk shape

- **Manifests** live in their own top-level directory: `spec_dd/manifests/<parent-name>.md`. Manifests are reference data describing how a group of specs joins together — they are deliberately not gated by the `1. next/` → `2. in progress/` → `3. done/` flow that specs themselves move through.
- **Children** are top-level entries under `spec_dd/1. next/<child-name>/`. Each goes through SDD independently and may move into `2. in progress/` and `3. done/` on its own schedule. Each carries frontmatter pointing back at its manifest (see below).
- **The original parent dir** (the one where the pre-split `idea.md` / `spec.md` lived) does not go through SDD after decomposition. What exactly happens to it — leave in place, archive, fold into the manifests dir, delete — is an open question for the spec stage.
- The manifest references children by **name**, not path, so children can be located by searching across status folders (matches how `/sdd:start` already resolves spec dirs).

## Manifest format (initial sketch — to be firmed up at spec stage)

The manifest at `spec_dd/manifests/<parent-name>.md` carries a YAML fenced block as the machine-readable source of truth, plus a prose `## Children` section for humans, and optionally a generated Mermaid diagram as a derived view. Cribbed from CCPM (`depends_on` per child) and from how Bazel/Cargo/CI handle DAGs (one declared edge list, computed reverse, generated visualisation).

Each child carries `manifest: <parent-name>` in markdown frontmatter, pointing back at the manifest that describes how it joins with its siblings. Child-side dependency declarations are deliberately avoided — keeping edges in one place prevents the bidirectional drift that bites ADRs. The frontmatter pointer is enough for an orphaned child dir to find its way home.

## Out of scope

- **Mechanical PR-shape decomposition.** No LOC heuristics, no app-count heuristics, no phase-count heuristics. Splits are by outcome only.
- **Cross-status dependency enforcement.** Children move through statuses independently; coordinating dependents that are in different statuses is a human concern, not something the manifest enforces.
- **Recursive splitting** (a child being decomposed again). Worth deciding at spec stage but assume "no" by default.

## Open questions for the spec stage

- What exactly does the command seed inside each child dir — a derived `idea.md`, a carved-out `spec.md`, or both depending on what stage the parent was at?
- Does the parent's `todo.md` (if one exists) get rewritten to track decomposition, replaced, or deleted?
- What happens to the original parent dir after decomposition? Options: leave in place, archive into `spec_dd/3. done/`, fold its content into the manifests dir, or delete. The pre-split `idea.md` / `spec.md` is still useful context but is no longer part of the SDD pipeline.
- Do we want a separate `/spec_graph` command to render the manifest as Mermaid on demand, or is the diagram regenerated as part of `/decompose_spec`?
- Should `/decompose_spec` also be auto-invoked (e.g. at the end of `/spec_from_idea`) for symmetry with `/decompose_plan`, or stay manual? The case for keeping it manual: idea/spec stage is more fluid and the user is more likely to want to think about decomposition explicitly. The case for auto: consistency, and it removes a thing the user has to remember.
- How does `/sdd:next` behave when invoked against a decomposed parent (probably: print "this is a manifest, see children")?
- Should anything stop a child from being decomposed again recursively, or do we just trust the user not to do it?

## Notes for the spec writer

The four research notes in this directory should be read alongside this idea — particularly:

- `research_reference_implementations.md` for prior art (BMAD's `/bmad-shard-doc` and CCPM's frontmatter are the closest references).
- `research_dependency_representation.md` for the manifest format trade-offs.
- `research_lifecycle_timing.md` for the reasoning behind splitting by outcome (and only by outcome) rather than at multiple stages with different questions.
- `research_pr_sizing.md` is the strongest argument *against* the path we chose — it's worth reading so the spec writer knows what we explicitly decided not to do, and why.
