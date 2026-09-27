# Research: how an `sdd`-owned agent file can preload testing skills without hard-coding one project's skill IDs

Scope: the idea's open question — hard-code `ds:testing`/`fls-dev:testing` into the new `sdd`-owned
batch-worker agent file's `skills:` frontmatter (as `qa-bugfixer` does), or use project-level
indirection. Builds on `research_sdd_standards_hooks.md` (already covers how each SDD phase loads
skills today and why `implement_plan`'s batch worker has no `skills:` slot) — that ground is not
repeated here.

## 1. What Claude Code 2.1.x actually supports

Confirmed against `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md` +
`resources/subagents.md` first, then https://code.claude.com/docs/en/sub-agents and
https://code.claude.com/docs/en/skills (fetched 2026-09-27):

- **`skills:` frontmatter is a static list, resolved at agent-file-parse time.** There is no
  templating, env-var substitution, or config-file read inside frontmatter — an agent file cannot say
  "preload whatever `.claude/sdd/config.md` names." Confirmed by `resources/subagents.md:26-32` in
  this repo and by the docs page's own description of the field ("inject the full skill content of
  each listed skill... at startup").
- **A missing/disabled skill in `skills:` fails soft, not hard.** Verbatim from
  https://code.claude.com/docs/en/sub-agents: "If a listed skill is missing or disabled, for example
  by your organization's policy, Claude Code skips it and logs a warning to the debug log." No
  session-visible error, no aborted spawn — just a debug-log line only visible with `--debug`. This
  matters directly for the idea's worry: **hard-coding `fls-dev:testing` into an `sdd`-owned file does
  not break a project that has no `fls-dev` overlay** — the reference is silently dropped, not fatal.
  The cost of the naive hard-code option is real (see §3) but it is not "the agent file fails to
  load," which is the sharper failure the idea's phrasing ("doesn't warrant a generic naming
  mechanism") seems to guard against.
- **The `Agent`/`Task` tool has no spawn-time skills parameter.** The `prompt` string is the only
  spawn-time input channel (already established in `resources/subagents.md:18-24`); there is no
  `skills:` argument alongside `subagent_type`/`model` on the tool call itself. So "tell the agent
  what skills to use at spawn time" can only happen as **prose in the prompt**, not as a structured
  preload — which is exactly the fallback the docs themselves name: "without [`skills:`], the subagent
  can still discover and invoke project, user, and plugin skills through the `Skill` tool during
  execution." A subagent's `tools:` allowlist (when the agent file specifies one) must include `Skill`
  for this to work — `qa-bugfixer.md:7` already does (`tools: Bash, Read, Edit, Write, Glob, Grep,
  Skill`).
- **A brief can already tell the agent to invoke `Skill(x:y)` as a first step, and this is not a novel
  pattern.** `qa-bugfixer.md:52-53` (an agent that *does* preload via frontmatter) still hedges with
  exactly this instruction: "They are preloaded via this agent's `skills:` frontmatter; if their
  content is not already in your context, invoke them with the `Skill` tool before writing anything."
  I.e. even the fully-hard-coded example already treats "instructed explicit invocation" as the
  belt-and-suspenders fallback to static preload, not a lesser alternative to it.
- **Project-level `.claude/agents/<name>.md` can shadow a plugin agent, but only by bare (unscoped)
  name — not by scoped `plugin:name` identifier.** The collision table
  (Managed settings > `--agents` CLI flag > `.claude/agents/` > `~/.claude/agents/` > plugin
  `agents/` dir) resolves same-named agents, and project scope beats plugin scope. But: "Names can't
  contain `:`, which is reserved for plugin-scoped identifiers such as `my-plugin:reviewer`. Claude
  Code doesn't load a file whose name contains one and logs an error to the debug log." So a project
  cannot define an agent literally named `sdd:sdd-implementer` to shadow `sdd`'s own file — it could
  only shadow a **bare** `sdd-implementer`. Every existing SDD fan-out spawn in this repo uses the
  fully-qualified scoped form (`subagent_type: "sdd:sdd-worker"`, `"sdd:sdd-mechanic"` — confirmed by
  grep across every command file, e.g. `implement_plan.md`, `plan_from_spec.md`,
  `fanout_recipe.md:34`), specifically to get deterministic resolution regardless of what else is
  installed. Docs describe the CLI `--agent`/`@`-mention paths explicitly; the docs' treatment of the
  *programmatic* `Agent` tool's `subagent_type` parameter is thinner, but the same named-registry
  mechanism underlies both, so the same bare-vs-scoped distinction should be assumed to apply — this
  is inference from the shared registry description, not a verbatim citation for the `Agent` tool
  specifically, and is flagged as such.
  - **Consequence:** project-level agent-file override is only available if `implement_plan.md`
    switches its batch-worker spawn to a **bare** `subagent_type: "sdd-implementer"`. That trades away
    the collision-safety the scoped-everywhere convention exists for (any other installed plugin, or
    the user's own `~/.claude/agents/`, defining an unscoped `sdd-implementer` would silently
    intercept every `implement_plan` batch). This is a real cost, not a free indirection.

Citations: https://code.claude.com/docs/en/sub-agents, https://code.claude.com/docs/en/skills,
https://code.claude.com/docs/en/plugins (fetched 2026-09-27);
`claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`,
`claude_plugins/sdd/skills/claude-code-authoring/resources/subagents.md`.

## 2. Existing indirection already in this repo

`.claude/sdd/config.md` (written/extended by `claude_plugins/sdd/commands/init.md` Step 2) already
carries exactly this shape for three unrelated concerns, and the shape is deliberate, documented
policy, not incidental:

- **`## Worktree Scripts`** — Setup/Teardown script paths, blank by default. `init.md:162-166`: "`sdd`
  is portable and names no product here — if another plugin owns those scripts in this project, the
  user points these keys at them." Read by `protected/start_worktree.md` / `finish_worktree.md`.
- **`## Rebase Hooks`** — Rebase command / Front-end check paths, blank by default, same "`sdd` is
  portable and names no product here" language (`init.md:170-172`). Read by
  `protected/pre_step_rebase.md` Steps 1–2: "Read `.claude/sdd/config.md`... Under `## Rebase Hooks`,
  look at the `Rebase command` value: blank, or the file or section absent → ... Stop. a non-blank path
  → read that file and follow its steps here." In this project the values are filled with other
  plugins' files (`claude_plugins/django-stack/commands/rebase_main.md`,
  `claude_plugins/fls-dev/commands/protected/frontend_check.md` — see `.claude/sdd/config.md:15-20`),
  i.e. **an `sdd`-owned config file already routinely names other plugins' artifacts by project-level
  choice**, not by being hard-coded into `sdd`'s shipped files.
- **`## Vocabulary Sources`** — a list of project files, empty by default, consulted by idea/spec/plan
  commands before coining a word (`init.md:174-178`; `.claude/sdd/config.md:22-31` in this project
  lists `.claude/skills/domain-glossary/SKILL.md`, `freedom_ls/*/models.py`, `docs/product/`,
  `docs/app_structure.md`).

All three are **read at depth 0**, by an `sdd`-owned command or protected helper, via plain
section/key-name parsing (no schema, "keep those exact" per `init.md:129-131`) — never by a subagent,
and never via agent-file frontmatter. This is the mechanism already proven for "an `sdd` command needs
a project-specific value without `sdd` naming any product."

A fourth section, `## Testing Skills`, would fit this pattern exactly:

```markdown
## Testing Skills

Skills to invoke before writing or reviewing tests. One skill ID per line, most authoritative first.
Leave the list empty if this project has no such skills.

- ds:testing
- fls-dev:testing
```

`implement_plan.md` Step 2 already runs at depth 0, immediately before each batch spawn — the same
place Step 0's `pre_step_rebase.md` read already happens. It could read this section the same way
`pre_step_rebase.md` reads `## Rebase Hooks`, and fold the named IDs into the batch subagent's spawn
prompt as an instruction ("before writing any code, invoke `Skill(<id>)` for each of: <ids from
config>"), rather than into the agent file's `skills:` frontmatter. This needs the new agent file's
`tools:` to include `Skill` (as `qa-bugfixer.md` already does) but needs no `skills:` entries naming
any specific project's plugins.

`ds:testing` / `fls-dev:testing` pairing precedent: `fls-dev:testing`'s own description says "Use
alongside `ds:testing` when writing pytest tests in the FreedomLS repo" and its body opens "Read
`Skill(ds:testing)` first for the generic pytest/TDD/AAA methodology. This overlay adds **only** the
FreedomLS specifics" (`claude_plugins/fls-dev/skills/testing/SKILL.md:3,9`). So the "list of skill IDs,
most-authoritative-first" framing used above for `## Vocabulary Sources` maps onto this pairing
directly — a generic-then-overlay skill list is exactly what a config-section list of skill IDs, read
in order, already expresses without `sdd` needing to know the pairing exists.

## 3. Options, with trade-offs

**A — Hard-code both skill IDs into the `sdd`-owned agent file's `skills:` frontmatter** (the
`qa-bugfixer` pattern, applied directly).
- *For:* zero new mechanism; matches the one working example (`fls-dev:qa-bugfixer`) exactly; true
  startup preload (content in context before the agent's first turn, not gated on it choosing to
  invoke `Skill`).
- *Against:* on a project with no `fls-dev` overlay the `fls-dev:testing` entry is dead weight (though
  per §1, silently skipped, not fatal); it names a second plugin's namespace inside a file `sdd`
  ships, which is a new instance of exactly the coupling `claude_plugins/sdd/README.md:12-14` already
  flags ("`sdd` is not yet fully standalone... FLS commands spawn the `sdd` agents" — this would add
  "an `sdd` agent file spawns knowledge of an FLS skill" in the other direction). It is honest,
  low-effort, and matches this project's actual needs today — but is the one option the idea's own
  text says to consider *not solving* ("If hard-coding two skill IDs into an `sdd`-owned agent file
  doesn't warrant a generic naming mechanism, the spec should say so plainly and record it as the same
  kind of documented coupling `claude_plugins/sdd/README.md` already carries").

**B — `## Testing Skills` config section + brief-instructed `Skill(...)` invocation** (§2's proposal).
- *For:* the `sdd`-owned agent file and command stay genuinely generic — no project's plugin names
  appear in any `sdd`-shipped file, only in this project's own `.claude/sdd/config.md`; reuses a
  pattern already proven three times over (`init.md`, `pre_step_rebase.md`) rather than inventing a
  new one; degrades cleanly to "no testing skills configured" (empty list, same as
  `## Vocabulary Sources`'s empty-list default) for a project with no testing skills at all; the
  fallback instruction ("invoke `Skill(x)` before writing anything") is the same one `qa-bugfixer.md`
  itself already relies on as a hedge, so it is proven to work with real skill content, not a
  theoretical substitute for preload.
- *Against:* content lands in context on the agent's first tool call rather than literally at spawn
  (a difference in *when*, not *whether*, given the brief makes the invocation the first instructed
  action); needs `implement_plan.md` Step 2 to gain a config-read (a small, well-precedented addition,
  not a new subsystem); needs `sdd:init` (or a manual edit, same as the other three sections today) to
  grow a fourth `## Testing Skills` section with the same "leave blank, sdd names no product" framing.

**C — The agent file is owned by `fls-dev` (or `ds`) instead of `sdd`.**
- *For:* removes the naming tension entirely — a `fls-dev`-owned file hard-coding `fls-dev:testing` is
  not a portability problem, the same way `qa-bugfixer.md` isn't one today.
- *Against:* `implement_plan.md` is an `sdd` command; having it spawn a non-`sdd` agent
  (`subagent_type: "fls-dev:sdd-implementer"` or similar) deepens the exact bidirectional coupling
  `research_sdd_standards_hooks.md` §3 already concluded is *consistent with, not a new instance of*,
  the documented, deferred `sdd` ↔ `fls-dev` coupling — but it is still a new **direction** of that
  coupling (an `sdd` command hard-picking a specific other plugin's agent, vs. today's coupling being
  `fls-dev` commands spawning `sdd`'s generic workers). A project without `fls-dev` would need `sdd`
  itself to fall back to something when `fls-dev` isn't installed — reintroducing a config-driven
  branch inside `implement_plan.md` anyway, at which point Option B's mechanism is doing the same job
  with one fewer moving part (no second plugin-owned agent file to keep in sync with `sdd`'s own
  batch-worker prompt/report shape).

**D — Project-level `.claude/agents/<bare-name>.md` override.**
- *For:* real startup preload, project-specific, no `sdd`-shipped file needs per-project content.
- *Against:* per §1, only works if `implement_plan.md` spawns the batch worker by **bare** name
  (`"sdd-implementer"`), sacrificing the scoped-everywhere collision-safety every other SDD spawn in
  this repo relies on — a real, not hypothetical, regression, since any other installed plugin or a
  stray `~/.claude/agents/sdd-implementer.md` would silently intercept every batch. Also asks every
  adopting project to author and maintain a full agent file (frontmatter + body) just to name two
  skill IDs, which is disproportionate next to Option B's four-line config-section edit.

## Recommendation

**Option B.** It is the smallest change that keeps `sdd` genuinely portable: add `## Testing Skills`
to `.claude/sdd/config.md` (and its default block in `commands/init.md` Step 2, worded like the
existing three sections — blank/empty by default, "`sdd` is portable and names no product here"), have
`implement_plan.md` Step 2 read it the same way `pre_step_rebase.md` reads `## Rebase Hooks`, and have
the new batch-worker agent file's brief instruct the spawned worker to invoke `Skill(<id>)` for each
configured ID as its first action — with `Skill` present in the agent's `tools:` allowlist. No skill ID
ever needs to appear inside any file `sdd` ships. This project's own `.claude/sdd/config.md` would then
carry `ds:testing` and `fls-dev:testing` exactly where its `## Rebase Hooks` section already carries
`claude_plugins/django-stack/commands/rebase_main.md` and
`claude_plugins/fls-dev/commands/protected/frontend_check.md` today — the identical shape, not a new
one.

If the spec instead judges this not worth a fourth config section for two lines of frontmatter, Option
A is the documented-coupling fallback the idea itself names — legitimate, cheap, and consistent with
`qa-bugfixer.md`'s precedent, provided the spec states plainly (per the idea's own framing) that this
is accepted `sdd` ↔ `fls-dev` coupling rather than an oversight. Given Option B costs one config
section and one small Step-2 read — reusing, not inventing, the mechanism `init.md` and
`pre_step_rebase.md` already establish — it is worth taking over Option A's silence.

## Files and pages read (citations)

- `spec_dd/1. next/test-organisation-and-hygene-2-sdd-review-and-boy-scout/idea.md`
- `spec_dd/1. next/test-organisation-and-hygene-2-sdd-review-and-boy-scout/research_sdd_standards_hooks.md`
- `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`,
  `resources/subagents.md`
- `claude_plugins/fls-dev/agents/qa-bugfixer.md`
- `claude_plugins/sdd/README.md`
- `claude_plugins/sdd/commands/init.md`
- `claude_plugins/sdd/commands/protected/pre_step_rebase.md`
- `claude_plugins/sdd/commands/implement_plan.md`
- `.claude/sdd/config.md`
- `claude_plugins/fls-dev/skills/testing/SKILL.md`
- `claude_plugins/fls-dev/templates/config.md`
- `claude_plugins/sdd/skills/claude-code-authoring/resources/fanout_recipe.md`
- https://code.claude.com/docs/en/sub-agents (fetched 2026-09-27) — skills preload/skip behaviour,
  agent-file frontmatter fields, subagent name collision/priority table, scoped-identifier rules
  (`:` reserved), explicit invocation (`--agent`, `@`-mention) semantics
- https://code.claude.com/docs/en/skills (fetched 2026-09-27) — subagent `skills` field description
- https://code.claude.com/docs/en/plugins (fetched 2026-09-27) — plugin component model, scoped
  identifiers, install/enable layering

status: ok
