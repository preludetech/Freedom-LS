---
description: Generate or refresh docs/app_structure.md — a mermaid diagram of inter-app dependencies
allowed-tools: Read, Bash
---

This command regenerates `docs/app_structure.md`, the authoritative picture of inter-app dependencies in this project. The file is both documentation for human readers and the source of truth that `/plan_structure_review` compares implementation plans against.

The diagram is generated deterministically from `ast` — it reflects what the code actually imports, not what we wish it imported. If the output surprises you, the code is what's wrong.

## Step 1: Run the generator

Invoke the helper script from the project root:

```
uv run python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_app_map.py
```

The script:

- Finds every directory containing an `apps.py`.
- Walks each app's `.py` files and collects cross-app `ImportFrom` edges via `ast`.
- Distinguishes runtime imports from test-only imports (paths under `tests/`, `test_*.py`, or `conftest.py`).
- Writes the result to `docs/app_structure.md` (mermaid + dependency table + legend).
- If the file already existed, prints a short diff of added/removed edges to stdout.

If the script fails (e.g. no `apps.py` files found), tell the user what happened and stop.

## Step 2: Surface the diff to the user

Read the script's stdout and report:

- If this was the initial generation, say so and mention the output path.
- If edges changed, list the added and removed edges exactly as printed.
- If nothing changed, say so in one line.

## Step 3: Nudge the user about intent

If any edges were **added** in this run, remind the user:

> New cross-app edges appeared in the diagram. If these were intentional, commit the updated `docs/app_structure.md`. If not, the right fix is to restructure the code — not to commit the new edge.

If any edges were **removed**, mention that a dependency was broken (usually a good sign, but worth noticing).

## Output

Print a short summary:

- The path to `docs/app_structure.md`.
- The diff summary from Step 2.
- The reminder from Step 3, if applicable.

Do not edit the generated file by hand. Do not call `update_todo`.
