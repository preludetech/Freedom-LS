# Research: best practices (claude-plugin-tidy-up)

Date: 2026-11-01. Sources are Anthropic docs fetched today, plus the project's own skills.

## 1. Packaging skills into plugins

Anthropic guidance:

- **Plugin vs standalone.** Standalone `.claude/` config is right while it serves one project or one person. Make a plugin to share, reuse across projects or version releases. [plugins/create]
- **Namespacing is automatic.** A plugin skill is invoked as `/<plugin-name>:<skill>` (e.g. `/my-plugin:deploy`), so two plugins can each ship `hello` without collision. Plugin `name` in `plugin.json` is the prefix; it must be stable. [plugins/create]
- **Layout.** `.claude-plugin/plugin.json` holds only the manifest. `skills/<name>/SKILL.md` sits at the plugin root, not inside `.claude-plugin/` (a common failure: "plugin loads but its skills are missing"). `commands/` is the older form; use `skills/` for new work. [plugins/create]
- **Migration recipe.** Copy `.claude/skills` into the plugin, test with `claude --plugin-dir ./plugin`, check each component under its new name, then delete the originals. While both exist, bare `/deploy` and `/my-plugin:deploy` both work, so no collision, but duplicates inflate context. Delete the originals once confirmed. [plugins/create]
- **Validate.** `claude plugin validate <path>` (add `--strict`) checks manifest and every skill's frontmatter. `/reload-plugins` applies edits mid-session. `claude plugin list` shows load state. [plugins/create]
- **Context cost is per enabled plugin, every turn.** Name and description of each model-invocable skill/agent/command sits in context on every turn; the body loads only on use. So every moved skill with a description adds standing cost wherever its plugin is enabled. `disable-model-invocation: true` removes that cost for hand-invoked skills. A plugin's footprint can be measured (`plugins/measure`). [plugins/overview]
- **Scope.** Plugins install at user, project (committed `.claude/settings.json`, each collaborator still installs) or local scope. Putting generic skills (`productivity`, `ds`) in plugins means each consumer project must enable them. [plugins/overview]
- **Skill-authoring rules (platform docs).** [skills best-practices]
  - `name`: at most 64 chars, lowercase/digits/hyphens, no reserved words ("anthropic", "claude"). Prefer consistent naming, gerund or noun phrase; avoid vague names (`helper`, `utils`).
  - `description`: at most 1,024 chars, third person, says what the skill does and when to use it, with concrete trigger terms. It is the sole selection signal among possibly 100+ skills.
  - Keep SKILL.md body under 500 lines; push detail into separate files.
  - Keep references one level deep from SKILL.md (nested links get partially read via `head`). Give reference files over 100 lines a table of contents. Name files descriptively.
  - Use one term consistently; avoid time-sensitive text; offer a default rather than many options.
  - Set degrees of freedom by fragility: low freedom for fragile sequences, high for judgement tasks.

Implication for this work: moving a skill changes its invocation name (`/answer` becomes `/productivity:answer`; a `fls-dev` skill gets `fls-dev:` prefix). Skill-to-skill calls and any "use the X skill" prose should use the final name.

## 2. Writing concisely (Anthropic)

- "The context window is a public good." Default assumption: Claude is already very smart; add only context it lacks. Challenge each paragraph: does Claude need this, can I assume it, does it justify its token cost. Example: a 50-token PDF snippet beats a 150-token one that explains what PDFs are. [skills best-practices]
- Concision matters in SKILL.md even though only metadata is pre-loaded, because once loaded every token competes with the conversation. [skills best-practices]
- Test with every model that will run the skill: Haiku (enough guidance?), Sonnet (clear and efficient?), Opus (over-explaining?). Tightening that suits Opus can starve Haiku; the project's `sdd-mechanic` agent runs on Haiku, so tightened mechanic-facing content needs the weakest-model check. [skills best-practices]
- Iterate with two instances: Claude A edits the skill, Claude B runs it on real tasks; fix based on observed behaviour. Stronger or more prominent wording ("MUST") is a fix for a rule that was ignored. [skills best-practices]
- Anthropic notes Claude handles skill format natively, with no need for a "writing skills" skill. The project's `writing-for-agents` goes beyond this (see section 5).

## 3. Safe large prose-tightening pass

Anthropic and the project's guidance combine into this practice (items marked "inference" are my synthesis, not a published rule):

1. **Baseline first.** Anthropic's evaluation-driven development: write evals (at least three per skill) and measure before changing. Here, record word/line counts per file and a pre-edit git tag or commit. Counting is cheap and objective (inference). Total target: ~135k words across ~170 files.
2. **Behaviour evals via `claude plugin eval`.** [plugin-evals] Requires Claude Code 2.1.269+ and git 2.31+. A suite lives in `evals/` inside the plugin; each case is a directory with `prompt.md` and `graders/`. It runs each case 3 times by default, with the plugin and without it (no-plugin baseline), and scores the delta. Graders: `regex`, `tool_used`, `tool_order`, `file_exists` (free, deterministic) and `llm`, `baseline` (judge model, cost money). `--threshold` defaults to 1.0; it can gate CI. Use `claude plugin eval init` to scaffold. Common first finding: a near-zero delta with the `tool_used: Skill` grader failing means the description does not trigger the skill. That makes it a direct test of description tightening. Limits: it targets plugins with a skill-firing prompt, so a project-level `.claude/` skill or an SDD slash command whose behaviour is a long multi-agent workflow is hard to cover. Every run costs real model calls, so prefer deterministic graders. Run before and after tightening and compare scores (inference).
3. **Per-file review, not bulk rewrite.** Tighten one file at a time with a diff review, keeping each commit small so a regression is bisectable (inference). The project's own tests for deleting a sentence: does it change behaviour versus the default (no-op test); is the meaning stated elsewhere (single source of truth); can the environment answer it (cache test).
4. **Preserve load-bearing content.** Keep unwritten conventions, reasons, gotchas, hard guardrails, and exact strings that other files or tools match on (frontmatter keys, `status:` footers, `mode: hook`, `${CLAUDE_PLUGIN_ROOT}`, file paths, command names, step order, completion criteria). Rewrite negations as positives, keeping the target behaviour. Never delete TODO or `@claude` comments (CLAUDE.md rule).
5. **Do not shorten descriptions blindly.** They are the trigger. Front-load the leading word, one trigger per branch, drop identity the body carries, but check by eval that the skill still fires.
6. **Mechanical checks after each batch.** `claude plugin validate --strict`; grep that no link or path broke; confirm every cross-referenced skill name still resolves.
7. **Do not drop steps' completion criteria.** Vague bounds invite premature completion; tightening must not blur them.
8. **Sequence the two tasks.** Move skills first (pure relocation, validate), commit; then tighten in place. Mixing them makes regressions unattributable (inference).

## 4. Renaming or moving skill identifiers without breaking callers

- Anthropic documents prefixing on move but no alias or redirect mechanism. Treat the rename as a breaking change that needs a grep-and-fix sweep. (I found no published alias feature; the absence is stated from the pages read, not proven.)
- Sweep for every reference form: slash invocations, `Skill` tool calls with `args`, `skills:` agent frontmatter preloads, prose "use the X skill", README and docs, `settings` permission allow-lists (`Skill(name)`), and `allowed-tools`. A raw grep for the five skill names returns 889 hits in 301 files, mostly planning docs and the common word "notifications", so the sweep must target invocation forms, not bare words.
- Cross-plugin call rule in this repo's `claude-code-authoring`: a hook from another plugin is invoked with the `Skill` tool, never by reading its path, because `${CLAUDE_PLUGIN_ROOT}` would resolve to the caller's plugin. Skills moved to a different plugin than their callers (e.g. `sdd` calling `writing-for-agents` now in `productivity`) must follow this, and any file-path pointer into `.claude/skills/...` breaks.
- Dependency direction: the project rule says `ds` and `sdd` stay generic, with no FLS content. `sdd/resources/writing_standard.md` and `sdd/commands/spec_from_idea.md` already mention these skills; after the move they depend on the `productivity` plugin being enabled, so state that dependency (plugins have a dependencies feature, `plugins/dependencies`, not read in depth).
- Keep names stable where possible. Keep skill directory names identical on move so only the prefix changes. Pick the new plugin names once; later renames repeat the problem.
- Verify with `claude --plugin-dir` for each new plugin, test the new name, then delete the originals from `.claude/skills/` (the single leftover is `brand-guidelines`). Per Anthropic, do not leave duplicates.
- Version: set `version` in `plugin.json` deliberately; setting it pins users until you bump it. [plugins/create]

## 5. Where the project's own guidance agrees with or goes beyond external practice

Read: `.claude/skills/writing-for-agents/SKILL.md`, `SKILL-MECHANICS.md`, `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`.

Agrees with Anthropic:
- Progressive disclosure, with the pointer idea sharpening it. Anthropic: "SKILL.md is a table of contents." Project: disclosed reference reached by a context pointer.
- Descriptions as triggers (Anthropic's "what and when"; project's "branches" and "one trigger per branch").
- Cut what the model already knows (Anthropic's "Claude is already very smart"; project's no-op test).
- Single source of truth and consistent terminology.
- Clear completion and validation loops (Anthropic's feedback loops and checklists; project's completion criteria).
- Sprawl, i.e. too long (Anthropic's 500-line limit).

Goes beyond or differs:
- **Two loads framing** (context load vs cognitive load) and the choice of `disable-model-invocation: true` for hand-invoked skills. Anthropic only mentions context cost; the project turns it into a rule: pay context load only if the agent or another skill must reach the skill. Directly relevant to the move: `answer`, `unslop` may be user-invoked.
- **Router skill** for many user-invoked skills (not in Anthropic docs).
- **Leading words** (compact pretrained concepts) as a compression lever, and **negation** as an anti-pattern (prompt the positive). Anthropic's guide does not cover either.
- **Environment as source of truth / cache** test: do not restate what config or `--help` shows.
- **Sediment** and relevance (staleness) pruning; **no-ops** judged by running the document, not by debate.
- **Splitting by sequence** to prevent premature completion (hide post-completion steps across a context boundary).
- **Co-location** within a file.
- **Possible tension:** Anthropic recommends a checklist plus explicit step lists and stronger wording ("MUST") for ignored rules; the project warns that prohibitions and emphasis can backfire and prefers a stronger leading word. Resolve case by case with evals.
- **Anthropic suggests testing across Haiku, Sonnet and Opus**; the project's `claude-code-authoring` tiers Haiku for mechanical chores, Sonnet for fan-out workers. The no-op test is "model-relative", so the weakest model that consumes a file sets its floor.
- `claude-code-authoring` is the project's source of truth for Claude Code behaviour (subagents cannot nest or ask the user, inline commands keep the caller's model so `model:` frontmatter is inert, file-based `status:` footer hand-off). Tightening must not strip these constraint statements or their `resources/` citations; they are the "reasons and gotchas" the cache test says to keep.

Remark on the idea's wording: "the only skill remaining in `.claude/skills` is brand-guidelines" matches the current glob (answer, brand-guidelines, unslop, code-comments, domain-glossary, notifications, writing-for-agents).

## 6. Recommendations for the spec

1. Treat the move as a rename event with a sweep; use final prefixed names everywhere and validate each plugin with `claude plugin validate --strict` and `--plugin-dir`.
2. Decide per moved skill whether it is model-invoked or user-invoked (context load vs cognitive load); for `productivity` skills, consider `disable-model-invocation: true` where only the human fires them.
3. State plugin dependency/enablement for generic plugins that reference `productivity` skills, keeping them generic (no FLS names).
4. For the tightening pass: record counts, add a small `evals/` set (deterministic graders, description-fires cases first) per plugin, run before and after, tighten per file in small commits, review diffs for load-bearing strings.
5. Run the tightened Haiku-facing content (e.g. `sdd-mechanic` inputs) against Haiku.
6. Keep SKILL.md under 500 lines and references one level deep; add contents lists to reference files over 100 lines.

## References

- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- https://code.claude.com/docs/en/plugins (overview)
- https://code.claude.com/docs/en/plugins/create.md
- https://code.claude.com/docs/en/plugin-evals.md
- Project: `.claude/skills/writing-for-agents/SKILL.md`, `.claude/skills/writing-for-agents/SKILL-MECHANICS.md`, `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`

status: ok · reason: complete
