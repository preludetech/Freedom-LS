# Research: How tightly is SDD coupled to FLS-specific concerns?

## Scope and method

Read in full: every command under `fls-claude-plugin/commands/sdd/` and `commands/sdd/protected/`,
the SDD `README.md`, both SDD agents (`sdd-worker.md`, `sdd-mechanic.md`), the SDD-adjacent commands
(`app_map.md`, `threat-model.md`, `security-review.md`, `tdd_implement.md`, `address_pr_review.md`,
`concrete/update_fls.md`), plus `qa-data-helper.md` and the `claude-code-authoring` skill (referenced
by nearly every SDD command). Also read the idea file itself
(`spec_dd/2. in progress/split-claude-plugin/idea.md`) and the plugin manifest
(`fls-claude-plugin/.claude-plugin/plugin.json`, `name: "fls"`).

## Dependency catalog

Legend for the last column: **G** = generic SDD scaffolding (stack-agnostic), **DS** = Django-stack-specific
but not FLS-domain-specific, **FLS** = genuinely FLS-domain-specific (only makes sense for *this* product).

| File | `fls:` agent/skill refs | FLS/Django domain assumptions | Hardcoded intra-plugin paths / namespace | Class |
|---|---|---|---|---|
| `commands/sdd/README.md` | `fls:qa-data-helper` (step 6), `fls:sdd-mechanic`/`fls:sdd-worker` (model-tiering section) | Steps 8–9 describe `docs/product/`, `upgrade_notes.md` for "downstream FLS projects", the template repo, and the `fls-content` plugin sync — all FLS-only | `fls-claude-plugin/agents/sdd-mechanic.md`, `sdd-worker.md`; `fls-claude-plugin/commands/sdd/protected/update_todo.md` | Mixed: steps 1–7,10,12 are **G**; steps 8, 8.5, 8.6, 9 are **FLS** |
| `commands/sdd/improve_idea.md` | `fls:sdd-worker` (fan-out recipe) | none | `fls-claude-plugin/commands/sdd/protected/update_todo.md` | **G** |
| `commands/sdd/spec_from_idea.md` | `fls:sdd-worker` | none | same helper path | **G** |
| `commands/sdd/spec_review.md` | none directly | reads `${CLAUDE_PLUGIN_ROOT}/resources/` for "project norms" — generic mechanism, but those resources today are FLS/Django conventions | same helper path | **G** shape / content depends on which plugin's `resources/` it points at |
| `commands/sdd/plan_from_spec.md` | `fls:sdd-worker` (×2: skill/MCP scan, review dims) | Step 5 hardcodes `PORT=$(.claude/fls/scripts/find_available_port.sh)` and `uv run python manage.py runserver $PORT` for the frontend_qa doc it drafts | same helper path | **G** shape, one **DS**-flavored paragraph |
| `commands/sdd/plan_security_review.md` | `fls:sdd-worker`, `fls:sdd-mechanic`, `fls:multi-tenant` skill | Scan spec explicitly cites `SiteAwareModel`, ORM-only rule, HTMX CSRF header, custom user model, multi-tenancy — all FLS/Django conventions baked into the worker's brief | same helper path | Orchestration shape **G**; scan content **FLS** |
| `commands/sdd/plan_structure_review.md` | `fls:sdd-worker`, `fls:sdd-mechanic` | Entire command is meaningless without `docs/app_structure.md`, produced by the Django-specific `/app_map` (walks `apps.py`, `ast` cross-app imports) | same helper path | Orchestration shape **G**; hard dependency on a **DS** artifact |
| `commands/sdd/implement_plan.md` | `fls:sdd-worker` (mentioned only as contrast), `fls:sdd-mechanic` | `uv run pytest`, `uv run git commit` (Python/uv-specific, per project `CLAUDE.md`); `request-code-review` skill | same helper path | **G** shape, **DS**-flavored tool invocations |
| `commands/sdd/do_qa.md` | `fls:qa-data-helper` (hard requirement, not optional), `fls:sdd-worker` (Step 5 ad-hoc probe) | `manage.py runserver`, `debug-branch-badge` template element, `.claude/fls/config.md` admin credentials, `.claude/fls/scripts/find_available_port.sh` / `kill_runserver.sh`, `${CLAUDE_PLUGIN_ROOT}/scripts/qa_cleanup.sh` / `compress_screenshots.py` | same helper path | **FLS** — this command cannot run against a non-Django, non-FLS project as written |
| `commands/sdd/finish_worktree.md` | `fls:sdd-mechanic` (×4) | `.claude/fls/scripts/dev_db_delete.sh` (Django dev-DB teardown) | same helper path | **G** shape, one **FLS**/**DS** line |
| `commands/sdd/next.md` | (indirect — inline-executes files that reference `fls:` agents) | none directly, but its command-resolution search is **hardcoded to two directories, both inside `fls-claude-plugin/commands/`**: `fls-claude-plugin/commands/sdd/{name}.md` and `fls-claude-plugin/commands/{name}.md` | Both candidate roots are literal `fls-claude-plugin/...` paths | **G** intent, **hardcoded single-plugin** implementation |
| `commands/sdd/start.md` | `fls:sdd-mechanic` (×3) | none directly (delegates) | `fls-claude-plugin/commands/sdd/protected/{setup_todo_list,move_spec_to_in_progress,start_worktree}.md` | **G** |
| `commands/sdd/update_claude_plugin_fls_content.md` | `fls:sdd-worker`, `fls:sdd-mechanic` | Entirely about syncing the sibling `fls-content-plugin/` course-author plugin — content schema, cotton templates, widget allowlists, `demo_content/` | same helper path | **FLS** — not a generic SDD step at all |
| `commands/sdd/update_template_repo.md` | `fls:sdd-mechanic` | Entirely about the FLS **template repo** (scaffold for new concrete FLS projects), `.claude/fls/config.local.md`, `fls:init`, `${CLAUDE_PLUGIN_ROOT}/resources/template_repo_manifest.md` | same helper path | **FLS** |
| `commands/sdd/update_product_docs.md` | `fls:sdd-worker`, `fls:qa-data-helper` | `docs/product/` audience/altitude rules are FLS-product-specific; Playwright capture against `manage.py runserver`, DemoDev site, `.claude/fls/config.md`, `.claude/fls/scripts/*` | same helper path | **FLS** |
| `commands/sdd/update_upgrade_notes.md` | `fls:sdd-mechanic` | Schema (`requires_migrations`, `requires_template_review`, etc.) exists purely to serve **downstream FLS projects** consuming FLS as a submodule via `/update_fls` | same helper path | **FLS** |
| `commands/sdd/protected/update_todo.md` | none | none | Referenced **by literal path** from ~13 other files | **G** — fully generic helper |
| `commands/sdd/protected/setup_todo_list.md` | `fls:qa-data-helper` (in the generated checklist text) | The generated `todo.md` template **hardcodes all 15 sections**, including FLS-only sections 10–13 (product docs, upgrade notes, template repo, author-plugin sync) directly in the markdown it writes | self-reference to `fls-claude-plugin/commands/sdd/README.md` | Sections 1–9, 14–15 **G**; sections 10–13 **FLS**, all in one undifferentiated template |
| `commands/sdd/protected/move_spec_to_in_progress.md` | none | `spec_dd/` directory convention (project convention, not stack-specific) | none | **G** |
| `commands/sdd/protected/start_worktree.md` | none | `.claude/fls/scripts/install_dev.sh` (FLS project bootstrap script) | none | **G** shape, one **FLS** line |
| `agents/sdd-worker.md` | (is itself the `fls:sdd-worker` agent) | **none** — fully generic non-interactive fan-out worker contract | none | **G** — zero FLS content |
| `agents/sdd-mechanic.md` | (is itself the `fls:sdd-mechanic` agent) | **none** in body, but names `fls-claude-plugin/commands/sdd/protected/update_todo.md` etc. by literal path | literal paths to protected helpers | **G** — one path-only coupling |
| `agents/qa-data-helper.md` | — | factory_boy, `qa_helpers` app, multi-site `SiteAwareModel`, FLS domain data (cohorts, courses) | `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md` | **FLS** |
| `commands/app_map.md` | none | Django-specific: walks `apps.py`, `ast` cross-app imports; not FLS-domain-specific, would work in any Django multi-app project | `${CLAUDE_PLUGIN_ROOT}/scripts/generate_app_map.py` | **DS** |
| `commands/threat-model.md` | none | Generic OWASP-style prompt, no FLS/Django specifics | none | **G** (stock, minimal) |
| `commands/security-review.md` | none | `bandit`, `pip-audit`, `detect-secrets`, `manage.py check --deploy` — Python/Django tool-specific | none | **DS** |
| `commands/tdd_implement.md` | none directly | References the project's "testing skill" (stack-specific conventions) | none | **DS**-leaning **G** |
| `commands/address_pr_review.md` | none | `.claude/fls/scripts/fetch_pr_comments.sh`; `uv run pytest`, `uv run pre-commit` | one FLS script path | **G** shape, **FLS**/**DS** tool paths |
| `commands/concrete/update_fls.md` | none | Entirely about a **downstream** concrete project consuming FLS as a git submodule, parsing `upgrade_notes.md`, running `makemigrations`/`migrate`, Tailwind rebuilds, npm installs | none | **FLS** — the consumer side of the FLS-specific upgrade-notes contract, not a generic SDD step |
| `skills/claude-code-authoring/*` (referenced pervasively) | — | **None.** This is pure Claude Code mechanics: subagent limits, model tiering, the fan-out recipe, interactive-CLI notes. Not FLS- or Django-specific in any way | — | **G** — arguably the most portable artifact in the whole set |

## Portability analysis: what's actually generic vs. what only makes sense for FLS/Django

**Genuinely generic "SDD scaffolding"** (idea → spec → plan → implement → review → ship, `todo.md`
tracking, worktree setup, the fan-out recipe, the two tiering agents):

- The **fan-out recipe** itself (declare inputs → one file per unit → resume scan → one worker per
  unit → structured returns → synthesis → cleanup) has zero FLS content anywhere it appears.
- `sdd-worker.md` and `sdd-mechanic.md` are **completely clean** — no FLS references in their bodies at
  all (only in *other* files' invocations of them).
- `improve_idea.md`, `spec_from_idea.md`, `spec_review.md` are clean generic authoring steps.
- `next.md`, `start.md`, `update_todo.md`, `move_spec_to_in_progress.md` are generic *in intent*, with
  narrow, mechanical FLS couplings (hardcoded paths, one script call).
- `claude-code-authoring` (the skill nearly every command cites for "why it works this way") is 100%
  portable Claude Code guidance with no FLS content — it just happens to live inside `fls-claude-plugin/`.
- `threat-model.md` is stock and generic.

**Irreducibly FLS/Django-specific** (structure review against `app_map`, product docs, upgrade notes,
template repo, `fls-content` sync, migration/pytest/uv/Playwright-against-Django assumptions):

- `do_qa.md` is not portable as written: it hard-requires `manage.py runserver`, a
  `debug-branch-badge` template element, and the FLS-specific `fls:qa-data-helper` agent (factory_boy,
  multi-site data). A generic QA command would need "start the dev server" and "seed test data" to be
  pluggable abstractions — that's a real design task, not a rename.
- `plan_security_review.md`'s orchestration shape is generic, but its **scan specification** is written
  in terms of `SiteAwareModel`, the ORM-only rule, HTMX CSRF headers, and the custom user model — FLS/Django
  conventions baked directly into the worker's brief, not merely referenced.
- `plan_structure_review.md` is structurally sound as a generic pattern ("diff a plan against an approved
  architecture diagram") but is **useless without `app_map.md`**, which is Django-specific (walks
  `apps.py`, extracts `ast` import edges) — not portable to non-Django stacks, and not something a
  "portable SDD" plugin can assume exists.
- `update_product_docs.md`, `update_upgrade_notes.md`, `update_template_repo.md`,
  `update_claude_plugin_fls_content.md` are **entirely FLS-specific**: they exist to serve FLS's own
  distribution model (a Django library consumed by downstream "concrete" projects via git submodule, with
  its own template-repo scaffold and a separate course-authoring plugin to keep in sync). None of this
  generalizes to an unrelated project.
- `concrete/update_fls.md` is the consumer-side counterpart of `upgrade_notes.md` — also entirely
  FLS-specific, and not part of the SDD step sequence proper (it runs in a *different* repository).
- `qa-data-helper.md` is FLS-domain data-modeling knowledge (factory_boy, cohorts, courses, multi-site),
  not generic QA tooling.

**The single biggest structural obstacle:** `setup_todo_list.md` generates one **undifferentiated**
`todo.md` template that hardcodes all 15 sections — generic sections 1–9 interleaved with FLS-only
sections 10–13 — in the same markdown block. There is no seam here today; splitting the plugin means
either dropping FLS's own checklist items from the generic template (breaking FLS's own workflow) or
teaching one plugin to extend another plugin's generated artifact (no such composition mechanism is
evidenced anywhere in this codebase — it would be new design work).

**The second obstacle:** `next.md`'s command-resolution logic is hardcoded to search exactly two
directories, both inside `fls-claude-plugin/commands/`. Splitting `sdd` out means this dispatcher must
resolve commands that may live in up to three plugin roots (`sdd`, `fls`, and possibly `django-stack` for
`/app_map`, `/security-review`). Claude Code's plugin model gives no evidence of a "list all installed
plugins' command roots" primitive in this codebase — `${CLAUDE_PLUGIN_ROOT}` only resolves to the
*current* plugin's own root, not a sibling's. A "portable" `sdd` plugin's dispatcher would either need to
hardcode knowledge of FLS's sibling plugin names (undermining portability to unrelated projects) or add
probing logic across a small conventionally-named list of sibling plugin roots (workable, but new design,
not a pure move/rename).

## VERDICT

**Option (b): straightforward only if the FLS/Django-specific steps stay behind — and even then, "straightforward" needs a caveat.**

A clean **partial** extraction is real and low-risk for the pieces that carry zero FLS content today:

- `agents/sdd-worker.md`, `agents/sdd-mechanic.md` — move as-is (one path-reference edit in
  `sdd-mechanic.md`).
- `skills/claude-code-authoring/` (SKILL.md + all `resources/`) — move as-is, zero FLS content.
- `commands/sdd/improve_idea.md`, `spec_from_idea.md`, `spec_review.md` — move with only a namespace
  rename (`fls:sdd-worker` → `sdd:sdd-worker`, etc.).
- `commands/sdd/plan_from_spec.md`, `implement_plan.md`, `finish_worktree.md`, `start.md`, `next.md` —
  move with the namespace rename **plus** small, mechanical edits to strip/parameterize the handful of
  FLS-flavored lines each contains (the port-script/`manage.py runserver` line in `plan_from_spec.md`,
  the `uv run pytest`/`uv run git commit` calls in `implement_plan.md`, the `dev_db_delete.sh` call in
  `finish_worktree.md`, `install_dev.sh` in `start_worktree.md`).
- `commands/sdd/protected/update_todo.md`, `move_spec_to_in_progress.md` — move as-is.
- `threat-model.md` — move as-is (or duplicate; it's tiny and stock).

That much genuinely is straightforward — mostly renames and small deletions, no design work.

What is **not** straightforward, and is why a fully clean, fully portable extraction misses the idea's
"quite straightforward" bar:

1. **`protected/setup_todo_list.md`'s todo template** has no seam between generic and FLS-only sections.
   Making the split clean requires either dropping FLS's own tracked steps (regression for FLS) or
   designing a cross-plugin composition mechanism that doesn't exist yet in this codebase (new work).
2. **`next.md`'s command dispatch** must go from a two-directory search hardcoded to one plugin, to a
   resolution strategy that works across `sdd` + `fls` (+ possibly `django-stack`) — a real design
   decision about how one plugin discovers a sibling's command files, not a mechanical rename.
3. **`do_qa.md`, `plan_security_review.md`'s scan spec, and `plan_structure_review.md`'s dependency on
   `app_map`** all have Django/FLS domain knowledge woven directly into their instructions (not just a
   superficial `fls:` reference). Genuinely generalizing them (pluggable dev-server start, pluggable
   data-seeding agent, an assumed-optional architecture diagram) is design work, not extraction.
4. **New cross-plugin runtime dependency.** Every FLS-only command that stays behind
   (`do_qa`, `plan_security_review`, `plan_structure_review`, `update_product_docs`,
   `update_upgrade_notes`, `update_template_repo`, `update_claude_plugin_fls_content`) still spawns
   `fls:sdd-worker` / `fls:sdd-mechanic` today. After extraction they'd spawn `sdd:sdd-worker` /
   `sdd:sdd-mechanic` instead — meaning **`fls` now depends on `sdd` being installed** for its own SDD
   workflow to run at all. That's a one-directional layering (acceptable), but it means the two plugins
   are not independently usable for FLS's own purposes — only `sdd` gains standalone portability, `fls`
   does not shed the dependency.

### Recommended split, if pursued

| Plugin | Contents |
|---|---|
| **`sdd`** (new, portable) | `agents/sdd-worker.md`, `agents/sdd-mechanic.md`, `skills/claude-code-authoring/`, `commands/sdd/{README,improve_idea,spec_from_idea,spec_review,plan_from_spec,implement_plan,next,start,finish_worktree}.md`, `commands/sdd/protected/{update_todo,move_spec_to_in_progress,start_worktree}.md`, `commands/threat-model.md` — each with the namespace rename and the small mechanical edits listed above |
| **`fls`** (stays) | `commands/sdd/{do_qa,plan_security_review,plan_structure_review,update_claude_plugin_fls_content,update_template_repo,update_product_docs,update_upgrade_notes}.md`, `commands/sdd/protected/setup_todo_list.md` (FLS's superset template), `agents/qa-data-helper.md`, `commands/concrete/update_fls.md` — all updated to spawn `sdd:sdd-worker`/`sdd:sdd-mechanic` instead of `fls:...` |
| **`django-stack`** (new, per the idea's own split) | `commands/app_map.md`, `commands/security-review.md` — Django-generic, not FLS-domain-specific, not part of portable SDD either |

### Recommendation

Given the idea's explicit bar — *"Only do this if it is quite straightforward"* — my recommendation is:

- **Do the scoped move** of the zero-content-change pieces (both agents, the `claude-code-authoring`
  skill, and the clean command files) into a new `sdd` plugin. This part really is mechanical and low-risk.
- **Do not attempt to fully generalize** `do_qa.md`, `plan_security_review.md`, `plan_structure_review.md`,
  or the `setup_todo_list.md` template-composition problem in this pass — that is separate, non-trivial
  design work (pluggable dev-server/data-seeding abstractions, cross-plugin todo composition, cross-plugin
  command resolution in `next.md`) that deserves its own spec if wanted later, not a side effect of this
  reorganization.
- Treat the resulting `sdd` plugin as **portable scaffolding with known gaps** for now: `next.md`'s
  command resolution will need to probe a small, explicitly-listed set of sibling plugin roots
  (`fls`, `django-stack`) rather than being blindly plugin-agnostic — document this as a known
  limitation rather than solving it generically.
- This is a middle ground between (b) and (c): mechanically straightforward for ~60% of the SDD
  surface area (by file count), genuinely tangled for the rest. If the team wants a *fully* clean,
  zero-caveat extraction, treat that as out of scope for this reorganization and revisit later.

status: ok
