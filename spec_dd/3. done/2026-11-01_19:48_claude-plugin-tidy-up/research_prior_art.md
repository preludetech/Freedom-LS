# Prior art: moving skills into plugins and tightening plugin prose

Limit: no Bash tool was available, so `git log` was not run. Findings come from `spec_dd/` files and a grep of the current tree. Run `git log --oneline -- claude_plugins .claude/skills` before relying on commit-level claims.

## Here

### 1. `split-claude-plugin` (done, 2026-07-28)

Dir: `spec_dd/3. done/2026-07-28_23:40_split-claude-plugin/`.

- **What:** one `fls` plugin became `ds` (django-stack), `fls-dev`, `sdd` and `fls-content`, all under `claude_plugins/`. Portable skills left `fls` and moved to `ds`. `fls-dev` kept thin overlay skills (for example `fls-dev:testing` over `ds:testing`) that point at the `ds` skill and add only the FLS delta.
- **What broke or was learned** (`research_claude_code_multi_plugin.md`, `research_reference_surface.md`, `upgrade_notes.md`):
  - Claude Code does no cross-plugin validation. A missed reference fails silently at invoke time.
  - Every namespaced identifier changed: `Skill(fls:*)` became per-plugin globs, `subagent_type` strings changed in about 20 files, and agent-memory directories were orphaned until renamed.
  - Hardcoded intra-plugin paths broke (about 16 literal `fls-claude-plugin/...` self-references).
  - `${CLAUDE_PLUGIN_ROOT}` is per plugin, so shared scripts had to be copied, not referenced.
  - The launcher (`claude.sh`) needed one `--plugin-dir` per plugin. A stale launcher plus an updated `settings.json` hard-stopped every session.
  - Its init commands had to migrate old names and clean up in a fixed order.
  - It left a bidirectional `sdd` <-> `fls-dev` dependency for later.
  - The completion checklist is a grep for old names and paths. The same grep-for-old-names approach fits this move.
- **Direct lessons for this spec:**
  - Moving skills out of `.claude/skills/` changes their names. A project skill is invoked bare (`unslop`). A plugin skill is invoked as `productivity:unslop`, and similarly for `fls-dev:domain-glossary`, `fls-dev:notifications` and `ds:code-comments`.
  - `.claude/settings.json` has `Skill(ds:*)`, `Skill(fls-dev:*)` and `Skill(sdd:*)` but no `Skill(productivity:*)`. The new plugin needs that entry, plus a `--plugin-dir` line in `claude.sh` and an `enabledPlugins` key. `/ds:init` owns the launcher skeleton.
  - The `ds` init command and its migration logic are the established way to propagate a new plugin to downstream projects.

### 2. `sdd-improve` (done, 2026-10-12)

Dir: `spec_dd/3. done/2026-10-12_20:53_sdd-improve/idea.md`.

- **What:**
  - Deleted `/sdd:next` and `/sdd:improve_idea`.
  - Deleted the `ds` and `fls-dev` security and structure commands.
  - Introduced the config-hook pattern: `## Plan Review Hooks`, `## Review Hooks` (with `Comment standard` and `Test standard`) and `## Documentation Hooks` in `.claude/sdd/config.md`.
  - Settled the rule that every FLS value reaches `sdd` only through `.claude/sdd/config.md`.
- **Relevance:**
  - `.claude/sdd/config.md` line 28 holds `Comment standard: .claude/skills/code-comments/SKILL.md`. This must change when `code-comments` moves to `ds`.
  - `.claude/sdd/config.md` line 48 lists `.claude/skills/domain-glossary/SKILL.md` as a vocabulary source. This changes when `domain-glossary` moves to `fls-dev`.
  - `claude_plugins/fls-dev/commands/init.md:328` hardcodes the `.claude/skills/code-comments/SKILL.md` path and only sets `Comment standard` when that file exists.
  - `claude_plugins/fls-dev/agents/qa-bugfixer.md:217` says "Follow the `code-comments` skill". Further bare-name references:
    - `claude_plugins/sdd/resources/writing_standard.md:50` says "Invoke the `unslop` skill".
    - `claude_plugins/sdd/commands/spec_from_idea.md:132` says "then `unslop`".
  - `.claude/skills/domain-glossary/SKILL.md` and the agent memory file `.claude/agent-memory/ds-code-reviewer/MEMORY.md` point at `.claude/skills/brand-guidelines/...`. That skill stays, so those paths are fine.
  - Generic-plugin rule: `sdd` and `ds` must not name FLS paths or skills. Pointing `sdd/writing_standard.md` at `productivity:unslop` is fine, because `productivity` is generic. `ds:code-comments` must stay free of FLS content.
  - Because of that rule, `domain-glossary` and `notifications` correctly go to `fls-dev`, not `ds`. Check `code-comments` for FLS-specific content before it goes into `ds`.
- **Lesson on prose:** `sdd-improve` already ran an informal tightening pass. `claude_plugins/sdd/resources/writing_standard.md` ends with `unslop` plus a re-read, and asks to report before and after line and word counts as an observation, not a budget. It also records the principle "coverage is the target, not length": a completeness pass first (nothing lost, one home per decision), then an earning-its-place pass. This is the closest in-repo precedent for the tightening half. It says to check that nothing is lost before cutting.

### 3. `make-sdd-more-efficient` (done, 2026-10-09)

Dir: `spec_dd/3. done/2026-10-09_09:03_make-sdd-more-efficient/idea.md`.

- **What:** defined the test tiers `none`, `targeted` and `full`. Its `none` tier includes "plugin markdown".
- **Relevance:** a pure markdown tightening pass needs no pytest beyond whatever checks the repo already enforces on `claude_plugins` (pre-commit, mirroring, and so on). Confirm in the plan which checks touch plugin markdown.

### 4. Other earlier specs

- `fls-content-plugin-extendable` (done, 2026-10-04): extension points for the `fls-content` plugin. No skill moves.
- `make-qa-more-efficient`, `testing-cleanup-junk`: no skill moves. They mention plugin files only in passing.
- `fls-dev` was earlier named `fls`. `claude_plugins/fls-dev/commands/init.md` (lines ~170-178) carries the migration for projects that still have `.claude/fls/`. That is the model for migrating anything else that downstream projects might hold.
- `learner-terminology-rename` (done) found that its sweep hit plugin skill examples in `claude_plugins/fls-dev/skills/registration/SKILL.md:199`. That was a doc example, not code. Tightening must keep examples intact.
- No past spec was found that runs a bulk prose-tightening pass over all of `claude_plugins/*`. This work is new, and no QA report exists on one.

## Overlap and conflict with queued and in-progress work

- **`test-organisation-and-hygene-2-sdd-review-and-boy-scout` (in progress)** is the main conflict.
  - It edits `claude_plugins/sdd/commands/implement_plan.md`, `plan_from_spec.md`, `pre_step_rebase` and `.claude/sdd/config.md`, and adds new agent files in `sdd`.
  - It adds a `## Testing Skills` config section.
  - The roadmap (`spec_dd/1. next/roadmap.md` ~line 302) says that spec "changes `claude_plugins/sdd/`".
  - A whole-tree tightening pass will conflict with it textually. Land one first, or exclude files it is editing, and rebase.
  - It also names `ds:testing` and `fls-dev:testing` in config, so the testing skill names should not change.
- **Roadmap spec 3, test-organisation enforcement-checks (done 2026-10-04):** changed `generate_app_map.py`, `pyproject.toml` and `.pre-commit-config.yaml`. No conflict, but those checks may scan plugin paths.
- **Roadmap and plans cite skills by bare name.**
  - The roadmap says "Skills every one of these specs should consult: `domain-glossary`, `brand-guidelines`, ..." and lists `notifications` and `domain-glossary` in several specs (lines ~131, 258, 493, 639).
  - `spec_dd/1. next/educator-interface-12-docs-and-polish/idea.md:46` cites `unslop`.
  - `spec_dd/2. in progress/learner-facing-ux-refinements/2. plan.md:18` cites `code-comments`, `unslop` and `domain-glossary`.
  - These become wrong names after the move. Decide whether to update them. Roadmap lines are live guidance for future specs. Done specs are history and should be left alone.
  - Plugin skills are invoked namespaced, so `domain-glossary` becomes `fls-dev:domain-glossary`.
- **Another overlap:** `mega-qa` (in `1. next`) mentions plugin inheritance. No direct conflict found.
- **`.claude/skills/` leaves `brand-guidelines` only.** It is referenced by path in `domain-glossary` and in `ds-code-reviewer/MEMORY.md`, so those paths stay valid. `domain-glossary/SKILL.md` line 263 also references `fls-content`.

## Elsewhere (brief)

- A web search found no direct reports on rewriting skill files. The nearest evidence is on prompt compression:
  - Aggressive compression can silently degrade edge-case behaviour. Safety and format constraints are the common casualties. The guidance is to keep a verbose original and measure on held-out cases before and after.
  - Persona and style constraints are the most fragile under shortening (largest degradation on the RoleLLM persona benchmark).
  - Correctness-gated shortening of 3.5-7.6% of a production prompt did not regress held-out correctness. Gains are modest when gated.
- Applied here:
  - Git is the verbose original.
  - Tighten by deleting padding, not by compressing rules.
  - Keep every rule, threshold, example and "never" item.
  - Review the diff per file for lost instructions, not just word counts.
  - Keep `TODO` and `@claude` comments (project rule).
- Practitioner guidance carries no direct evidence for or against skill-level rewrites. Treat the above as general, not specific to Claude Code skills.

## Web sources

- https://arxiv.org/html/2511.23271v1 (Behavior-Equivalent Token: persona and constraint fragility)
- https://gravitee.io/corpus/gen-1626/information-theory/prompt-compression.html (what compression must preserve)
- https://neurips.cc/virtual/2026/169878 (correctness-gated prompt compression)
- https://codex.danielvaughan.com/2026/08/10/trace-context-compression-instability-long-horizon-agents-codex-cli-boundary-local-verification-compaction-reliability/ (long-horizon compression instability)

status: ok · reason: complete from spec_dd and tree grep; git log was not run because no Bash tool was available
