# Idea 3 of 3: downstream QA propagation

**Run last.** There is nothing to propagate until idea 2 has produced plans, and no downstream staging
run to point them at until idea 1 has shipped an installable reset app.

---

## Why

FLS is never deployed on its own. Every real deployment is a concrete downstream project with FLS as a
git submodule, and that project needs its own whole-system QA suite.

Most of it will be identical to FLS's. A concrete project usually behaves exactly as FLS does and
differs in one or two places, a customised learner dashboard being the obvious case. Copying nine
plans to change one of them means the other eight silently rot the first time FLS improves them.

So: a command that pulls FLS's plans into a concrete implementation and customises them, alongside the
existing `/fls-dev:update_fls`. Where a plan is unchanged, the project links to it rather than copying
it.

---

## What has been settled

### Link with a stub file, not a symlink

The local file at the plan's conventional path is a short stub naming the upstream plan inside the FLS
submodule and saying to run it unchanged. The agent resolves that path at run time, so the stub cannot
go stale: it always reads whatever the submodule currently has there.

A symlink is the obvious answer and the wrong one, for a reason that has nothing to do with taste.
Reports and screenshots are written beside the plan that was run. A symlinked plan resolves into
`submodules/Freedom-LS`, so every execution would write QA artifacts into a read-only dependency that
the next submodule update discards. Symlinks also degrade silently to one-line text files on Windows
checkouts, where the reader gets a path string instead of a plan and nothing raises an error.

The stub keeps artifacts in the downstream project's own tree, which is the constraint that actually
decides this.

### The manifest records inheritance status

Every area gets a row: inherited, overridden, not applicable, or local-only, with the reason where one
is needed. The manifest is the at-a-glance view; the per-area stub or override is what an executing
agent opens. Keep both, because an index alone leaves nothing to read locally and stubs alone leave
nobody able to see the shape of the suite.

### An overridden plan does not also run the upstream one

That would either double-report the same area or fail against behaviour the project changed on
purpose. A "not applicable" area shows as a deliberate, visible declaration rather than a missing
file, so it never reads as an area somebody forgot.

This is the same decision `conformance.drop()` already implements for route probes, and the
conformance suite is the model for the whole mechanism: shared source upstream, a thin local opt-in,
and an explicit visible skip when something genuinely does not apply. Conformance also splits probes
into a contract tier that cannot be dropped and an internal tier that can, which is the existing
machinery for saying some plans are non-negotiable.

### Drift only threatens overridden plans, and the detection already exists in another form

An inherited stub cannot drift, since it resolves to current upstream content. An override can, and
FLS already solves the identical problem for templates: `upgrade_notes.md` declares which template
paths a spec touched, and `/fls-dev:update_fls` flags downstream overrides of those paths for human
review without auto-merging. The same declaration for QA plan paths gives the same signal, with no
hashing and no diffing, because FLS already knows what it changed. It wrote the spec that changed it.

### Distribution needs nothing new

Downstream-facing commands already live alongside `/fls-dev:update_fls`, and a concrete project reaches
the whole plugin through the checkout its launcher points at. Nothing in the plugin manifest filters
which commands a project can see. A command placed there becomes available the moment the submodule
pointer advances past it.

### Plans must be parameterised before any of this works

A plan that hardcodes a base URL, a login address, or a site domain cannot be inherited unchanged even
when the behaviour it describes is identical. Environment belongs in configuration; only behaviour
belongs in a plan body. Idea 2 owns that parameterisation, which is the real reason this idea runs
after it.

---

## Things the spec will have to decide

- Whether any plans are un-droppable, and how a project declares an override without editing anything
  inside the submodule. Conformance's contract-versus-internal split is the mechanism to extend.
- Where a downstream project's own QA-only plans live, for behaviour FLS does not have at all.

---

## Research

`research_downstream_qa_inheritance.md` has the submodule mechanics, the conformance suite read in
full as the precedent, the rejected alternatives with their failure modes, and confirmation of how the
new command reaches concrete projects.
