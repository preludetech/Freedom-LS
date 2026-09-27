# Research: agent-file shape for the batch implementer, the test-organisation reviewer, and the boy-scout

Scope: for each of the three roles `implement_plan` needs (batch implementer, test-organisation
review dimension, boy-scout), whether it should be its own agent file or an `sdd:sdd-worker` /
`general-purpose` spawn given wider tools — covering tools, model tier, how it gets the two testing
rules, naming, and whether the boy-scout's guardrails are tool-enforceable. Findings, not a spec.

## 0. The decisive constraint: tool grants cannot be widened at spawn time

This resolves the framing of the open question ("`sdd:sdd-worker`-shaped spawn given `Edit`/`Bash`
breadth") before the per-role analysis: **it is not a real option.** The `Agent` tool's spawn-time
parameters are `subagent_type`, `model`, and `name` only — there is no parameter that adds or widens
the tool set a named subagent's own frontmatter declares. A subagent's tools are fixed at whichever of
these applies: its own `tools:`/`disallowedTools:` frontmatter (if it has an agent file), or — for the
built-in `general-purpose` type, which has no agent file and no `tools:` frontmatter — the full tool
set available to the parent session, minus the always-stripped tools (`Agent`, `AskUserQuestion`, and
others) and minus the further reduction applied when running in the background. Either way, **the
caller's own tool set is the ceiling; nothing widens a named agent's declared tools per spawn.**
(Confirmed against https://code.claude.com/docs/en/sub-agents — see the model-resolution and tool
sections cited throughout, and the direct query results below.)

Concretely: `sdd:sdd-worker`'s frontmatter is `tools: Read, Glob, Grep, WebFetch, WebSearch, Write`
(`claude_plugins/sdd/agents/sdd-worker.md:7`). There is no way for `implement_plan.md` (or any other
caller) to spawn "`sdd:sdd-worker` but with `Bash` and `Edit` added" — that file's tool list is fixed
regardless of what the calling command's own `allowed-tools` permit. Widening `sdd-worker`'s own
frontmatter to add `Bash`/`Edit` would apply to **every** use of `sdd:sdd-worker` across the whole SDD
workflow (plan review dimensions, the skills/MCP scan, any future fan-out), not just the boy-scout —
an unacceptably broad side effect for a one-off need.

So the real choice, for every one of the three roles, collapses to exactly two options:

1. **Reuse the built-in `general-purpose` type** (as `implement_plan.md` Step 2 already does today for
   the batch worker), which inherits the full tool set the depth-0 command itself is allowed
   (`implement_plan.md`'s own `allowed-tools: Read, Glob, Grep, Write, Edit, Bash, Skill, Agent`) —
   but gets **no `skills:` frontmatter slot at all**, since `general-purpose` has no agent file.
2. **Author a new, dedicated agent `.md` file** with its own `tools:`, `model:`, and (optionally)
   `skills:` frontmatter, shaped like `qa-bugfixer.md` or `sdd-worker.md`.

There is no third "sdd-worker-with-more-tools" option. This single finding is the anchor for the
per-role recommendations below.

## 1. Batch implementer

**Today:** bare `subagent_type: "general-purpose"`, per-spawn `model: "sonnet"`
(`implement_plan.md:33`). No agent file, so no `skills:` slot — the two testing rules reach it only
via skill auto-trigger on the plan's own wording (`research_sdd_standards_hooks.md` §1, already
established; not re-derived here).

**Tools needed:** exactly what it already gets via `general-purpose` today — `Bash` (to run
`uv run pytest` and make the `[batch N]` commit itself, `implement_plan.md:36-38`), `Edit`/`Write`
(production + test code), `Read`/`Glob`/`Grep` (investigate existing code), `Skill` (to invoke the
preloaded testing skills explicitly if auto-trigger doesn't fire). `Agent` is irrelevant — it is
always stripped from subagents regardless of what's listed.

**Recommendation: give it a dedicated new agent file** (e.g. `claude_plugins/sdd/agents/sdd-implementer.md`),
`tools: Bash, Read, Edit, Write, Glob, Grep, Skill` (identical breadth to today's `general-purpose`
grant, minus the tools that would be stripped anyway), `skills: [ds:testing, fls-dev:testing]` — the
exact `qa-bugfixer.md` pattern (`tools:`/`skills:` frontmatter, `claude_plugins/fls-dev/agents/qa-bugfixer.md:7-13`).
This is the one place a dedicated file earns its keep over `general-purpose`: it is spawned **every
batch, every spec**, so a preloaded `skills:` slot removes the auto-trigger gamble on every single
spawn, not just once. Reusing `general-purpose` (option 1 above) is a real fallback that preserves
current behaviour with zero migration risk, but forfeits the preload — the exact gap
`research_sdd_standards_hooks.md` §1 already flags as this spec's reason for existing.

**Model tier:** `sonnet`, matching `implement_plan.md`'s current per-spawn `model: "sonnet"`
(`implement_plan.md:33`). Per the confirmed model-resolution order — **per-invocation `model`
parameter (priority 1) → subagent's own frontmatter `model` (priority 2) → `CLAUDE_CODE_SUBAGENT_MODEL`
→ parent's model** — `implement_plan.md`'s existing per-spawn `model: "sonnet"` argument to the `Agent`
tool call continues to govern even after the batch worker gets its own file, so the new file's
frontmatter `model: sonnet` is a *default*, not a behaviour change: it only matters if some future
caller spawns `sdd:sdd-implementer` without a per-spawn override. The existing "user can override to
`model: "opus"` per spawn" affordance (`implement_plan.md:33`) is unaffected, since per-spawn always
wins. Note the per-spawn `model` parameter only accepts the bare aliases `sonnet|opus|haiku`
(`model_tiering.md`, citing issue #34821) — not a dated ID — so if reproducible pinning is wanted, it
has to live in the frontmatter and be invoked *without* a per-spawn override, which would give up the
opus-override affordance. Given `implement_plan.md` already wants that affordance, keep the per-spawn
override and treat the frontmatter `model:` as an alias-level fallback, not a pinned ID.

## 2. Test-organisation review dimension

**Fits `sdd:sdd-worker` unmodified — no new agent file.** This is already what the idea's "What is
settled" section decided (`idea.md`: "one `sdd:sdd-worker` per dimension, writing a `.sdd-work/` file
with a `status:` footer"), and the tool/model facts back it up:

- **Tools:** the dimension only reads the batch's diff, `docs/app_structure.md`, and writes one
  `.sdd-work/` report — exactly `sdd-worker`'s existing `Read, Glob, Grep, WebFetch, WebSearch, Write`
  (`sdd-worker.md:7`). It needs no `Edit`, no `Bash` (verifying does not mean fixing — fixing is the
  boy-scout's job). This is the same shape `plan_from_spec.md` Step 6's plan-review dimensions already
  use (`plan_from_spec.md:96-104`), which this spec's idea explicitly models itself on.
- **How it gets the two rules, given `sdd-worker` has no `skills:` frontmatter:** the same way
  `plan_from_spec.md` Step 6's dimensions and `plan_structure_review.md` Step 1 already get their
  project-specific inputs — **prompt-baked instruction, not agent-frontmatter preload.**
  `plan_structure_review.md` Step 1 explicitly tells its spawned worker to read
  `docs/app_structure.md` before checking anything (`research_sdd_standards_hooks.md` §5, already
  established) — no skill or frontmatter mechanism is used for that either. The equivalent for this
  review dimension is a Step-2/3-composed prompt that says, verbatim, "invoke `Skill(ds:testing)` and
  `Skill(fls-dev:testing)` before checking test placement and cross-app imports, then read
  `docs/app_structure.md`'s dependency table" — baked into the per-unit brief the way the fan-out
  recipe already requires ("Bake into each prompt everything the worker needs",
  `claude-code-authoring/resources/fanout_recipe.md:15`). This is not a workaround; it is the
  established idiom for a shared, generic agent file (`sdd-worker` is reused across every SDD fan-out
  dimension in every project) that must not carry any one caller's project-specific skill IDs in its
  own frontmatter. Hard-coding `skills: [ds:testing, fls-dev:testing]` onto `sdd-worker.md` itself
  would push that FLS-shaped skill pair into **every** other dimension spawned as `sdd:sdd-worker`
  too — the plan's "no junk files" or "vocabulary match" dimensions gain irrelevant preloaded content —
  which is a strictly worse and wider coupling than the one the idea's own "Open until the spec"
  section is already worried about for the batch-implementer's hard-coded `skills:` (`idea.md`, the
  "generic across projects" paragraph). Prompt-baking sidesteps that entirely: the coupling lives in
  `implement_plan.md`'s own prose (already `sdd`-owned, already documented as coupled per
  `claude_plugins/sdd/README.md:12-14`), not in a shared agent file's frontmatter.
- **Model:** `sonnet`, `sdd-worker`'s existing default (`sdd-worker.md:8`) — matches the "non-interactive
  fan-out" tier (`claude-code-authoring/resources/model_tiering.md:10-14`). No reason to deviate: this
  is read-only analysis against a known table, not code judgement heavier than any other plan-review
  dimension already running at this tier.

**Conclusion:** no new agent file for the reviewer. The only artifact this role needs is the new
review-dimension text inside `implement_plan.md` (or wherever it's wired), following the exact
`plan_from_spec.md` Step 6 fan-out shape, with the skill/doc reads baked into that dimension's prompt.

## 3. Boy-scout

**Tools needed:** `Bash` (git mv/rename, `git show --name-only <batch-sha>` to get the touched-file
list, its own labelled commit(s), running `uv run pytest` on affected apps — `idea.md`'s "What is
settled" list), `Edit`/`Write` (moving/splitting test files, adding the "not a bug, here's why"
comment), `Read`/`Glob`/`Grep` (locate the files, check `docs/app_structure.md`), `Skill` (invoke
`ds:testing`/`fls-dev:testing` for the two rules it applies). This is materially the same tool list as
`qa-bugfixer.md`'s `Bash, Read, Edit, Write, Glob, Grep, Skill` (`qa-bugfixer.md:7`), minus
`WebFetch`/`WebSearch` (the boy-scout needs no external lookups).

Per §0, `sdd:sdd-worker` cannot supply this (no `Bash`/`Edit` in its fixed frontmatter, and nothing
widens it per spawn). That leaves `general-purpose` (inherit-everything, no `skills:` slot) or a new
file. Two more facts push this specifically toward a **new dedicated agent file**, matching the idea's
own steer ("closer in shape to `qa-bugfixer` than to `sdd-worker`", `research_sdd_standards_hooks.md`
§4c):

- **`sdd:sdd-mechanic` is the wrong tier despite overlapping tools.** Its tool list (`Bash, Read, Edit,
  Write, Glob, Skill` — `sdd-mechanic.md:9`) is close, and it already does git mv-shaped chores, but
  its entire contract is "no design judgement... stop and return `status: blocked` rather than
  guessing" (`sdd-mechanic.md:14,20,26`) on Haiku at `effort: low`. The boy-scout's job is explicitly
  judgement-bearing: deciding a move is "mechanical," recognising "obvious, genuinely broken code,"
  deciding when the ~3-file/1-dependency budget is exceeded and writing a deferred-work note instead
  (`idea.md`'s "What is settled" list) — all things `sdd-mechanic`'s own file says it must **not** do.
  Reusing it either breaks its documented contract or forces every boy-scout run into
  `status: blocked` at the first non-mechanical judgement call.
- **A repeatable, multi-step procedural contract (budget check, one-move-one-edit-commit-shape for
  rebase safety, defer-to-cleanup-spec logic, the "flag but don't fix" rule, the report shape) is
  exactly what an agent file is for** — the same reasoning that makes `qa-bugfixer` (not a bare
  `general-purpose` spawn) the TDD bug-fix pattern in this repo. Repeating that procedural detail in
  `implement_plan.md`'s prose on every batch (the `general-purpose` fallback) risks drift between
  batches and bloats the orchestrating command file; a dedicated file keeps it in one place.

**Recommendation:** a new `claude_plugins/sdd/agents/sdd-boy-scout.md`, `tools: Bash, Read, Edit,
Write, Glob, Grep, Skill`, `skills: [ds:testing, fls-dev:testing]`, `model: sonnet`. Same
`model:`-frontmatter-is-a-fallback caveat as the batch implementer applies if `implement_plan.md`
passes a per-spawn `model` override.

**Whether the "only touch this batch's files, only mechanical moves" guardrail is tool-enforceable:
no — only the brief (plus a cheap post-hoc check) can enforce it.** Tool grants
(`tools:`/`disallowedTools:`) gate by **tool name** (`Edit` on/off, `Bash` on/off) — Claude Code has no
per-subagent mechanism to scope *which paths* a granted `Edit`/`Bash` may touch to a dynamic,
per-spawn file list computed from `git show --name-only <sha>`. The one real path-scoping primitive in
this repo, `django-stack`'s `PreToolUse` hooks (`security-guard.sh`,
`claude_plugins/django-stack/hooks/hooks.json`), block by **content pattern** globally for every
`Write`/`Edit` in the session — they are not, and are not built to be, parametrised per-subagent-spawn
with "the file list from batch N's commit." Building that (a hook that reads a per-run scratch file
naming the allowed paths and reads the invoking agent's identity) is technically conceivable but is
exactly the kind of Claude-Code-hook-based orchestration the `claude-code-authoring` skill defers for
now ("hooks... adopting them is explicitly out of scope for the current workflow",
`SKILL.md:79`/`resources/interactive_cli.md`). So enforcement has two real layers, neither of them tool
grants:

1. **The brief** — per the fan-out recipe's own rule ("Bake into each prompt everything the worker
   needs"; the idea's own settled text: "the exact file list (never 'look at what changed')" —
   `idea.md`), the boy-scout's prompt must contain the literal file list from
   `git show --name-only --pretty=format: <batch-N-sha>`, and the agent file's own prose must say "fix
   only these files, nothing else" as an explicit behavioural rule it is trusted to follow — the same
   trust model `qa-bugfixer.md` already relies on for "stage only the files you created or modified...
   NEVER use `git commit -a`" (`qa-bugfixer.md:114-125`), which is enforced by instruction, not tooling.
2. **A cheap post-hoc mechanical check**, not a tool restriction: after the boy-scout returns, a
   `sdd:sdd-mechanic` spawn (no design judgement needed — this is a pure set-comparison) can verify
   `git show --name-only <boy-scout-sha>` ⊆ the batch's own file list, and flag (not silently fix) any
   file outside it. This gives an actual enforcement point without inventing hook infrastructure, and
   fits `sdd-mechanic`'s existing "mechanical chores that need no design judgement" contract exactly
   (`sdd-mechanic.md:1-8`) — unlike reusing it *as* the boy-scout (see above), using it *after* the
   boy-scout for a yes/no path check is squarely inside its mandate.

## 4. Naming conventions for new agent files in this repo

Observed pattern across every existing agent file (`sdd-worker.md`, `sdd-mechanic.md`,
`qa-bugfixer.md`, `qa-data-helper.md`, `code-reviewer.md`, `content-formatter.md`): kebab-case,
2-3 words, `name:` frontmatter matches the filename stem, and the plugin's own namespace prefix
(`sdd:`, `fls-dev:`, `ds:`) is supplied by the invocation (`subagent_type: "sdd:sdd-worker"`), never
duplicated inside the agent's own `name:` field beyond the `sdd` plugin's own convention of prefixing
its two existing agents with `sdd-` (`sdd-worker`, `sdd-mechanic` — the only plugin that does this;
`fls-dev`'s `qa-*` agents use a role prefix, not the plugin name, and `code-reviewer`/`content-formatter`
use no prefix at all). Since both new files belong in `claude_plugins/sdd/agents/` (the workflow
change is `sdd`-owned per `research_sdd_standards_hooks.md` §3), the consistent names are:

- `claude_plugins/sdd/agents/sdd-implementer.md`, `name: sdd-implementer`
- `claude_plugins/sdd/agents/sdd-boy-scout.md`, `name: sdd-boy-scout`

Registration needs no manifest edit: agent files are discovered by directory convention (recursive
scan of each enabled plugin's `agents/` directory, matched by the `name:` frontmatter field, not the
filename) — confirmed against https://code.claude.com/docs/en/sub-agents. `claude_plugins/sdd/.claude-plugin/plugin.json`
carries only plugin-level metadata (`name`, `version`, `description`) and does not enumerate agents
(`plugin.json` for `sdd` has no `agents` key), consistent with every other plugin in this repo. So
dropping the two new `.md` files into `claude_plugins/sdd/agents/` is sufficient; no companion registry
edit exists to make.

## 5. Summary table

| Role | Fits `sdd:sdd-worker`? | Fits `general-purpose`? | Recommended | Tools | Model | Skills preload |
|---|---|---|---|---|---|---|
| Batch implementer | No (needs Bash/Edit) | Yes (today's behaviour) | **New file** `sdd-implementer` | Bash, Read, Edit, Write, Glob, Grep, Skill | sonnet (per-spawn override still wins) | `ds:testing`, `fls-dev:testing` via frontmatter |
| Test-org reviewer | **Yes, as-is** | Not needed | **Reuse `sdd:sdd-worker`** | Read, Glob, Grep, WebFetch, WebSearch, Write (unchanged) | sonnet (unchanged) | Prompt-baked `Skill(...)` invocation, not frontmatter |
| Boy-scout | No (needs Bash/Edit) | Possible but loses skills preload + procedural home | **New file** `sdd-boy-scout` | Bash, Read, Edit, Write, Glob, Grep, Skill | sonnet | `ds:testing`, `fls-dev:testing` via frontmatter |

## Sources

- https://code.claude.com/docs/en/sub-agents — subagent frontmatter fields, model resolution order,
  tool-inheritance ceiling ("subagents cannot be granted broader tools than the invoking session has"),
  `general-purpose`'s inherit-all-tools behaviour, directory-convention agent discovery (no manifest),
  and the `Agent`/Task tool's actual spawn-time parameter set (`subagent_type`, `model`, `name` only —
  no tool-widening parameter). Queried directly for this research (two targeted fetches) in addition to
  the citations already carried in `claude_plugins/sdd/skills/claude-code-authoring/resources/subagents.md`
  and `resources/model_tiering.md`.
- `claude_plugins/sdd/agents/sdd-worker.md`, `sdd-mechanic.md`
- `claude_plugins/fls-dev/agents/qa-bugfixer.md`, `qa-data-helper.md`
- `claude_plugins/django-stack/agents/code-reviewer.md`
- `claude_plugins/fls-content/agents/content-formatter.md`
- `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`, `resources/subagents.md`,
  `resources/model_tiering.md`, `resources/fanout_recipe.md`
- `claude_plugins/sdd/commands/implement_plan.md`, `plan_from_spec.md` (Step 6)
- `claude_plugins/sdd/README.md`
- `claude_plugins/sdd/.claude-plugin/plugin.json`
- `claude_plugins/django-stack/hooks/hooks.json`
- `spec_dd/1. next/test-organisation-and-hygene-2-sdd-review-and-boy-scout/idea.md`,
  `research_sdd_standards_hooks.md` (sibling; not repeated here)

status: ok
