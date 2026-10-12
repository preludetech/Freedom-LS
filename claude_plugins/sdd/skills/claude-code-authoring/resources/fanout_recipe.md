# The fan-out resilience recipe (Claude Code 2.1.x)

This is the canonical explanation of the recipe
that SDD fan-out commands embed in compact form.

## Why a recipe is needed
Claude Code's subagent model is **fire-and-forget and one-shot**: task in → single result out, in an
isolated context, with **no mid-run messaging**, **no user prompting from a subagent**, and **no
nesting**. Robustness must therefore be **designed into the workflow**, not delegated to a runtime
feature. A command can also run in hook mode: read and followed inline by another command at
depth 0, told so by `mode: hook`.

## The recipe (depth-0 orchestrator over units U1…Un)

1. **Start the work; don't ask permission for it.** Never ask the user whether to research, scan or
   fan out: spawn the workers. Bake into each prompt everything the worker needs from what the user
   has already said and what is on disk. Questions only the user can answer are asked via
   `AskUserQuestion` (legal only at depth 0) **while the workers run**, not as a gate before them:
   as early as possible, batched up to four per call, so the user answers while research runs.
   A question that depends on a unit's findings waits for that unit; nothing else waits on a
   question. As findings land, strike the questions they answer and ask the new ones they raise.
   *(Patterns B1/B5.)*

   **What earns a question.** All three hold: the answer changes what gets built or written; no
   source file, the code, a finished unit or a running unit can answer it; and there is no default
   the user would obviously accept (if there is, take it and record it as an assumption where the
   user will see it). Never ask whether to do the work, to confirm what the source already says,
   or anything with one sensible answer. Quote the line or finding that leaves the question open
   and offer concrete options, recommended one first.

   **When the question is asked.** A command that can ask does so in one batch at the start,
   while its workers run, up to four per `AskUserQuestion`. Each question carries a recommended
   answer and one clause on why it matters.

   **When a question comes late.** A question that surfaces after that batch takes the
   recommended default and is recorded in the artifact so one grep finds every unconfirmed
   decision: in a spec under `## Open questions` as
   `- Q: <question>? → A: <default taken> (assumed default: <why safe>. Overrule by editing <section>.)`;
   in a plan as `> **Assumed default:** <what>. Why: <clause>. To change: <section>.`
   Review findings that are judgement calls reach the user in one batch at the end of the
   command, recommended option first, each naming the artifact line it concerns. An unanswered
   one is recorded as an assumed default. A `blocked` worker is answered from the idea, the code
   or another worker's file before anything is asked.
2. **One output path per unit.** Assign a deterministic path. Durable artifacts keep their real
   names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` at the
   project root, named `<phase>_<unit-id>.md`. *(Pattern A2.)*
3. **Resume scan (before spawning).** For each unit, if its output file exists **and** ends with
   `status: ok`, skip it. Spawn only missing/not-ok units. *(Pattern A3 — `todo.md` is the manifest.)*
4. **One subagent per unit**, in parallel, via the `Agent` tool (`subagent_type: "sdd:sdd-worker"`,
   or `"sdd:sdd-mechanic"` for mechanical units). Pass the exact output path and baked-in inputs.
   **Never one worker looping over the whole batch** — a sibling's failure must not lose others'
   work. *(Pattern A1.)*
5. **Collect structured returns** and act per `status`:
   - `ok` → done.
   - `failed` → retry the **same** unit, ≤2 attempts, including the prior error in the retry brief.
     *(Pattern A5.)*
   - `blocked` → the orchestrator supplies the listed `needs` from the source, the code or another
     unit's output where it can, and where it can't, asks in the command's question batch when the command can ask; a brief run as
     a hook of another command is instead recorded as skipped with its need, and the run continues. Then it
     **re-spawns a fresh worker** with the original brief + answers (pointing at any partial file).
     *(B3/B4.)*
6. **Synthesis is a separate step.** A later step reads the output **files** (pass paths, never dump
   contents into the orchestrator prompt) and produces the artifact — so it can be retried without
   re-running workers. *(Pattern A6 — two-phase fan-in.)*
7. **Clean up on success.** When the phase artifact is finalised, delete the command's own scratch
   files by name, never the `.sdd-work/` directory, which other commands share. Durable
   artifacts are **not** deleted. An abandoned `.sdd-work/` from an interrupted run is **intentional**
   — it is what makes resume (step 3) cheap.

## Atomic writes & the completeness contract
A worker emits its output in a **single `Write`** to the final path: the `Write` tool puts the whole
file down in one operation, so a crash leaves either the complete file or nothing — there is no
half-written state to guard against, and a research/review worker therefore needs **no `Bash`/rename
tool**. Completeness is signalled **only** by the `status:` footer; the resume scan (step 3) re-runs
any file that lacks it. (A shell-style temp-then-rename would require `mv`, which these workers
deliberately don't have.) *(Pattern A2.)*

Source: https://www.anthropic.com/engineering/multi-agent-research-system ·
https://code.claude.com/docs/en/sub-agents · https://code.claude.com/docs/en/headless
