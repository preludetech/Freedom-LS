# Research: UX patterns for moving skills into plugins and tightening Claude-facing markdown

Users: developers running Claude Code in this repo, and downstream projects that install `ds`, `sdd` and the new `productivity` plugin. Sources are repo files plus Claude Code behaviour known from its docs; the docs were not re-fetched this run, so verify the namespacing and frontmatter points below before they go into a spec.

Doc references to verify:
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins
- https://code.claude.com/docs/en/plugin-marketplaces

## 1. Repo facts that shape the UX

- `.claude/skills/` holds 7 skills: answer, brand-guidelines, code-comments, domain-glossary, notifications, unslop, writing-for-agents. They are unnamespaced today (`/answer`, `Skill(domain-glossary)`).
- `claude.sh` (repo root) is the opt-in mechanism. It has one `--plugin-dir "$SCRIPT_DIR/$PLUGINS_ROOT/claude_plugins/<name>"` line per plugin (currently django-stack, fls-dev, sdd, turn-progress). `fls-content` has an init but no launcher line here.
- Each plugin has `commands/init.md`. The sdd init shows the contract:
  - It runs a Step 0 preflight that writes nothing.
  - It merges only its own `enabledPlugins` key and its own `Skill(sdd:*)` allow entry.
  - It adds only its own `--plugin-dir` line, following `resources/launcher_editing.md`.
  - It uses a shared `PLUGINS_ROOT` rule and never prompts.
- Plugin READMEs exist for django-stack, fls-content, fls-dev, sdd and turn-progress. The turn-progress README is the model: what it shows, how it works, limits, "Loading it", "Checking it". `productivity` needs one.
- `answer` sets `disable-model-invocation: true` and `argument-hint: <question>`. `unslop` says "Must always apply", and `writing-for-agents` is "Use when creating or editing skills, or modifying CLAUDE.md". These are model-triggered by description.
- Hard-coded references to the old names and locations, each of which breaks or changes on a move:
  - `.claude/sdd/config.md:28` sets `Comment standard: .claude/skills/code-comments/SKILL.md`.
  - `.claude/sdd/config.md:48` lists `.claude/skills/domain-glossary/SKILL.md` under Vocabulary Sources.
  - `claude_plugins/fls-dev/commands/init.md:328` sets `Comment standard` to the code-comments path "only when that file exists".
  - `claude_plugins/fls-dev/agents/qa-bugfixer.md:217` says "Follow the `code-comments` skill".
  - `claude_plugins/sdd/resources/writing_standard.md:50` and `commands/spec_from_idea.md:132` invoke `unslop` by bare name.
  - `.claude/skills/brand-guidelines/voice.md:37` points at `Skill(domain-glossary)`.

## 2. Patterns

### 2.1 Namespaced names in the `/` menu
- Plugin skills appear as `/plugin:skill` (for example `/productivity:answer`). Project skills in `.claude/skills/` are unprefixed (`/answer`). Moving `answer` into `productivity` therefore changes the command the developer types from `/answer` to `/productivity:answer`. This is the largest visible regression risk.
- Plugin namespace comes from the plugin manifest `name`, not the directory. Check that the manifest names match the intended prefix (`ds` is the short form of `django-stack`).
- Mitigation options a spec can choose from:
  - Accept the longer name and document it.
  - Keep a thin alias command in `.claude/commands/answer.md` that forwards to the plugin skill. This costs a stub file.
  - Keep `answer` at project level. The idea says it moves, so this contradicts the idea.
- Autocomplete matches on the name, so `/answer` still finds `/productivity:answer` by typing `answer`. The cost is mostly muscle memory and docs.
- Model-facing references must use the namespaced form once the skill is a plugin skill: `Skill(productivity:unslop)`, not `unslop`. The `Skill(sdd:*)` permission style shows the convention. Without an allow entry for `Skill(productivity:*)`, the skill triggers a permission prompt.

### 2.2 User-invocable vs model-invocable
- Two independent axes:
  - `disable-model-invocation: true` means only the user can run it (via `/`). Claude never auto-loads it, and its description is not put in Claude's context.
  - `user-invocable: false` hides it from the `/` menu. Claude alone loads it by description.
- Fit to the six moved or kept skills:
  - `answer`: user-only. Keep `disable-model-invocation: true` and `argument-hint`. It is an explicit mode switch ("do nothing else") and must not self-trigger.
  - `unslop`, `writing-for-agents`, `code-comments`, `domain-glossary`, `notifications`: model-triggered by description. Also being in the `/` menu is harmless and useful for manual use.
- Frontmatter must survive the move unchanged. Check each moved skill's frontmatter for `disable-model-invocation`. A move that drops it would silently make `answer` auto-invocable.
- Because every model-invocable description is always in context, tightening descriptions (section 2.5) reduces constant context cost. Descriptions of user-only skills cost nothing.

### 2.3 Opting a plugin in
- This repo's pattern is the launcher: `./claude.sh` passes one `--plugin-dir` per plugin. A session started without it has no plugins; the turn-progress README says to add the flag by hand.
- For `productivity` the repo-local change set is:
  - a `--plugin-dir` line in `claude.sh`;
  - `"productivity": true` under `enabledPlugins` and `Skill(productivity:*)` under `permissions.allow` in `.claude/settings.json`;
  - an `init` command written to the same contract as sdd's (preflight first, merge-only, own lines only, no prompting).
- Simplest UX: a minimal `productivity:init` in the same shape as `sdd:init`, but with no config dir (the plugin has no per-project settings). Reusing the shared `PLUGINS_ROOT` rule text keeps the "edit all copies together" invariant; adding a plugin adds one more copy to keep in sync.
- Marketplace is the alternative for downstream projects that do not vendor `claude_plugins/`: `/plugin marketplace add <repo>` then `/plugin install productivity@<marketplace>`. A `.claude-plugin/marketplace.json` at the repo root listing all generic plugins would make adoption a two-command flow. Check whether one exists; this run did not. This is outside the idea's scope, so note it as an optional follow-up.
- `claude plugin validate <dir>` (used in the turn-progress README) is a cheap acceptance check for the new plugin's manifest and skill frontmatter.

### 2.4 Discoverability
- Plugin `description` in the manifest is what `/plugin` lists; write it as one scannable line saying what the plugin is for, for example "Writing and answering helpers: answer, unslop, writing-for-agents".
- README per plugin, in the turn-progress shape: one-line purpose, what is in it (a table of skill, how it is invoked, user-only vs model-triggered), loading it, checking it. A skill table gives the user-only vs model-invocable answer in one glance.
- Skills moved out of `.claude/skills/` vanish from the project's own listing. The root `CLAUDE.md` Plugins section and each plugin README are where a developer learns where they went. A one-line pointer for each moved skill (old path to new `plugin:skill`) in the destination plugin README helps.
- The `generic stays generic` rule applies. `productivity` must name no FLS value. `domain-glossary` and `notifications` go to `fls-dev` for this reason; `code-comments` goes to `ds`, so check it for FLS-specific content before the move.

### 2.5 Migration notes for downstream projects
Skill moves are a breaking change for any project that references the old name or path. Patterns:
- Changelog or migration note listing, for each skill: old invocation to new invocation, and old path to new path. Include only what changed:

  | Skill | Was | Now |
  |---|---|---|
  | answer | `/answer` | `/productivity:answer` |
  | code-comments | `Skill(code-comments)`, `.claude/skills/code-comments/SKILL.md` | `Skill(ds:code-comments)`, path inside `claude_plugins/django-stack/` |

- Config pointers are the quiet breakage. `.claude/sdd/config.md` keys hold file paths (`Comment standard`, Vocabulary Sources). A path to a file that no longer exists makes the sdd helpers silently skip that review half or fail. Options: update the paths in this repo's config, and tell downstream projects to re-point theirs. Check whether sdd's helper reports a missing target; if not, a spec may want that reported.
- The fls-dev init currently sets `Comment standard` only "when that file exists" at the old path. After the move it should point at the plugin file, using `${CLAUDE_PLUGIN_ROOT}`-style resolution or a stable relative path. Decide which, since the plugin path depends on `PLUGINS_ROOT`.
- Re-running `init` should be the migration path: idempotent, merge-only, and it adds `Skill(productivity:*)` and the launcher line. Existing inits already guarantee this shape.
- Reject a long-lived deprecation shim by default (the repo style is no unrequested functionality). If a stub is wanted for `/answer`, make it explicit and time-boxed.
- Search all Claude-facing files for the old names after the move (grep list in section 1); also CLAUDE.md, `.claude/settings.json` allow lists, hooks and agent files.

### 2.6 Readability of the content (Task 2: tightening)
Patterns drawn from this repo's own `writing-for-agents` skill and from skill-authoring practice:
- Front-load the trigger. The description is the router: start with what the skill is, then "Use when ...". The `notifications` and `domain-glossary` descriptions are good models of the trigger list, but are long (about 60 words); cut examples before cutting triggers.
- One-line summary, then rules. A skill body opens with the decision or rule, not background.
- Scannable structure: short headings, lists and tables for parallel items, prose only for reasoning. Put the must/never rules where an agent sees them first.
- Progressive disclosure: keep `SKILL.md` small and move detail to sibling files (as `writing-for-agents` does with `SKILL-MECHANICS.md` and `brand-guidelines` does with `voice.md`). Link, do not paste.
- Cut: restated rules, motivational prose, hedges, examples that repeat a rule already shown, history. Keep: the rule, the one example that disambiguates, the reason when an agent could otherwise "fix" the rule away.
- Put the "why" with the rule in one clause. Rules with no reason get rationalised away; reasons with no rule get ignored.
- Keep exact strings that other files depend on: section and key names in `config.md` ("the reader helpers locate the values by the section and key names"), headings that commands cite, filenames, and skill names. Tightening must not rename these.
- Behaviour-preservation check: tighten, then diff for lost rules, not lost words. Have a reviewer compare the rule lists before and after. Avoid tightening and restructuring in the same pass.
- Large files such as `sdd/commands/init.md` (about 290 lines) are the best targets. Repeated blocks, for example the `PLUGINS_ROOT` rule copied across inits, are deliberately duplicated ("Edit all copies together"); change them identically everywhere or not at all.
- Apply `unslop` as a final pass, as `writing_standard.md` step 50 already prescribes.

## 3. Recommendations for the spec
1. Decide and state the invocation form for every moved skill (`/productivity:answer` etc.) and update every model-facing reference to the namespaced name.
2. Keep `disable-model-invocation: true` and `argument-hint` on `answer`; add an acceptance check that frontmatter is unchanged by the move.
3. Give `productivity` the full opt-in kit: manifest with a one-line description, README with a skill table, `init` command following the sdd contract, `claude.sh` line, `Skill(productivity:*)` permission.
4. Add a migration table (old name/path to new) in the PR/changelog, and re-point `.claude/sdd/config.md` keys and the fls-dev init `Comment standard` logic.
5. Make a grep-for-old-names step part of acceptance, using the list in section 1.
6. For tightening, require: descriptions front-loaded, SKILL.md small, exact-string dependencies preserved, and a rules-before/after comparison.
7. Optional follow-ups (not in the idea): marketplace manifest, a deprecation stub for `/answer`.

## 4. Open questions
- Does a marketplace manifest already exist for the generic plugins?
- Does sdd report a missing path for `Comment standard` or Vocabulary Sources, or skip silently?
- Does `code-comments` contain FLS-specific content that would break the "ds stays generic" rule?

status: ok · reason: complete; Claude Code docs behaviour not re-fetched, flagged for verification
