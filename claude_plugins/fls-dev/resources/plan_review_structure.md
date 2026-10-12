# Plan review brief: cross-app structure

Inputs from the caller: `<plan-path>`, `<spec-path>`, `<output-path>`.

Read `docs/app_structure.md`. If it is missing, write `<output-path>` with
`status: blocked · needs: docs/app_structure.md` and stop.

**Parse the approved graph.** Read `docs/app_structure.md` and extract:
- The set of apps (nodes in the mermaid block).
- The set of runtime edges (lines of the form `A --> B`).
- The set of test-only edges (lines of the form `A -.-> B`).

Also read the spec and the plan in full.

**Identify proposed cross-app edges in the plan.** Signals to look for:
- Explicit `from <app>.<module> import …` snippets inside code blocks or step descriptions.
- Step descriptions that create files in app `A` and reference models, forms, views, services, or helpers from app `B`.
- New tests in app `A` that rely on factories, fixtures, or data builders from app `B`.
- New management commands or signal handlers in `A` that orchestrate work in `B`.

For each such signal, record the directed edge `(source_app, target_app)`. Classify each edge as **runtime** or **test-only** based on where the code would live (tests/, `test_*.py`, `conftest.py` → test-only; everything else → runtime). If the plan is vague about where code will live, record that ambiguity rather than guessing.

**Classify each proposed edge:**
1. **Already in the graph as a runtime edge** → no action.
2. **Already in the graph as a test-only edge, and the plan would make it runtime** → this is a *promotion*, and counts as new. Flag.
3. **Not in the graph at all** → new edge. Flag.
4. **Removes an existing edge** → not flagged. Fewer edges is generally good.

Write `<output-path>` in a single `Write`. Its first line is `callout: Structure concern`. Then
one line per flagged edge,
`<plan step>: new <runtime|test-only> edge <A> --> <B>: clear fix: <the helper moved to an app both ends already depend on> | judgement call: accept and document, or restructure`,
then the `status:` footer. No flagged edge is `status: ok` with `no new edges`.
