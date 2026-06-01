# Resilience Patterns for Multi-Agent Orchestration in Claude Code

Research to inform the redesign of the SDD (spec-driven development) slash-command workflow.
Focused on two pain points: (A) batch fragility, and (B) mid-run input to sub-agents.

Sources are official Anthropic / Claude docs plus Anthropic engineering posts; see References.
Retrieved 2026-05-30. Docs now live under `code.claude.com` (Claude Code) and
`platform.claude.com` (Agent SDK); the older `docs.claude.com` / `docs.anthropic.com` URLs 301/307
to these.

## Summary

Claude Code's sub-agent model is **fire-and-forget and one-shot**. The orchestrator (main agent)
invokes a sub-agent via the **`Agent` tool (formerly, and still aliased, `Task`)**; the sub-agent
runs autonomously in an **isolated context window** and **returns a single result** to the
orchestrator when done. Key constraints, all confirmed by official docs and Anthropic engineering:

- A sub-agent *"works independently and returns results"* — it is a **one-shot** call: task in,
  result out. There is **no supported mechanism to send a new message into a sub-agent while it is
  running.**
- **Sub-agents cannot prompt the user** — they *"cannot go back and ask clarifying questions"*
  (they *"have temporary context windows"*). Only the orchestrator (or, in the SDK, the host
  application) talks to the user.
- **Sub-agents cannot spawn their own sub-agents** — the `Agent`/`Task` tool is not exposed inside a
  sub-agent. Orchestration is effectively **single level / flat**.
- Multiple sub-agents **run in parallel** (the lead typically spawns *"3-5 subagents in parallel"*),
  each in its own context.

Because of these constraints, robustness must be **designed into the workflow**, not delegated to a
runtime feature. The two highest-leverage levers:

1. **One sub-agent per unit of work, each writing its own output file** — a sibling's failure never
   destroys completed work, and "resume" becomes "skip units whose output file already exists."
   (Pain Point A)
2. **An explicit input contract per phase** — every phase declares up front what user input it
   needs, the orchestrator gathers it *before* spawning, and sub-agents are **non-interactive and
   fail-fast**, returning a structured `blocked: needs X` result instead of hanging. (Pain Point B)

Session **resume / continue / fork** does exist (SDK `resume`, `continue: true`, `forkSession` /
`fork_session`; CLI `--resume <id>` / `--continue`), but it applies to a *session*, **not** to
reaching into a live `Agent`/`Task` sub-agent. It is still useful as a checkpoint-and-resume
mechanism for the top-level workflow, or for SDK-hosted long-lived workers (see B6).

---

## Pain Point A — Batch fragility

**Problem:** A batch (e.g. several parallel research agents, or several review dimensions) runs, and
if one task fails the whole batch effectively restarts.

**Root cause in Claude Code terms:** if a *single* sub-agent is asked to do N units of work, or if
results are only consolidated after *all* siblings return, then any one failure loses the partial
work of the rest. Anthropic's own research team hit this: *"we need to durably execute code and
handle errors along the way... we can't just restart from the beginning: restarts are expensive,"*
so they built checkpointing to *"resume from where the agent was when the errors occurred"* rather
than restart (Anthropic, *Multi-agent research system*).

### Pattern A1 — One agent per unit, not one agent per batch (fan-out)
Spawn an **independent sub-agent for each unit of work** (each research question, each review
dimension), not a single sub-agent that loops over all of them. Failures are then isolated to one
unit. This is the supported pattern — sub-agents *"run multiple analyses in parallel"* and the lead
activates *"3-5 subagents in parallel rather than serially."* Classic name: **fan-out / fan-in**.

### Pattern A2 — Each unit writes its own output file (durable partial progress)
Give every sub-agent a **deterministic, assigned output path** (e.g. `reviews/<dimension>.md`,
`research/<slug>.json`) and instruct it to write its result there as the **last step** before
returning. Anthropic explicitly recommends this: subagents can *"store their work in external
systems, then pass lightweight references back to the coordinator."* Consequences:
- A completed unit's output **survives a sibling's failure** — it is already on disk.
- The orchestrator never has to hold all results in its own context to "save" them (also a token win).
- Fan-in becomes "read the files," cheaper on context than re-summarising.
Write **atomically** (write `*.tmp`, then rename) so a crashed mid-write sub-agent never leaves a
half-file that looks complete.

### Pattern A3 — Resume = skip units whose output already exists (idempotency)
Before spawning the batch, the orchestrator scans the output directory and **only spawns sub-agents
for units whose output file is missing or marked not-ok**. This makes the batch **idempotent and
resumable**: re-running after a partial failure re-does only the missing units. This is the
file-system version of Anthropic's *"resume from where the agent left off"*, achievable today with
nothing but file-existence checks. Encode a status marker in each file (`status: ok|failed|blocked`)
so "exists but failed" is distinguishable from "succeeded"; re-spawn anything not `ok`.

### Pattern A4 — Structured pass/fail result per unit (supervisor can decide)
Require each sub-agent to **end with a small fixed-schema result.** In headless/SDK runs this is
first-class: `claude -p ... --output-format json` returns a `result`, `session_id`, and `is_error`,
and `--output-format json --json-schema '<JSON Schema>'` returns schema-conforming data in a
`structured_output` field. For in-conversation `Task` sub-agents (no enforced schema), instruct them
to end with a fixed JSON block, e.g.:
```json
{ "unit": "security-review", "status": "ok|failed|blocked",
  "output_path": "reviews/security.md", "reason": "..." }
```
The orchestrator (a **supervisor**) reads these, knows exactly which units to retry, and never has
to infer success from prose.

### Pattern A5 — Retry only the failed unit (bounded)
On a `failed` result, the orchestrator **re-spawns just that one unit** (a fresh sub-agent — they
start clean each invocation), up to a small fixed retry budget (e.g. 2). Because units are
independent (A1), durable (A2) and idempotent (A3), a retry cannot corrupt units that already
succeeded. This is the **supervisor/retry** pattern, scoped to the unit, not the batch. Anthropic
notes agents *"adapt gracefully when tools fail"* when told about the failure — so include the prior
error in the retry brief. (Note: headless mode also auto-retries *transient API* errors and emits a
`system/api_retry` event; that is network-level retry, separate from the unit-level retry here.)

### Pattern A6 — Two-phase fan-in (collect, then synthesize)
Keep **work** and **synthesis** as separate phases. Phase 1: fan-out workers each write a file.
Phase 2: a *separate* synthesis step reads the files and produces the combined artifact. If synthesis
fails it can be retried freely without re-running any workers, since their outputs are durable. (The
saga-style "each step is independently re-runnable" idea, grounded in files.)

### Pattern A7 — Checkpoint the orchestrator itself
For long multi-phase commands, persist a tiny **manifest** (e.g. `progress.json` listing each
phase/unit and its status) and/or rely on session resume (`--resume <session-id>` / SDK `resume`) so
the *top-level* run can be continued, not restarted. The manifest is the cheap file-based checkpoint;
session resume is the runtime one. The SDD workflow already uses a `todo.md` checklist — that **is**
this kind of manifest and should drive the skip-if-done logic (A3).

---

## Pain Point B — Mid-run input to sub-agents

**Problem:** A sub-agent needs information only the user can supply. The main agent can ask the user
but **cannot inject the answer into an already-running sub-agent.**

**Root cause in Claude Code terms — this is a confirmed, documented limitation.** Sub-agents
*"have temporary context windows and cannot go back and ask clarifying questions."* They operate
autonomously once invoked; there is **no mechanism for the main agent to message a running
sub-agent**, and sub-agents **cannot prompt the user**. Anthropic's research team makes the same
point: subagents *"can't ask clarifying questions mid-task,"* so *"each subagent needs an objective,
an output format, guidance on the tools and sources to use, and clear task boundaries,"* and
*"failures usually trace back to an underspecified task at the start."*
**You cannot fix this at runtime; you fix it in the protocol.**

### Pattern B1 — The "input contract" per phase (gather up front)
Each phase/command declares, **as data**, the user input it will need *before any sub-agent is
spawned* — a small list of required answers (target Site, scope decisions, ambiguous spec points).
The orchestrator: (1) reads the input contract, (2) **collects every declared input from the user in
one batch** (the orchestrator *can* talk to the user), (3) only then spawns sub-agents, passing the
gathered answers inside the task prompt. This converts "interactive mid-run" into "complete brief up
front" — exactly what the multi-agent guidance prescribes.

### Pattern B2 — Sub-agents are strictly non-interactive
Write every sub-agent's instructions to **never wait for, or ask, the user.** They work only from the
brief. This matches runtime reality (they can't reach the user anyway) and prevents the silent-hang
failure mode where a sub-agent stalls waiting for input that can never arrive. (Even the SDK's
user-input / tool-approval callbacks are owned by the *host application*, via a permission callback —
they are not a channel a sub-agent can use to ask the human a free-form question.)

### Pattern B3 — Fail-fast with a structured "blocked: needs X" result
If a sub-agent discovers it is **missing required information**, it must **stop immediately and return
a structured result** rather than guessing or hanging, e.g.:
```json
{ "status": "blocked", "needs": ["which Site should QA use?",
  "is feature X in scope for this spec?"], "partial_output_path": "research/topic.md" }
```
`blocked` (vs `failed`) tells the orchestrator the problem is **missing input**, not a bug. Combined
with A2 (write partial output first), the work done so far is not wasted.

### Pattern B4 — Orchestrator collects X and re-spawns (the resume loop)
On a `blocked` result, the orchestrator: (1) asks the user the questions in `needs`, (2) **re-spawns
a fresh sub-agent** for that unit with the original brief **plus** the new answers (and a pointer to
`partial_output_path` so it continues rather than restarts). Because `Task` sub-agents start clean
each invocation, "resuming a sub-agent" is really "spawn a new one with more context" — fine when
units are idempotent (A3) and partial output is durable (A2). This is the only robust way to get
late-arriving user input into the work today.

### Pattern B5 — Pre-flight question harvest
Add an explicit early step that **scans the whole upcoming batch (the spec/idea) for likely-needed
inputs and asks them all at once**, before fan-out. This minimises round-trips: instead of N
sub-agents each coming back `blocked` one at a time, the orchestrator front-loads the ambiguity.
(Complements B1: B1 is the declared/static contract, B5 is the dynamic scan of the actual content.)

### Pattern B6 — When you genuinely need a long-lived, interruptible worker: use the SDK, not `Task`
If a use case truly requires feeding input to an in-flight agent, run that worker as its **own
session via the Agent SDK / headless CLI**, not as an `Agent`/`Task` sub-agent. Sessions support
**resume** and **continue** — *"Continue and resume both pick up an existing session and add to
it"*; `continue: true` / `--continue` resumes the most recent on-disk session; `resume` /
`--resume <id>` resumes a specific one; *"When you resume a session with a new prompt, that prompt
becomes a new message added to the session history."* `forkSession` / `fork_session` branches a copy
under a new id. Headless JSON output exposes the `session_id` (present on every result, success or
error). So the orchestrator can run the worker with `--output-format json`, capture its `session_id`,
ask the user, then `--resume <id>` with the answer as a new turn. This is heavier, is a design choice
for the workflow *runner*, and loses the in-conversation progress visibility the `Task` tool gives;
nested `claude -p` calls from inside a sub-agent also have *"no progress tracking, no ability to
interrupt, and no structured output handling"* from the parent's view.

---

## What Claude Code supports today vs. what must be designed around

| Capability | Supported today? | Notes / how to design around it |
|---|---|---|
| Spawn sub-agents via `Agent`/`Task` tool | Yes (`Task` is an accepted alias of `Agent`) | One per unit of work (A1). |
| Run sub-agents in parallel | Yes — lead typically spawns 3-5 concurrently | Fan-out batch. |
| Sub-agent isolated context window | Yes — each *"runs in its own context window"* | Why fan-out keeps context clean. |
| Sub-agent returns a result to orchestrator | Yes — one-shot, task in → result out | Make it a fixed JSON schema (A4, B3). |
| Send a new message into a **running** sub-agent | **No** | Re-spawn a fresh sub-agent with more context (B4). |
| Sub-agent prompts the **user** directly | **No** — *"cannot go back and ask clarifying questions"* | Orchestrator gathers input up front (B1/B5); sub-agent returns `blocked` (B3). |
| Sub-agent spawns its own sub-agents (nesting) | **No** — `Task` tool not exposed inside a sub-agent (single level) | Keep orchestration flat; orchestrator owns all fan-out. |
| Resume / continue / fork a session | Yes — SDK `resume` / `continue: true` / `forkSession`(`fork_session`); CLI `--resume`, `--continue` | Applies to a *session*, not a live `Task` sub-agent; use for top-level checkpoint (A7) or SDK workers (B6). |
| Structured JSON output | Yes — headless `--output-format json` (`result`, `session_id`, `is_error`) and `--json-schema` → `structured_output` | Basis for structured pass/fail (A4) and `blocked` (B3). |
| Durable partial progress | **Not automatic** | Each unit writes its own file atomically (A2); idempotent skip-if-exists (A3); manifest / `todo.md` (A7). |
| Automatic retry of failed sub-agents | **No** (only transient *API* errors auto-retry, via `system/api_retry`) | Orchestrator-driven, bounded, per-unit supervisor/retry (A5). |

### Net design rules for the SDD redesign
- Fan out **one sub-agent per unit**; never one sub-agent for a whole batch.
- Every unit **writes its own file atomically**; the file *is* the checkpoint.
- **Resume = skip units whose `ok` output already exists** (drive off `todo.md` / a manifest);
  retry only non-`ok` units, bounded, with the prior error included in the retry brief.
- Every sub-agent returns a **fixed JSON result** with `status: ok|failed|blocked`.
- Every phase has an **input contract**; gather all user input **before** spawning (plus a pre-flight
  scan of the spec/idea for likely questions).
- Sub-agents are **non-interactive** and **fail-fast with `blocked: needs [...]`**; the orchestrator
  collects the input and **re-spawns** (there is no way to talk to a running sub-agent).
- Keep orchestration **flat** — sub-agents can't spawn sub-agents, so the top-level command must own
  all fan-out, retry, and input-gathering.

---

## References

(All retrieved 2026-05-30. Note 301/307 redirects from the older domains.)

- Claude Code — *Create custom subagents*:
  https://code.claude.com/docs/en/sub-agents
  (*"Each subagent runs in its own context window... works independently and returns results"*;
  *"Subagents work within a single session"*; redirected from
  https://docs.claude.com/en/docs/claude-code/sub-agents)
- Claude Agent SDK — *Subagents in the SDK*:
  https://platform.claude.com/docs/en/agent-sdk/subagents
  (programmatic `agents` parameter or filesystem `.claude/agents/`; separate context, orchestrated by
  the main agent; redirected from https://docs.claude.com/en/api/agent-sdk/subagents)
- Claude Agent SDK — *Work with sessions*:
  https://platform.claude.com/docs/en/agent-sdk/sessions
  (*"Continue and resume both pick up an existing session and add to it."* `continue: true` resumes
  the most recent on-disk session; `resume` resumes a specific one; `forkSession` / `fork_session`
  branches a copy with a new id; *"When you resume a session with a new prompt, that prompt becomes a
  new message added to the session history."* `session_id` is on every result message.)
- Claude Code — *Run Claude Code programmatically (headless)*:
  https://code.claude.com/docs/en/headless
  (`-p`/`--print`; `--output-format text|json|stream-json` with `result`, `session_id`, `is_error`,
  `num_turns`, `total_cost_usd`; `--json-schema` → `structured_output`; `--resume <id>` / `--continue`;
  `system/api_retry` events; redirected from https://docs.claude.com/en/docs/claude-code/headless)
- Claude Agent SDK — *Handle approvals and user input*:
  https://platform.claude.com/docs/en/agent-sdk/user-input
  (user input / tool approvals handled by the host application via a permission callback, not a
  channel a sub-agent uses to query the human.)
- Claude API — *Tool use overview* (the `Agent` tool, formerly `Task`):
  https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
- Anthropic Engineering — *How we built our multi-agent research system*:
  https://www.anthropic.com/engineering/multi-agent-research-system
  (orchestrator-worker; lead spawns *"3-5 subagents in parallel rather than serially"*; subagents
  *"can't ask clarifying questions mid-task"* and need full briefs — *"each subagent needs an
  objective, an output format, guidance on the tools and sources to use, and clear task boundaries"*;
  *"we can't just restart from the beginning: restarts are expensive"* → checkpointing /
  *"resume from where the agent was when the errors occurred"*; subagents *"store their work in
  external systems, then pass lightweight references back to the coordinator"*; agents *"adapt
  gracefully when tools fail."*)
- GitHub — anthropics/claude-code issue #4182, *Sub-Agent Task Tool Not Exposed When Launching Nested
  Agents*: https://github.com/anthropics/claude-code/issues/4182
  (confirms sub-agents cannot spawn sub-agents — single-level depth; nested `claude -p` has no
  progress tracking / interrupt / structured-output handling from the parent.)
- Claude Code — *Best practices*: https://code.claude.com/docs/en/best-practices
  (general guidance on subagent usage and workflow structure.)
