# Spec-Driven Development (SDD)

A step-by-step workflow for taking a rough idea all the way to a merged pull request. Each step produces an artifact that feeds the next one, so you can pause, review, and correct course between stages.

## The workflow at a glance

1. **Idea** → write a rough idea file, optionally refine it.
2. **Spec** → turn the idea into a specification, review it, threat-model it.
3. **Plan** → turn the spec into an implementation plan and a QA plan, then security-review the plan, then structure-review the plan.
4. **Implement** → execute the plan.
5. **Code security review** → review the code diff for security issues.
6. **QA** → run the QA plan.
7. **Refresh the app map** → if structure changed, re-run `/app_map`.
8. **Document** → run `/update_product_docs` to update `docs/product/` for the shipped feature.
9. **Upgrade notes** → run `/update_upgrade_notes` to produce `upgrade_notes.md` for downstream FLS projects.
10. **Sync the course-author plugin** → run `/update_claude_plugin_fls_content` to sync the `fls-content` plugin if authoring functionality changed (fast-skips otherwise).
11. **Ship** → PR, address feedback, finish worktree.

> `/sdd:start` is the entry point: it creates the `todo.md` checklist next to the spec/idea **and** sets up an isolated worktree for the work. Run it once, then do everything else inside the worktree.

> **One-time setup:** before the first SDD run on a project, run `/app_map` to generate `docs/app_structure.md`. The structure review step compares proposed plans against that diagram.

---

## Step 1: Capture the idea

1. Create an idea file manually (a markdown file describing what you want to build and why).
2. Optionally run `/improve_idea` to research the idea and suggest improvements.

## Step 2: Write the spec

1. Run `/spec_from_idea` to generate a specification from the idea file.
2. Review the spec and edit it manually where needed.
3. Run `/spec_review` to sanity-check the spec.

## Step 2.5: Threat model

1. Run `/threat-model` on the spec to identify security considerations.
2. Update the spec to close any gaps the threat model surfaced, before moving on to planning.

## Step 3: Build the plan

Run `/plan_from_spec`. This produces:

- an implementation plan, and
- a QA plan.

## Step 3.5: Plan security review

Run `/plan_security_review` to review the implementation plan for insecure design choices (raw SQL, missing auth, unvalidated input, etc.) before any code is written. This is cheaper than catching the same issues in `/security-review` after implementation, because design-level security problems often require structural rework.

This complements `/threat-model` (which reviews the spec) and `/security-review` (which reviews the code diff).

## Step 3.6: Plan structure review

Run `/plan_structure_review` to check whether the plan introduces any new cross-app dependencies. The command reads `docs/app_structure.md` (the authoritative dependency diagram) and compares it against the imports the plan implies. Any new edge becomes a `> **Structure concern:**` callout that the user must resolve — either by accepting the edge (with a rationale, and regenerating the diagram after implementation) or by restructuring to avoid it.

This complements `/plan_security_review`: same callout-and-approval pattern, different concern. Catching structural drift at plan time is cheaper than unpicking it after the code is written.

If `docs/app_structure.md` doesn't exist yet, run `/app_map` first. `/app_map` is a general command (not SDD-specific) that walks `apps.py`-containing directories, extracts cross-app `ImportFrom` edges via `ast`, and writes a mermaid diagram plus a dependency table. Re-run it whenever an approved structural change lands, then commit the updated file.

## Step 4: Implement

Run `/implement_plan` to execute the implementation plan.

## Step 5: Code security review

Run `/security-review` to check the code diff for security issues. Running this before QA means structural security fixes don't force QA to be re-run.

## Step 6: QA

Run `/do_qa` to execute the QA plan.

### Reacting to the QA report

- If tests were skipped because of missing data or fixtures, create the needed test data (the `fls:qa-data-helper` agent is designed for this).
- If bugs were detected, fix them using TDD — write a failing test that reproduces the bug, then implement the fix. *(A dedicated bugfix command is still TODO.)*
- If QA fixes change code significantly, re-run `/security-review`.

## Step 7: Refresh the app map

If `/plan_structure_review` surfaced any structure concerns that were accepted (i.e. the plan intentionally introduced new cross-app edges), or if implementation ended up adding, removing, or renaming apps, re-run `/app_map` to regenerate `docs/app_structure.md`. Commit the updated file alongside the feature so the diagram stays the authoritative reference for the next structure review.

If no structural change happened, skip this step.

## Step 8: Update product docs

Run `/update_product_docs` to refresh the product documentation under `docs/product/` for the feature that just shipped. The command reads the spec and plan to identify which docs are affected, fans out one worker per affected doc to draft the updates, applies the edits, and — for features with visible UI — starts a dev server to capture and compress screenshots via Playwright MCP. It ticks its own todo box and cleans up scratch files on completion.

## Step 8.5: Upgrade notes

Run `/update_upgrade_notes` to produce `upgrade_notes.md` in the spec directory. The file has a YAML frontmatter block with machine-readable flags (`requires_migrations`, `requires_template_review`, `requires_settings_change`, `requires_package_upgrade`, `requires_tailwind_rebuild`) plus a short prose body covering breaking changes and manual steps. Downstream FLS projects use this file to know exactly what they need to do after pulling the change.

The command reads the spec, plan, and the actual `git diff main..HEAD` to determine which flags to set. If the feature has no downstream impact, the notes say so plainly — an honest "no action needed" is the right output.

## Step 9: Sync the course-author plugin (if authoring functionality changed)

Run `/update_claude_plugin_fls_content`. The command runs a single `git diff main --name-only | grep` over authoring-relevant paths (content-engine schema, cotton templates, widget allowlist settings, management commands, demo content) — if nothing matched, it ticks its box and exits immediately at zero LLM cost. If something matched, it fans out one `fls:sdd-worker` to read only the changed authoring-relevant files, drafts scoped edits to the `fls-content` reference skills and the bundled validator, applies them (re-applying both the Django-icon stub and the standalone CLI shim when the validator source changed), and cleans up scratch files on completion.

## Step 10: Ship it

1. Open a pull request.
2. Run `/address_pr_review` to work through review feedback.
3. Once merged, run `/finish_worktree` to clean up the worktree.

---

## How the workflow runs

1. **`/clear` before `/sdd:next`.** `/sdd:next` runs the next command **on the main thread (depth 0)** — it no longer isolates the step in a fresh agent. So run `/clear` first to keep the previous step's context from leaking in. This is a deliberate trade-off: we lose automatic context isolation, and in return commands can legally fan out (research/review) again — fan-out is only allowed at depth 0 — and the workflow costs fewer tokens.

2. **Model tiering & the override knob.** Defaults: mechanical work (test runs, commits, file moves, todo ticking) → the `fls:sdd-mechanic` agent (Haiku); non-interactive fan-out (research topics, review dimensions, scans) → the `fls:sdd-worker` agent (Sonnet); interactive authoring/review commands run at depth 0 on the **user's session model** (so run the session on a strong model). To change a step's model, **edit the relevant agent file's `model:` frontmatter** (`fls-claude-plugin/agents/sdd-mechanic.md`, `sdd-worker.md`). The env var `CLAUDE_CODE_SUBAGENT_MODEL` can force one model for **all** subagents in a pinch — but it **overrides every per-agent `model:` frontmatter**, so it must be left **unset (or `inherit`)** for normal tiered operation.

3. **Aliases vs pinned IDs.** The agents use aliases (`haiku`/`sonnet`) for readability. A user who wants frozen, reproducible automation can pin dated IDs (e.g. `claude-haiku-4-5`) in the agent files instead.

4. **Target Claude Code version.** These files target the current **2.1.x** line — per-agent/per-command `model:` frontmatter, `AskUserQuestion`, non-nesting subagents, and "commands merged into skills" all hold here. There is no runtime version check; this is a documented target, not enforced.

5. **Why it runs this way.** See the **`claude-code-authoring`** skill for the canonical reference on the Claude Code mechanics behind all of the above: no subagent nesting or fan-out, no slash commands from subagents, no `AskUserQuestion` in subagents, model tiering, and file-based hand-off.

---

## The `todo.md` checklist

`/sdd:start` creates a `todo.md` checklist in the spec directory that tracks every step above. Each SDD command ticks off its own box (and adds follow-up tasks where relevant) by invoking the protected helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` as its final step. You don't run this helper yourself — the other commands call it for you.

---

## TODO

- Command for reacting to QA-reported bugs.
