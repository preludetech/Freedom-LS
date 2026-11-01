# Codebase research: claude-plugin-tidy-up

Paths are relative to the repo root. Word counts were not measurable (no shell); sizes are line counts from `rg ^`, blank lines included.

## 1. References to the moving skills

Skills now in `.claude/skills/`: `answer`, `brand-guidelines` (+`visual.md`, `voice.md`), `code-comments`, `domain-glossary`, `notifications`, `unslop`, `writing-for-agents` (+`SKILL-MECHANICS.md`). No other project skills exist. There is no `.claude/agents/` or `.claude/commands/`.

### Live references that must change

| Where | Line | Text | New form |
| --- | --- | --- | --- |
| `.claude/sdd/config.md` | 28 | `Comment standard: .claude/skills/code-comments/SKILL.md` | `claude_plugins/django-stack/skills/code-comments/SKILL.md` (a path, because review workers read files and cannot load skills by name; see `sdd/commands/implement_plan.md:52`) |
| `.claude/sdd/config.md` | 48 | `Vocabulary Sources: .claude/skills/domain-glossary/SKILL.md` | `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` |
| `claude_plugins/fls-dev/commands/init.md` | 327-330 (Step 8b) | sets a blank `Comment standard` to `.claude/skills/code-comments/SKILL.md` "only when that file exists in the project", else lists an outstanding action | Point at `<PLUGINS_ROOT>/claude_plugins/django-stack/skills/code-comments/SKILL.md` (same prefix rule as the other Step 8b keys). The "only when the file exists" guard and the outstanding action become unnecessary. |
| `claude_plugins/fls-dev/commands/init.md` | 358-359, 377 | Step 9 checks | No change needed unless init also manages the productivity plugin. |
| `claude_plugins/sdd/resources/writing_standard.md` | 50 | `Invoke the \`unslop\` skill over the file.` | `productivity:unslop`. This is a generic plugin naming another plugin's skill. |
| `claude_plugins/sdd/commands/spec_from_idea.md` | 132 | `...then \`unslop\` and a re-read.` | `productivity:unslop` |
| `claude_plugins/fls-dev/agents/qa-bugfixer.md` | 217 | `Follow the \`code-comments\` skill.` (the agent's `skills:` preload list at lines 8-12 names only testing skills) | `ds:code-comments` |
| `.claude/skills/brand-guidelines/voice.md` | 37 | `Skill(domain-glossary)` | `Skill(fls-dev:domain-glossary)` |
| `.claude/skills/domain-glossary/SKILL.md` | 227 | path to `.claude/skills/brand-guidelines/voice.md` | still valid (brand-guidelines stays). The file moves, so its own path-style cross-references stay correct. |
| `docs/how tos/landing-pages.md` | 194 | `the \`domain-glossary\` skill` | `fls-dev:domain-glossary` |
| `freedom_ls/audit_log/README.md` | 106 | `(\`.claude/skills/domain-glossary/SKILL.md\`,` | `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` |
| `claude_plugins/sdd/scripts/upstream_change_scan.sh` | 157 | `path == .claude/skills/*` marks a changed file as a "convention" | The glob `*/skills/*` already covers plugin skills. `.claude/skills/*` stays correct for `brand-guidelines`. No change. |
| `claude.sh` | 11-16 | five `--plugin-dir` lines (ds, fls-dev, sdd, turn-progress) | add a productivity line |
| `.claude/settings.json` | 43-45, 157-161 | `Skill(ds:*)`, `Skill(fls-dev:*)`, `Skill(sdd:*)`; `enabledPlugins` ds/fls-dev/sdd (turn-progress is in neither) | add `Skill(productivity:*)` and `"productivity": true` |

Nothing in `CLAUDE.md`, `.claude/ds/config.md`, `.claude/fls-dev/config.md`, `.github/workflows/`, `pyproject.toml`, or any `tests/` file names the six skills. `tests/test_update_concrete_projects.py` and `tests/plugin_markdown.py` do not reference them.

### Skill-name references in `spec_dd/`

These use bare names (`domain-glossary`, `notifications`, `unslop`, `code-comments`) in "Skills:" lists or old `.claude/skills/<name>` paths. Most are done or queued specs, which are historical or future inputs, so a rename is optional.

- Queued (`spec_dd/1. next/`): the bare names `domain-glossary` and `notifications` appear in `roadmap.md` (131, 258, 450, 493-494, 639) and in the `idea.md` of about 20 effort directories (deadlines-3/4/5/6/7, user-communication-2/6/8, corporate-job-course-recommendations-4/5, educator-interface-12 and others). They would need `fls-dev:` prefixes to stay accurate.
- Old paths: `spec_dd/1. next/user-communication/design_brief.md:32` (brand-guidelines, stays valid), `research_notification_sources_and_delivery.md:13`, `deadlines/research_deadline_integration_points.md:7,121`, `deadlines/research_current_deadlines.md:95-96`. `spec_dd/0. noop/landing-pages/*` and `spec_dd/3. done/*` are archives.
- In progress: `spec_dd/2. in progress/learner-facing-ux-refinements/2. plan.md:18` and `research_codebase.md:61`; `test-organisation-and-hygene-2-sdd-review-and-boy-scout/research_agent_skill_preload.md:91` and `research_flagged_bug_reporting.md:93-95,218`.

## 2. How plugins are registered and loaded

- **Manifest.** `claude_plugins/<dir>/.claude-plugin/plugin.json` with `name`, `version`, `description`. `ds` is the only plugin whose directory (`django-stack`) differs from its manifest name; the manifest name drives the `ds:` skill prefix and `enabledPlugins` key. `turn-progress` adds a `types` field. There is no top-level marketplace manifest and no `.claude-plugin/` at the repo root.
- **Launcher.** `claude.sh` (generated by `/ds:init` from `claude_plugins/django-stack/templates/wrapper_scripts/claude.sh`) sets `CLAUDE_PLUGINS_LOADED=1` and passes one `--plugin-dir "$SCRIPT_DIR/$PLUGINS_ROOT/claude_plugins/<dir>"` per plugin. A `SessionStart` hook in `.claude/settings.json` (line 184-193) stops the session if `CLAUDE_PLUGINS_LOADED` is unset. `fls-content` is not in `claude.sh`.
- **Each plugin's init adds its own line.** `ds` (`django-stack/commands/init.md`), `sdd` (`sdd/commands/init.md` Step 4, lines 245-250), `fls-dev` (`fls-dev/commands/init.md` Step 7, lines 296-303) each follow `resources/launcher_editing.md`. That file is duplicated verbatim (123 lines) into `django-stack/resources`, `sdd/resources` and `fls-dev/resources`, with a one-row table naming `<PLUGIN_DIR_NAME>`, because `${CLAUDE_PLUGIN_ROOT}` is per-plugin. A `productivity` init would need a fourth copy.
- **Preflight rules.** `sdd/commands/init.md` P1/P3b stop unless `claude.sh` exists and every `--plugin-dir` path contains `/claude_plugins/`. `fls-dev/commands/init.md` P3 requires `"ds": true`.
- **Discovery rule that decides if a new plugin gets flagged.** `django-stack/commands/init.md:299-313` tells the user to run `/<name>:init` for every plugin under `claude_plugins/` that lacks a `--plugin-dir` line, but only for plugins that ship `commands/init.md` mentioning `--plugin-dir`. A `productivity` plugin with no init is skipped silently, so someone must edit `claude.sh` by hand (as with `turn-progress`, whose README line 60 says `claude.sh` passes it). A plugin with an init mentioning `--plugin-dir` gets the prompt automatically.
- **Settings.** `.claude/settings.json` per plugin: `Skill(<name>:*)` allow, `enabledPlugins`. `ds` owns `claude_plugins/django-stack/templates/settings.json` (line 7 holds `Skill(ds:*)`). `sdd`'s init adds its own `Skill(sdd:*)` and key (`sdd/commands/init.md:36,106,257`). `fls-dev` does the same (init.md 133-136).
- **READMEs.** Each plugin has a README with manifest name, namespace line (`Skill(<name>:*)`) and a "counted from disk" inventory that will go stale: `django-stack/README.md:36-38` (9 skills -> 10), `fls-dev/README.md:18-25` (13 skills -> 15, plus its list of FLS-specific skills), `sdd/README.md:51` (unaffected). `fls-dev/README.md:20-25` is where the new skills should be named.
- **Prefix changes.** `unslop` -> `productivity:unslop`, `writing-for-agents` -> `productivity:writing-for-agents`, `answer` -> `productivity:answer` (it is `disable-model-invocation: true` with `argument-hint`, so users type `/productivity:answer <question>` instead of `/answer`), `code-comments` -> `ds:code-comments`, `domain-glossary` -> `fls-dev:domain-glossary`, `notifications` -> `fls-dev:notifications`. Callers are the table in section 1. The `CLAUDE.md` rule "Use skills whenever possible" names none of them. The user-level plugin instruction is not in scope.
- **Genericity of dependencies.** `ds` README says it "depends on no other plugin". `sdd` is "independent". `fls-dev` README line 13 documents its runtime dependency on `sdd`. Naming `productivity:unslop` from `sdd` is a new plugin-to-plugin dependency. The idea does not say whether that is allowed.

## 3. fls-dev overlay pattern

An overlay is a thin skill in `claude_plugins/fls-dev/skills/<x>/SKILL.md` that says "Read `Skill(ds:<x>)` first ... This overlay adds **only** the FreedomLS ...". Seen in `template`, `testing`, `app-settings`, `admin-interface`, `alpine-js`, `frontend-styling`, `playwright-tests`, `use-playwright`; `git-worktree-setup` overlays `sdd:`.

- Description form: `FreedomLS-specific extension of the ds:<x> skill. Adds ... Use alongside ds:<x> when ...` (`fls-dev/skills/template/SKILL.md:3`); `allowed-tools: Read, Grep, Glob`.
- Detail lives in a `fls-dev/resources/<x>.md` addendum that opens "This addendum extends the generic `ds` `<x>.md` resource ... Read the `ds` resource first" (testing, templates_and_cotton, factory_boy, admin_interface, playwright-testing, frontend_styling).
- If `ds:code-comments` needs an FLS layer, the shape is `fls-dev/skills/code-comments/SKILL.md` plus optionally `resources/code_comments.md`. The sdd `Comment standard` hook takes one file path, so it could point at the overlay, which tells the worker to read the ds file first. Whether an overlay is needed depends on what FLS-specific content survives; section 4 finds almost none.

## 4. Project-specific content inside the moving skills

### `code-comments` (-> `ds`; must be generic)

- `.claude/skills/code-comments/SKILL.md:3` (description): "in the FreedomLS codebase", "spec_dd/ paths".
- Line 6-13 body is generic. Line 23 "most common rot in this codebase" is project-flavoured but not a name.
- Line 31: row "Paths into the spec tree" with `spec_dd/2. in progress/schools/3. frontend_qa.md` is a project path (`spec_dd/` is `sdd`'s convention, `schools` an FLS effort).
- Lines 28, 47-58, 86-90, 119-120, 140, 153-158: examples use FLS domain (educator interface panel actions, `REGISTRATION_CHANGED`/`EDUCATOR_CHANGED`, toasts, runner `Cache-Control`, `form_submit_and_exit`, save-on-exit forms, quiz percentage, category scores, "coming-soon course"). These need neutral replacements.
- Line 73 mentions a "coming-soon course launch notification" (FLS feature).
- Lines 164-178 cite `CLAUDE.md` ("never delete TODO or @claude comments"), which is a project rule, not a ds rule. A generic form says "a project rule that protects TODO or @claude comments"; the FLS wording could move to an overlay. Needs a decision.
- The concept "planning documents (spec, plan, research, QA plan/report)" is `sdd` vocabulary, but `ds` may describe it without naming `sdd` or `spec_dd/`. `sdd/resources/plan_review_dimensions.md:17` (`comments` dimension) already states the same rule generically.
- `{% comment %}` / Tailwind lines (123-127) are Django/Tailwind and fit `ds`'s declared stack.

### `domain-glossary`, `notifications` (-> `fls-dev`; FLS content is expected)

- `domain-glossary/SKILL.md` is 264 lines, wholly FLS (`freedom_ls/...` paths at lines 21, 34, 55, 66-68, 73-74, 105, 131, 141, 160, 170-175, 256-264). Line 227 points at `.claude/skills/brand-guidelines/voice.md`, which stays.
- `notifications/SKILL.md:3` "When FreedomLS should...", line 46 "Examples in FLS". It uses `raise_notification`, FLS categories. Lines 92-96 are web links.
- Both belong in `fls-dev`. Their descriptions have no prefix issue.

### `unslop`, `answer`, `writing-for-agents` (-> `productivity`; must be generic)

- No `FreedomLS`, `FLS`, `freedom_ls`, `spec_dd` or `.claude/` string found by grep in any of the three.
- `writing-for-agents/SKILL.md:6,8` mention `CLAUDE.md` (generic Claude Code concept). `SKILL-MECHANICS.md` (22 lines) is a sibling reference.
- `unslop/SKILL.md` line 76 and 72 use generic software examples (`.toSQL()`, database). Line 50 "Avoid em dashes entirely" is a style choice. A British/American spelling stance is not set.
- `answer/SKILL.md:16-20` names Edit/Write/NotebookEdit, git, migrations; generic enough.
- **Dependency risk.** `writing-for-agents` and `unslop` are the instruments for part 2. `sdd/skills/claude-code-authoring` does not reference `writing-for-agents`.

## 5. Tests and validation over plugin content

- `tests/test_update_concrete_projects.py` (about 290 lines) asserts literal strings in `claude_plugins/fls-dev/commands/update_concrete_projects.md` (lines 149-151, 194-196, 213-215, 259, 263-265, 278-289, e.g. `Skill(sdd:roadmap)` appears in "## End of run" but not under "**Large fix.**" or "## Pull-in scan"; section headings such as "## Step 3: Preview and confirm", "**Size test.**"), `do_qa.md` (project-root inputs section, no `cd`, lines 218-240), `concrete/update_fls.md`, `resources/concrete_spec_integration.md`, `templates/config.local.md`, and `.claude/settings.json` allow/deny entries (lines 96-97, 105-113, 165-167, 252). It also reads `.claude/settings.json` for the fls-dev script entries. **Tightening those four files must keep every asserted heading, literal and code fragment.** `tests/plugin_markdown.py` supplies `code_fragments()` and a `uv run pytest` invocation regexp used on them.
- `claude_plugins/fls-content/validate/tests/test_validator.py` tests course-content validation, not plugin docs.
- `claude_plugins/turn-progress/tests/progress.test.ts`; README lines 64-69 give `claude plugin validate` / `claude plugin test`. A new `productivity` plugin can run `claude plugin validate` too.
- CI (`.github/workflows/tests.yml:26,28`) runs `generate_app_map.py --check` and `check_test_mirroring.py` from `django-stack/scripts`. These do not read skills.
- No link checker, frontmatter check or skill-name registry exists. Nothing in CI checks that skill references resolve, so stale references are caught only by review.

## 6. Size inventory (Claude-facing markdown)

Totals by plugin (lines of `.md`): `claude_plugins/django-stack` 4455 (36 files), `sdd` 3613 (40), `fls-dev` 4616 (46), `fls-content` 2821 (35), `turn-progress` 69 (1). Plugin total 15,574 over 158 files. `.claude/skills/` 1005 over 10 files (answer 31, notifications 96, brand-guidelines 29+121+90, domain-glossary 264, code-comments 191, unslop 80, writing-for-agents 81+22).

By directory type across `claude_plugins/`: skills (including `fls-content` widget resources) 4531 lines / 62 files; commands 5821 / 44; plugin-level `resources/` 4136 / 38; agents 689 / 6; the rest (READMEs, templates) about 397. About 15,000 words is a guess at roughly 10 words per line; count it properly when work starts. `fls-content` is a course-author plugin: its skills, command and agent are Claude-facing, but written for course authors working in a separate project. Whether it is in scope for part 2 is not said by the idea. It is 18% of the lines (and the largest single file `fls-content/.../course-files.md` is there).

Top 20 largest files by line count:

1. `fls-dev/commands/do_qa.md` 715
2. `django-stack/resources/testing.md` 640
3. `fls-content/skills/content-types/resources/course-files.md` 525
4. `fls-dev/commands/update_concrete_projects.md` 407
5. `fls-dev/commands/init.md` 391
6. `fls-content/skills/content-types/resources/form-files.md` 316
7. `django-stack/commands/init.md` 314
8. `sdd/commands/init.md` 289
9. `sdd/commands/roadmap.md` 276
10. `django-stack/resources/alpine_csp_build.md` 272
11. `.claude/skills/domain-glossary/SKILL.md` 264
12. `django-stack/commands/rebase_main.md` 260
13. `fls-dev/skills/registration/SKILL.md` 235
14. `django-stack/skills/htmx/SKILL.md` 221
15. `fls-dev/agents/qa-bugfixer.md` 217
16. `django-stack/resources/alpine_no_csp.md` 211
17. `fls-dev/commands/update_product_docs.md` 211
18. `sdd/commands/register_design.md` 201
19. `django-stack/resources/factory_boy.md` 199
20. `django-stack/resources/templates_and_cotton.md` 192

(Next: `fls-dev/resources/email_templates.md` 191, `.claude/skills/code-comments/SKILL.md` 191, `django-stack/commands/pre_step_rebase`/`sdd` 182, `django-stack/agents/code-reviewer.md` 180.)

Duplicated files are exact line-count matches that the READMEs call deliberate copies: `launcher_editing.md` 123 lines in ds/sdd/fls-dev; `wrapper_script_migration.md` 156 in ds/fls-dev; `agent_memory_guidelines.md` 34 in ds/sdd/fls-dev. Tightening one means tightening the copies, and a productivity init adds a launcher_editing copy.

Scripts, `.json`, `.sh`, `.py`, `.ts`, templates and `.claude/agent-memory/` (about 90 memory notes for `ds-code-reviewer` and `fls-dev-qa-data-helper`) are not skill, command, resource or agent content; the idea does not mention agent memory.

## 7. Review rules that would judge this work

- `claude_plugins/sdd/resources/spec_review_dimensions.md`, row `generic_plugin` (line 20): "no project name, path, app or value in a plugin whose README says it is generic". Also `vocabulary` (line 19) against `## Vocabulary Sources` and `completeness`, `feasibility`, `cut_list`. The same check is a row in `claude_plugins/sdd/resources/plan_review_dimensions.md:14`, with `skills`, `comments` (line 17) and `vocabulary`.
- `claude_plugins/fls-dev/resources/plan_review_structure.md` (32 lines) checks cross-app import edges against `docs/app_structure.md`. It judges Django apps and has nothing to say about plugins.
- `fls-dev/resources/plan_review_fls_threats.md` (29 lines) is the FLS threat brief.
- `sdd/resources/writing_standard.md` (54 lines): the writing rules for SDD artifacts. It ends with an `unslop` pass (line 50), so this spec and plan will be judged by a file this work edits.
- Project rule in `CLAUDE.md` ("Plugins"): ds and sdd stay generic; FLS content goes in fls-dev. It names `ds` and `sdd` only, so `productivity` falls under the same genericity rule by analogy. That is an inference. State it in the spec.
- `.claude/sdd/config.md` `## Plan Review Hooks` (lines 21-24) wire `plan_review_structure.md` and `plan_review_fls_threats.md`.

## 8. Conflicts and open points for the spec

- `sdd` naming `productivity:unslop` makes `sdd` depend on a sibling plugin that the project may not load. The alternative is to leave the call in sdd as plain `unslop` text. The spec needs to pick.
- `answer` changes its slash command from `/answer` to `/productivity:answer`.
- The `Comment standard` and `Vocabulary Sources` hooks stay as file paths; they must be updated in `.claude/sdd/config.md` and in `fls-dev/commands/init.md` Step 8b together, or `/fls-dev:init` on a fresh project will leave the comment hook blank with an outstanding action.
- Part 2 edits `sdd/commands/*`, `fls-dev/commands/update_concrete_projects.md`, `do_qa.md` and other files with string-asserting tests (section 5).
- `.claude/agent-memory/**` and `spec_dd/**` were excluded from "Claude-facing content" in this survey; neither is named in the idea.

status: ok · reason: complete
