# Research: merging steps

Scope: idea point 2 (`idea.md:5-22`). Merges (a)-(d), the generic/overlay rule, resumability, and what must change. Paths are relative to the project root.

## Facts that constrain every merge

- Subagents (`sdd:sdd-worker`) have `Read, Glob, Grep, WebFetch, WebSearch, Write` only (`claude_plugins/sdd/agents/sdd-worker.md:7`). They cannot Edit, run Bash, ask the user, spawn workers or type slash commands (`claude_plugins/sdd/skills/claude-code-authoring/SKILL.md:26-37`). They CAN read a helper `.md` and follow it (SKILL.md:30-32). So a review dimension = a worker told to read a brief file and write findings to `.sdd-work/<phase>_<dim>.md`; all edits to the spec/plan happen at depth 0.
- `sdd:sdd-mechanic` (Haiku) has Bash: use it for scripts (`generate_app_map.py`, `git diff`).
- The hook pattern: `.claude/sdd/config.md:8-19` has `## Rebase Hooks`, `## Design Hooks`, `## Test Hooks`, each `- Key: path-to-command-file`. sdd reads the file and follows it inline at depth 0 (`claude_plugins/sdd/commands/protected/pre_step_rebase.md:40-45`, `claude_plugins/sdd/commands/implement_plan.md:74`). A blank value or absent section = skip. Hook keys today are single-valued; sections are created by `/sdd:init` (`claude_plugins/sdd/commands/init.md:119-151,187,212-216`).
- `update_todo` stops if a `tick:` item is not found (`claude_plugins/sdd/commands/protected/update_todo.md:41`). Any command followed as a hook inside a merged command must therefore skip its own tick.
- `/sdd:next` runs one `(cmd)` item inline at depth 0 and says "Run `/clear` then `/sdd:next` again" (`claude_plugins/sdd/commands/next.md:93`). It resolves the command via prefix map and stops if the file is missing (`next.md:56-63`). Old in-flight `todo.md` files (e.g. `spec_dd/1. next/phone-number-form-field/todo.md`) name the old commands.
- Resume markers today: `.sdd-work/*` files ending `status: ok` (recipe step 3) and `[batch N]` git subjects for implementation (`implement_plan.md:36-38`). A fan-out command's "applied" state has no marker unless it commits.

---

## (a) `/sdd:improve_idea` produces the spec

### Today
- `improve_idea` (`claude_plugins/sdd/commands/improve_idea.md`): input = idea file. Step 1 picks research topics itself (`:25-31`); Step 2 one worker per topic writes durable `research_<topic>.md` next to the idea (`:33-37`) while depth 0 asks user questions in batches of 4; Step 3 REWRITES the idea (`:39-73`); Step 4 ticks "Optionally run `/improve_idea`..." (`:75-82`); Step 5 commit+push (`:84-88`). Questions: only what research cannot settle (`:37,43`).
- `spec_from_idea` (`claude_plugins/sdd/commands/spec_from_idea.md`): input = idea + sibling `*.md` (incl. `research_*.md`, `design.md`) (`:59-73`). Step 1 fans out 3 workers (codebase, best practices, reference implementations) to `.sdd-work/spec_research_<task>.md` (`:31-37`); Step 2 asks questions while they run (`:39-46`); Step 3 writes `1. spec.md` (`:48-125`); Step 4 deletes scratch (`:126-128`); Step 5 ticks "Run `/spec_from_idea`..." (`:130-137`); Step 6 commit.
- The overlap is already large: both research, both ask questions during the fan-out, both read the directory. The difference is that `improve_idea` leaves a human gate: todo "(user) Review the refined idea and edit as needed" (`claude_plugins/sdd/commands/protected/setup_todo_list.md:65`).
- Where `improve_idea` may run: README says "runs on main without starting the spec, so it leaves the roadmap alone" (`claude_plugins/sdd/commands/README.md:33`, `claude_plugins/sdd/resources/roadmap_format.md:42`). The todo, however, lists it after `/sdd:start` (`setup_todo_list.md:64`), i.e. in the worktree. Both are legal today. `spec_from_idea` needs `todo.md` (it ticks it, `:134`) and a feature branch (Step 0 rebase skips on main, `pre_step_rebase.md:20`); commit_and_push never commits SDD artifacts on main (`commands/README.md:158`).

### Merged shape
Two readings of "improve idea could make the spec":
1. Literally extend `improve_idea` to also write the spec. Problem: it then needs a worktree and `todo.md`, which kills its main-branch use (roadmap/precursor flow), and it duplicates `spec_from_idea`.
2. (Better) `spec_from_idea` absorbs `improve_idea`'s research. One fan-out wave: the idea-level topics `improve_idea` would have picked (UX patterns, complaints, prior art) plus the three spec research tasks, all at once, all given the idea only. Durable ones keep `research_<topic>.md` names so `setup_todo_list.md:35` pre-tick detection and the "read the whole directory" rule (`spec_from_idea.md:59`) keep working; spec-only ones stay in `.sdd-work/`. The idea is NOT rewritten (the spec is the refinement). One Step-2 question batch, front-loaded, as `idea.md:3` asks. `improve_idea.md` stays as the optional main-branch command, unchanged.
- Plugin: sdd (generic already). No hooks needed.
- Artifacts: `1. spec.md`, `research_*.md` (durable), scratch removed by name. Commit "write the spec" stages the research files too.
- Todo: drop the "Optionally run `/sdd:improve_idea`" and "Review the refined idea" items from the template (`setup_todo_list.md:64-65`) or keep the first as `(cmd) Optionally ... on main before /sdd:start`. `setup_todo_list.md` detection table row for `research*.md` (`:35`) then ticks a no-longer-existing item; retarget it to no tick.

### Trade-offs
- Context: one command, but research findings are read as files at synthesis either way; saving is one fewer `/clear` + `/sdd:next` round and one fewer rewrite pass (idea rewrite is skipped). Orchestrator context grows only by the larger research file set (up to ~6-8 files).
- Resumability: durable `research_*.md` + `.sdd-work` `status: ok` scan already make a dead run cheap to resume; the spec is one `Write`. Safe.
- Human loses the idea-review gate. Compensation: questions are asked up front (so decisions are the user's), defaults taken are listed under the spec's "Open questions" (`spec_from_idea.md:46`), and the "(user) Review the spec" item remains. The idea-review gate mostly caught "research took the wrong direction"; a spec-level review catches the same, one step later.

### Recommendation
Reading 2: fold improve_idea's research topics into `spec_from_idea` Step 1; remove the optional improve_idea/idea-review items from the todo; keep `improve_idea.md` for main-branch use. Do not make improve_idea write the spec.

---

## (b) Spec review by subagents inside the spec command

### Today
- `spec_review` (`claude_plugins/sdd/commands/spec_review.md`): input = `1. spec.md` + idea + siblings. No fan-out; depth-0 loop: find contradictions one at a time, "describe, ask for input, edit" (`:20-26`); check technical feasibility/norms against `${CLAUDE_PLUGIN_ROOT}/resources/`, vocabulary, generic-plugin rule (`:28-44`); repeat until clean (`:46-48`); tighten with completeness pass first (`:50-77`); tick "Run `/spec_review`..." and add `Spec|user|Decide how to handle ...` for unresolved questions (`:79-85`); commit (`:87-91`). Asks the user per contradiction/problem.
- It is explicitly "the last gate before planning whichever way [the spec] arrived", including hand edits and `/threat-model` amendments (`:55-57`). Todo order: spec_from_idea -> (user) review/edit -> spec_review -> (user) address issues (`setup_todo_list.md:69-72`).

### Merged shape
Inside `spec_from_idea`, after the spec is written (second wave: review needs a spec to review, so it cannot join the research batch). Commit "write the spec" first (resume marker), then fan out one `sdd:sdd-worker` per dimension, mirroring `plan_from_spec` Step 6 (`plan_from_spec.md:125-136`):
1. contradictions + completeness vs idea and every sibling `*.md` (`spec_review.md:62-65`);
2. feasibility and project norms vs code and `${CLAUDE_PLUGIN_ROOT}/resources/`;
3. vocabulary / Terminology section (`:34`);
4. generic-plugin rule (`:38-40`);
5. cut-list candidates (`spec_review.md:66-76`, `spec_from_idea.md:106-119`).
Each writes `.sdd-work/spec_review_<dim>.md` with findings (quoted spec text, problem, proposed fix, `needs-user` flag). Depth 0 applies clear fixes by Edit (workers cannot), batches the `needs-user` ones into one `AskUserQuestion` (default taken + listed under "Open questions" when a default exists), then does the tighten pass (an editing pass, stays at depth 0), unslop, counts. One bounded re-check (single re-run of dimensions 1 and 3 only) replaces "repeat until clean".
- Plugin: sdd. Dimension briefs can be inline in the command or a shared `claude_plugins/sdd/resources/spec_review_dimensions.md` that both `spec_from_idea` and the (kept) `spec_review` read. Nothing FLS-specific.
- Artifacts: `1. spec.md` (edited), second commit "review and tighten the spec"; todo: tick spec_from_idea only; unresolved questions become `add:"Spec|user|Decide ..."` as `spec_review.md:85` does today.
- Todo: remove "(cmd) Run `/sdd:spec_review`" or make it "(cmd) Optionally run `/sdd:spec_review` after hand edits".

### Trade-offs
- Context: review findings are small files; applying edits happens in a context that already holds the spec. Saves a `/clear` cycle and re-reading the spec cold. Cost: orchestrator context carries research + spec + findings; mitigated because workers do the reading.
- Resumability: the weak point is non-idempotent in-place edits. A rerun after a crash mid-apply would re-apply `status: ok` findings to a half-edited spec. Mitigate with the commit marker: commit the draft spec, apply findings, commit "review and tighten"; on resume, if the review commit exists skip, else re-apply findings against the working tree (findings quote text, so already-applied ones are detected as absent).
- Human gate: today the human edits the spec and the review then checks those edits. After the merge, hand edits are unreviewed. Keep `/sdd:spec_review` as an optional command that runs the same dimensions (shared resource), and make the template item optional. Per-contradiction user dialogue is replaced by one front-loaded batch (consistent with `idea.md:3`).

### Recommendation
Do it, as a second wave inside `spec_from_idea`, with the dimension list in a shared sdd resource; keep `spec_review` as an optional post-hand-edit command (same resource, no duplicated text).

---

## (c) Plan structure + "new threats" checks as fan-out units in `plan_from_spec`

### Today
- `plan_from_spec` (`claude_plugins/sdd/commands/plan_from_spec.md`): Step 1 spawns the skills/MCP scan immediately (`:44`); Step 2-3 write the plan; Step 5 QA file; Step 6 spawns 8 review-dimension workers to `.sdd-work/plan_review_<dim>.md`, depth 0 edits the plan (`:125-139`); cleanup, tick, commit (`:143-159`). Asks contradictions the code can't resolve, batched (`:50`). Allowed-tools already include `AskUserQuestion`. The dimension at `:132` already checks the generic-plugin rule, which `plan_structure_review.md:68-72` duplicates.
- `plan_security_review` (`claude_plugins/fls-dev/commands/plan_security_review.md`): one worker scans plan vs a very wide insecure-design list (`:51-101`); edits plan or adds `> **Security concern:**` callouts + `Plan security review|user|...` todo items (`:103-130`); commit. Idea says it is too wide/paranoid and unused (`idea.md:13`).
- `plan_structure_review` (`claude_plugins/fls-dev/commands/plan_structure_review.md`): stops if `docs/app_structure.md` missing (`:43-47`); one worker parses the mermaid graph and flags new/promoted cross-app edges (`:51-82`); edits plan or adds `> **Structure concern:**` callouts + `Plan structure review|user|...` items (`:84-122`); commit.
- `ds:threat-model` (spec level, 6 generic lines, `claude_plugins/django-stack/commands/threat-model.md`) and `ds:security-review` (code level, bandit/pip-audit/detect-secrets, `.../security-review.md`) are generic ds commands; template sections 3, 5, 6, 8 call them (`setup_todo_list.md:74-77,84-92,99-102`).

### Merged shape
Add two dimensions to Step 6's wave (they review the finished plan, so they ARE the second wave; the skills scan stays in the first). Both are hook files so FLS content never enters sdd:
```
## Plan Review Hooks
- Review dimension: claude_plugins/fls-dev/resources/plan_review_structure.md
- Review dimension: claude_plugins/fls-dev/resources/plan_review_new_threats.md
```
(repeatable key; blank/absent = no extra dimensions, same convention as the other hooks). Step 6 reads each listed file, spawns one `sdd:sdd-worker` per file with the brief = that file and output `.sdd-work/plan_review_<hook-file-stem>.md`. Because workers can read-and-follow a file but not run a command, the hook files are briefs, not slash commands.
- `plan_review_structure.md` = the "Scan specification" block of `plan_structure_review.md:53-82`, minus the Step 0/tick/commit scaffolding; the missing-diagram case becomes `status: blocked` `needs: docs/app_structure.md`, which depth 0 satisfies by running the `app_map` script via a mechanic (or skips with a note). The plugin-boundary paragraph (`:68-72`) can go, since the existing generic dimension covers it.
- `plan_review_new_threats.md` = a NARROW brief: only attack surface the plan adds (new endpoints/URLs, new input, new permissions/tenancy paths, new files/uploads, new deps, new secrets). Keep the FLS multi-tenant reference (`plan_security_review.md:57`), which is why it lives in fls-dev; drop the ten-heading checklist, rate-limit/logging/consistency sections. Output "none introduced" as a valid `status: ok`.
- Findings handling replaces callouts: depth 0 edits the plan where the fix is clear (as today), and batches judgement calls into ONE `AskUserQuestion` at the end of the command (front-loaded per `idea.md:3`), recording the decision in the plan. If the user is unavailable the callout format (`> **Structure concern:**`) plus `add:` todo items remain the fallback.
- `/sdd:next`, `setup_todo_list.md`: delete template sections 3, 5, 6 (threat model, plan security review, plan structure review). Section 8 (`/ds:security-review` on code) is not part of the merge; see open questions.
- `ds:threat-model` and `fls-dev:plan_security_review`: removable; `plan_structure_review` becomes the hook file (git mv) and the command is removed (or kept as a thin stub).

### Trade-offs
- Context: 2 extra workers, 2 extra small files read; negligible against the 8 existing. Wall-clock: parallel, so ~unchanged.
- Resumability: best of the four. Findings files are `status: ok`-resumable; plan edits are idempotent enough, but add the same commit marker pattern (commit plan before review, then "review the plan") if desired.
- Human gate: loses the explicit "(user) Address any structure/security concerns" todo items. The "(user) Review both plans" gate (`setup_todo_list.md:82`) remains and now sees a plan that already absorbed the findings. Self-review compensates by quoting plan text per finding and by being forced to flag, never auto-resolve, ambiguous new edges (`plan_structure_review.md:97`).
- One FLS-side point: structure review depends on `docs/app_structure.md` being current. `.pre-commit-config.yaml:70` runs `generate_app_map.py --check` on commit, which makes the diagram refresh effectively enforced at implementation time, not only in (d).

### Recommendation
Do it. Hooks as above; delete `plan_security_review` and `ds:threat-model`; reuse the structure scan spec verbatim as a hook file.

---

## (d) One post-implementation documentation command

### Today
- `update_product_docs` (fls-dev, `claude_plugins/fls-dev/commands/update_product_docs.md`): reads spec+plan, relevance gate (`:62-68`), one worker per affected doc drafts to `.sdd-work/<doc>.md` (`:70-93`), depth 0 applies, then screenshots: reuses QA screenshots from `spec_dd/.../screenshots/` and only starts a dev server for gaps (`:103-184`), cleanup, tick, commit (`:186-217`). Empty result is a normal outcome (`:68`).
- `update_upgrade_notes` (fls-dev, `.../update_upgrade_notes.md`): depth 0, no fan-out (`:8`); reads spec, plan and the full `git diff main..HEAD` (`:77-85`); writes `upgrade_notes.md` with YAML flags (`:10-53,96-108`); verifies names against the tree (`:110-131`); tick, commit. Re-run after PR review in todo (`setup_todo_list.md:129`).
- `update_claude_plugin_fls_content` (fls-dev): zero-token grep gate over authoring paths (`:13-23`), one worker only on a match (`:25-41`), apply edits and re-apply validator patches (`:43-63`), tick, commit.
- `ds:app_map` (`claude_plugins/django-stack/commands/app_map.md`): runs `generate_app_map.py`, prints the edge diff; "Do not call update_todo" (`:57`); no commit (the file is committed with the feature, `commands/README.md:116`).
- All four fls-dev commands start with the pre-step rebase (their Step 0) and end with tick + commit. Template sections 10-12 (`setup_todo_list.md:111-123`) hold their todo items; `/ds:app_map` has no todo item (it is README step 7, `commands/README.md:114-118`).

### Merged shape
New sdd command `/sdd:document` (generic) with a hook list:
```
## Documentation Hooks
- Documentation step: claude_plugins/django-stack/commands/app_map.md
- Documentation step: claude_plugins/fls-dev/commands/update_upgrade_notes.md
- Documentation step: claude_plugins/fls-dev/commands/update_product_docs.md
- Documentation step: claude_plugins/fls-dev/commands/update_claude_plugin_fls_content.md
```
Order matters: app map and upgrade notes first (product docs routes upgrade content to upgrade notes, `update_product_docs.md:25`); fls-content last; all after `/fls-dev:do_qa`, because product docs reuse QA screenshots (`:107`).
- Each hook is followed INLINE at depth 0, in order, the way Rebase Hooks are, NOT spawned as workers: `update_product_docs` fans out per doc, and a worker cannot fan out (SKILL.md:27-28), and it needs Bash/dev server. Hook mode = skip the hook's Step 0 rebase (merged command ran it once) and its todo tick; keep each hook's own commit (a per-hook commit is the resume marker and satisfies README rule 5, `commands/README.md:158`). Add that sentence once to each hook file (or to `/sdd:document`'s instruction to follow them).
- "Only if needed" is already encoded: fls-content's grep gate exits with no LLM cost; `app_map` can run `generate_app_map.py --check` first and skip when clean; product docs allows "no change needed".
- A failing hook does not stop the rest; report at the end and leave its todo sub-item unticked.
- Todo: sections 10-12 collapse to `## 10. Documentation`: `(cmd) Run /sdd:document ...`, `(user) Review the documentation`. Keep the post-PR-review "(cmd) re-run /fls-dev:update_upgrade_notes" (`setup_todo_list.md:129`), so `update_upgrade_notes` must remain a standalone command that works both as a hook and directly. Commands/README steps 7-9 merge into one.
- Plugin: the generic command and hook mechanism in sdd; every FLS path in `.claude/sdd/config.md`. `setup_todo_list.md` then names `/sdd:document` (generic) where it named three `/fls-dev:*` items, reducing the existing coupling noted in `claude_plugins/sdd/README.md:12-14`. Alternative: put `/fls-dev:document` in fls-dev and name it in the template (no hook list, but sdd's template stays coupled).

### Trade-offs
- Context: the heaviest merge. Sequential inline hooks put product-docs instructions (~215 lines of the command + per-doc drafts) and upgrade-notes' full branch diff in one window, after an already long implementation+QA session. Mitigations: `/clear` before `/sdd:next` still applies (the command is a single item); have a mechanic write `git diff main..HEAD` to `.sdd-work/branch.diff` and let upgrade notes be drafted by a worker that Reads it (worker lacks Bash), or run it first so the diff is the only large input at that point.
- Resumability: per-hook commits make it good. Resume scan = for each hook, "commit with its summary exists on the branch since the last `[batch ...]`" or its `.sdd-work` units `status: ok`. A death during product-docs screenshot capture leaves a dev server; already handled by its kill step (`update_product_docs.md:145-165`).
- Human gate: two user review items (docs, upgrade notes) become one. Upgrade-notes correctness is protected by its own name-verification step (`:110-131`) and the post-PR re-run.

### Recommendation
Do it as `/sdd:document` + `## Documentation Hooks`; keep the four underlying commands (hook mode, plus `update_upgrade_notes` standalone for the post-review re-run). Run strictly after QA.

---

## Cross-cutting: todo template and /sdd:next

- `/sdd:next` needs NO logic change: it dispatches any `/<prefix>:<name>` via the prefix map (`next.md:52-63`). Only the example list at `next.md:52` (names `/ds:threat-model`) should be refreshed. It will still say "Run `/clear` then `/sdd:next`" after each merged command; keep that.
- `setup_todo_list.md` must change: the checklist (`:57-136`) loses sections 3 (threat model), 5 (plan security), 6 (plan structure), and the optional improve_idea/idea-review and spec_review items; sections 10-12 become one; the artifact-detection table (`:32-39`) loses the `research*.md` -> improve_idea tick. Renumber headings. The "Tick this item" strings in each command's final step must match the new template text exactly, because `update_todo` stops on a missing tick (`update_todo.md:41`): `spec_from_idea.md:135`, `plan_from_spec.md:152`, and the new `/sdd:document` command.
- In-flight specs: old `todo.md` files name removed commands; `next.md:60-62` would stop with "resolves to no command file". Keep removed command files as stubs for one release, or tell owners to hand-edit. `setup_todo_list.md` already refuses to overwrite an existing todo (`:22-26`), so no automatic migration exists.
- `init.md` must create/validate the two new config sections (`## Plan Review Hooks`, `## Documentation Hooks`) next to the existing ones (`init.md:119-151,187,212-216`); this repo's `.claude/sdd/config.md` gets the FLS values.
- Questions in merged commands: front-load. Wave order per command: spec = [research] -> questions asked during -> synthesis -> [review wave] -> one batch of review questions; plan = [skills scan] -> write plan -> [review wave incl. hooks] -> one batch; docs = sequential inline hooks, questions only from `AskUserQuestion` in the hooks themselves (feature-dir ambiguity, `update_product_docs.md:64`), which the merged command resolves once.

## References that must change

Grep over `claude_plugins/`, `.claude/`, `docs/`, `CLAUDE.md`, READMEs, `spec_dd/1. next/` (excluding `spec_dd/3. done/` history):
- `claude_plugins/sdd/commands/README.md` (22 hits): workflow list `:9-17`, steps 2-2.5 `:43-52`, 3.5-3.6 `:63-75`, 5 `:81-83`, 7-9 `:114-132`; "One-time setup" `:21` mentions app_map (unchanged).
- `claude_plugins/sdd/README.md:6-7,19-20,31` (command inventory, "15 files", list of fls-dev/ds steps and the coupling note `:12-14`).
- `claude_plugins/sdd/commands/protected/setup_todo_list.md` (15 hits, see above).
- `claude_plugins/sdd/commands/next.md:52` (example list).
- `claude_plugins/sdd/commands/improve_idea.md:80` (tick text) if its todo item changes; `spec_from_idea.md:135`; `spec_review.md:83` (tick text, and its `/threat-model` mention at `:55-57`); `plan_from_spec.md:152` and Step 6 `:125-139`.
- `claude_plugins/sdd/commands/init.md:119-151,187,212-216` (config sections).
- `claude_plugins/sdd/commands/roadmap.md:161,234`, `claude_plugins/sdd/resources/roadmap_format.md:42,159` (mention improve_idea/spec_from_idea; only wording changes if improve_idea stays).
- `claude_plugins/sdd/commands/protected/update_todo.md:22` (example prose only).
- `claude_plugins/fls-dev/README.md:29-31,59` (command inventory); `claude_plugins/django-stack/README.md:41-42` (`security-review`, `threat-model` if removed).
- `claude_plugins/fls-dev/commands/plan_security_review.md`, `plan_structure_review.md` (removed/converted); `update_product_docs.md:25,192-215`, `update_upgrade_notes.md:139`, `update_claude_plugin_fls_content.md:71` (hook-mode sentence; their tick text).
- `claude_plugins/fls-dev/commands/concrete/update_fls.md:22` (names `/update_upgrade_notes`; unchanged if kept).
- `claude_plugins/django-stack/commands/threat-model.md` (removed); `security-review.md` per open question.
- Unchanged if `app_map` is kept: `claude_plugins/fls-dev/skills/testing/SKILL.md:37`, `claude_plugins/django-stack/resources/testing.md:49`, `docs/app_conventions.md:120`, `docs/app_structure.md:3,11`, `.pre-commit-config.yaml:70`, `test_organisation/import_contracts.toml:1`, `generate_app_map.py`.
- `.claude/sdd/config.md` (new sections). `.claude/agent-memory/ds-code-reviewer/project_fls_content_plugin.md` mentions the fls-content command; agent memory, do not edit.
- `CLAUDE.md`: no command names found; no change. Its "Plugins" rule (`CLAUDE.md` Plugins section) is the review criterion for all new files.
- `spec_dd/1. next/`: `phone-number-form-field/todo.md` (12 hits) and other `todo.md` files carry old item text; `educator-interface-12-docs-and-polish/idea.md`, `mega-qa/idea.md`, `educator-interface-full-polish/application-review-ui/idea.md` and `mega-qa/research_*.md` mention these commands in prose; `spec_dd/1. next/roadmap.md` (4 hits). Review only; they are other specs' text.

## Open questions for the owner

1. Does "the current threat-model and security review commands ... can be removed" (`idea.md:13`) include `/ds:security-review` on code (template section 8 and its re-run in section 9, `setup_todo_list.md:99-109`), or only `ds:threat-model` and `fls-dev:plan_security_review`? ds:security-review is generic and runs bandit/pip-audit/detect-secrets, unlike the wide plan review.
2. Should `spec_review` survive as an optional command after hand edits (recommended), or be deleted outright, accepting that hand-edited specs are unreviewed?
3. Where does the merged documentation command live: generic `/sdd:document` with a `## Documentation Hooks` list (recommended, less coupling), or `/fls-dev:document`?
4. Old in-flight `todo.md` files: keep stubs of removed commands for a release, or hand-edit those todos?
5. Plan-review findings that need a judgement call: ask via one `AskUserQuestion` at the end of `plan_from_spec` (recommended) or keep leaving `> **... concern:**` callouts plus user todo items?

status: ok
