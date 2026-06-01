# The fan-out resilience recipe (Claude Code 2.1.x)

Distilled from `research_resilience_patterns.md`. This is the canonical explanation of the recipe
that SDD fan-out commands embed in compact form. Every claim traces to that research.

## Why a recipe is needed
Claude Code's subagent model is **fire-and-forget and one-shot**: task in → single result out, in an
isolated context, with **no mid-run messaging**, **no user prompting from a subagent**, and **no
nesting**. Robustness must therefore be **designed into the workflow**, not delegated to a runtime
feature.

## The recipe (depth-0 orchestrator over units U1…Un)

1. **Declare inputs up front (input contract).** Each phase lists the user input it needs. The
   orchestrator gathers it via `AskUserQuestion` (legal only at depth 0) **before** spawning, and
   bakes the answers into each worker prompt. *(Patterns B1/B5.)*
2. **One output path per unit.** Assign a deterministic path. Durable artifacts keep their real
   names (e.g. `research_<topic>.md`); intermediate outputs go in a scratch dir `.sdd-work/` inside
   the spec directory, named `<phase>_<unit-id>.md`. *(Pattern A2.)*
3. **Resume scan (before spawning).** For each unit, if its output file exists **and** ends with
   `status: ok`, skip it. Spawn only missing/not-ok units. *(Pattern A3 — `todo.md` is the manifest.)*
4. **One subagent per unit**, in parallel, via the `Agent` tool (`subagent_type: "fls:sdd-worker"`,
   or `"fls:sdd-mechanic"` for mechanical units). Pass the exact output path and baked-in inputs.
   **Never one worker looping over the whole batch** — a sibling's failure must not lose others'
   work. *(Pattern A1.)*
5. **Collect structured returns** and act per `status`:
   - `ok` → done.
   - `failed` → retry the **same** unit, ≤2 attempts, including the prior error in the retry brief.
     *(Pattern A5.)*
   - `blocked` → the orchestrator gathers the listed `needs` via `AskUserQuestion`, then **re-spawns
     a fresh worker** with the original brief + answers (pointing at any partial file). *(B3/B4.)*
6. **Synthesis is a separate step.** A later step reads the output **files** (pass paths, never dump
   contents into the orchestrator prompt) and produces the artifact — so it can be retried without
   re-running workers. *(Pattern A6 — two-phase fan-in.)*
7. **Clean up on success.** When the phase artifact is finalised, delete `.sdd-work/`. Durable
   artifacts are **not** deleted. An abandoned `.sdd-work/` from an interrupted run is **intentional**
   — it is what makes resume (step 3) cheap.

## Atomic writes
Workers write `<path>.tmp` then rename to `<path>`, so a crash mid-write never leaves a half-file
that looks complete. *(Pattern A2.)*

Source: https://www.anthropic.com/engineering/multi-agent-research-system ·
https://code.claude.com/docs/en/sub-agents · https://code.claude.com/docs/en/headless
