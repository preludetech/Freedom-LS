# Docs and polish

Spec 12 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Close the effort. Document the panel framework for the people who will build on it, rewrite the educator product doc as one piece, walk every screen on desktop and mobile with a keyboard and a screen reader, consolidate the upgrade notes for downstream projects, and delete whatever the earlier specs left behind.

## Why

Each of the eleven specs documents its own change, but nobody has read the result end to end. The source idea's first goal is a framework that is "complete, self-contained and powerful enough for everything we need". That is only true once a developer who was not here can read one document, build a section in a downstream project, and get the same look and behaviour. The `fls-dev` skills that describe Alpine components already list one that does not exist, which is the kind of drift this spec removes.

## What is settled

**Developer doc.** `docs/product/panel-framework.md` (or `docs/how tos/`, whichever the existing docs convention favours): what a section is, the three view kinds, panels and tabs and their binding, actions, tables with filters and selection, the modal and the quick view, the permission hooks, URL state, the cotton components, how a downstream project registers a section and overrides a template. Written for a Django developer who has not seen the code, with one worked example.

**An `fls-dev` skill.** `claude_plugins/fls-dev/skills/panel-framework/` so an agent building a section reads the contract instead of guessing from the educator interface. It follows the shape of the existing skills. The `alpine-js` skill's component inventory is corrected to what is registered.

**Product doc.** `docs/product/educator-interface.md` rewritten as one document, with fresh screenshots from the QA folders, in the order an educator meets the interface: dashboard, learners, cohorts, courses, educators, history, reports. `docs/product/roadmap.md` loses the entries this effort closed.

**Polish pass.** Every screen at 390 wide and 1440 wide, in the default theme and in dark mode, matched against the mockups for layout and density. Keyboard through every action. A screen reader through the quick view, the modal and the tables. Fix what is found; a list of what is deliberately left goes in the spec.

**Consistency pass.** Same wording for the same action everywhere (deactivate, reactivate, remove, unregister), the same confirmation shape, the same empty states, the same badge vocabulary. The `domain-glossary` skill is the reference.

**Upgrade notes.** One consolidated `upgrade_notes.md` for the effort, in addition to each spec's own, listing the URL changes, every template a downstream may have overridden, new settings, new event types, new migrations, and `requires_tailwind_rebuild`. Written to the schema in `claude_plugins/fls-dev/commands/update_upgrade_notes.md`.

**Deletions.** Anything from the old interface that a spec forgot: unused cell templates, the two `qa_helpers` commands for the matrix if spec 1 left them, agent memory notes that describe deleted commands, stale doc sections.

**Tests.** The Playwright suites for the educator interface run green, and a smoke test per section exists.

## Open until the spec

- Where the developer doc lives under `docs/`.
- Whether the mockup fidelity check is done by eye or with a screenshot diff. By eye is fine; the mockups are not pixel references.

## Out of scope

- New features. If the pass finds a missing capability, it goes in `spec_dd/1. next/` as its own idea.

## Resources

- Every idea in `educator-interface-1-*` to `educator-interface-11-*`, and their specs' QA reports.
- `claude_plugins/fls-dev/commands/update_product_docs.md` and `update_upgrade_notes.md`.
- Skills: `fls-dev:update_product_docs`, `fls-dev:update_upgrade_notes`, `sdd:claude-code-authoring` for writing the skill, `fls-dev:do_qa`, `unslop`.
