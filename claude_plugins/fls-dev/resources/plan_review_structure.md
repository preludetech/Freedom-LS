# Plan review brief: cross-app structure

Inputs from the caller: `<plan-path>`, `<spec-path>`, `<output-path>`.

Read `docs/app_structure.md`. If it is missing, write `<output-path>` with
`status: blocked · needs: docs/app_structure.md` and stop.

**Parse the approved graph.** Extract the apps (nodes in the mermaid block), the runtime edges
(`A --> B`) and the test-only edges (`A -.-> B`). Read the spec and the plan in full.

**Identify proposed cross-app edges in the plan.** Signals:
- `from <app>.<module> import …` snippets in code blocks or step descriptions.
- Steps that create files in app `A` and reference models, forms, views, services or helpers from app `B`.
- New tests in app `A` that rely on factories, fixtures, or data builders from app `B`.
- New management commands or signal handlers in `A` that orchestrate work in `B`.

For each signal, record the directed edge `(source_app, target_app)`, **runtime** or **test-only** by where the code would live (tests/, `test_*.py`, `conftest.py` → test-only; everything else → runtime). If the plan is vague about where code will live, record that ambiguity rather than guessing.

**Classify each proposed edge:**
1. **Already in the graph as a runtime edge** → no action.
2. **Already in the graph as a test-only edge, and the plan would make it runtime** → this is a *promotion*, and counts as new. Flag.
3. **Not in the graph at all** → new edge. Flag.
4. **Removes an existing edge** → not flagged.

Write `<output-path>` in a single `Write`. Its first line is `callout: Structure concern`. Then
one line per flagged edge,
`<plan step>: new <runtime|test-only> edge <A> --> <B>: clear fix: <the helper moved to an app both ends already depend on> | judgement call: accept and document, or restructure`,
then the `status:` footer. No flagged edge is `status: ok` with `no new edges`.
