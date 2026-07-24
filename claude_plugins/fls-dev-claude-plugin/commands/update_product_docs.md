---
description: Update docs/product/ for the current feature after it ships
allowed-tools: Read, Glob, Write, Edit, Bash, Agent, mcp__playwright*
---

Update the product documentation under `docs/product/` to reflect the feature that was just implemented. This command runs at **depth 0** and fans work out to sub-agents.

## Purpose and audience

`docs/product/` is high-level **product documentation**, not developer or API reference. Its readers evaluate, operate, or integrate FLS — technical decision-makers, downstream integrators, and operators — and need to know *what the product does and what can be configured*, not how it is implemented.

Write to that audience and at that altitude:

- Describe capabilities and configuration surfaces in prose. Name a setting when it is the configuration entry point; do not document its internal schema.
- A typical feature update is **a few sentences** in the relevant doc. Gauge depth by the *altitude* defined above — not by whatever is already in the file. Some existing sections are over-detailed; write to the audience, and where you touch such a section, trim it toward the audience rather than perpetuating the bloat.
- **Do not** dump code blocks, settings dictionaries, or registry contents; enumerate every field/attribute/option in a table; explain internal mechanics, resolution order, or fallbacks; name view/URL routes (`app:view_name`), model/class/method names, ORM field names or types (e.g. `GenericForeignKey`), or internal status/state enums; or restate at length anything covered elsewhere — link instead.

**Altitude litmus test.** A sentence fails — and must be rephrased into plain product language or cut — if *either* prong catches it:

- *Symbols.* It names a Python/Django symbol — a view or URL route name, a model, method, field, an ORM type, or an internal status constant (e.g. `BLOCKED`/`READY`). The **only** code symbols that belong in these docs are a configuration setting an operator sets or an author-facing content option — and then only named in prose, never schema-dumped.
- *Mechanics.* It narrates *how* something is configured or behaves internally — specific tuning parameters (regions, checksums, timeouts, sampling rates, retry counts, TTLs), fallback/resolution behaviour beyond a single clause, or explicit-choice edge cases ("can instead opt into X via Y"). State the capability and its default, then stop; link the rest.

**Worked before/after** (the recurring failure mode — infrastructure prose with no symbols in it, so the symbol prong alone misses it):

> ❌ **Before (too low):** "…media files are stored via S3-compatible object storage, configured specifically for Cloudflare R2 (region, checksum, and compatibility settings suited to R2 rather than plain S3). Object storage is enabled by setting the storage bucket name via environment variable; if unset, the application falls back to local filesystem storage. Media is private by default: file links are time-limited signed URLs (one hour by default, configurable)… A deployment can instead opt into public, edge-cacheable serving via a custom domain, but that is an explicit choice."
>
> ✅ **After (right altitude):** "…media files are served from S3-compatible object storage (Cloudflare R2), enabled by setting the storage bucket environment variable; without it, media falls back to local filesystem storage. Media is **private by default** — links are time-limited signed URLs rather than permanently public, so application-gated course files aren't exposed to anyone who obtains a link. See [security and data handling](./security-and-data-handling.md)."
>
> *What was cut and why:* the R2-vs-S3 tuning settings, "one hour by default, configurable," and the custom-domain opt-in — all *mechanics*. What stays: the capability, the one config entry point (the bucket env var) with a one-clause fallback, and the reviewer-relevant posture (private-by-default), linked for the rationale.

When in doubt, write less and link to the authoritative detail (the code, the spec, or another doc).

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents.

1. **Declare inputs up front.** Gather any user input the phase needs now, via `AskUserQuestion`. Bake the answers into each worker prompt. Subagents don't have access to `AskUserQuestion`.
2. **One output path per unit.** Durable artifacts keep their real names; intermediate outputs go in `.sdd-work/` inside the spec directory, named `<doc>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "sdd:sdd-worker"`. Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → gather the listed `needs` via `AskUserQuestion`, then re-spawn a fresh worker with the original brief + answers.
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and apply edits to the real docs.
7. **Clean up on success.** Delete `.sdd-work/` once all edits are applied.

## Step 1: Identify the affected docs

Read the current feature's spec file (`spec_dd/2. in progress/<feature>/1. spec.md`) and plan file (`spec_dd/2. in progress/<feature>/2. plan.md`) to understand what the feature added or changed.

Determine which files under `docs/product/` are affected — i.e. which product areas the feature touches. Produce a list of `(doc_file, section_summary)` pairs: one entry per doc file that needs updating, with a one-sentence description of what changed in that area.

If the spec or plan path is ambiguous, use `AskUserQuestion` to confirm which feature directory to use before proceeding.

## Step 2: Draft updates (fan-out)

Apply the fan-out recipe: one `sdd:sdd-worker` **per affected doc**, each writing its draft to `.sdd-work/<doc>.md` (e.g. `.sdd-work/authentication.md`). Resume = skip units whose scratch file already ends `status: ok`.

For each worker, bake in:

- The path to the scratch file it must write (`.sdd-work/<doc>.md`).
- The path to the real doc it is drafting an update for (`docs/product/<doc>.md`).
- The section summary from Step 1 — what changed in this area.
- The paths to the spec and plan files (pass as paths; the worker reads them directly).
- Instruction to write **only the updated content** for the relevant section(s) of that doc — not a full rewrite unless the doc is new. Existing sections that are unaffected should be noted as unchanged.
- Instruction to end the scratch file with `status: ok` on success, `status: failed` + `reason:` on failure, `status: blocked` + `needs:` if inputs are missing.

Accuracy rules that every worker must follow (bake these into each prompt):

- Facts only. Base every statement on the spec, the plan, and code that exists. Do not guess, infer optimistically, or be creative.
- State absence plainly. Where a capability is absent, manual, or half-built, say so.
- No duplication. The canonical statement of a fact lives in exactly one doc body; other docs link to it.
- Right altitude. Product docs are high-level feature/configuration info for evaluators, operators, and integrators — not API reference. Aim for a few sentences. Do NOT gauge altitude by copying the surrounding sections — some existing docs are over-detailed; write to the audience instead. Apply the **altitude litmus test** (both prongs): (1) *symbols* — if a sentence names a view/URL route, model, method, field, ORM type, or internal status constant, rephrase it into plain product language or cut it; the only code symbols allowed are a configuration setting an operator sets or an author-facing content option. (2) *mechanics* — do not narrate how something is configured or behaves internally: specific tuning parameters (regions, checksums, timeouts, sampling rates, TTLs), fallback behaviour beyond a single clause, or explicit-choice edge cases belong in the code/spec, not here — state the capability and its default, then stop. No code dumps, no full option tables. See the worked before/after example under "Purpose and audience" above.
- Plain Markdown only — no cotton components, no custom widgets.

## Step 3: Synthesise — apply edits to the real docs

Read each `.sdd-work/<doc>.md` file **by path** (never dump its contents into this prompt). For each, apply the drafted updates to the real `docs/product/<doc>.md`:

- Use `Edit` for targeted section updates; use `Write` only if the doc is new or requires a full replacement.
- Update the `_Last updated: YYYY-MM-DD_` line at the top of each doc to today's date.
- Preserve all unchanged sections exactly.

## Step 4: Screenshot lifecycle (visual features only)

Skip this step if the feature has no visible UI changes (e.g. a backend-only or CLI feature). Proceed if the feature touches any of: learner-experience, educator-interface, admin-interface, or any other doc that requires screenshots.

**Teardown must run even if capture fails** — use a trap or run the kill step explicitly after any error.

### 4a: Find a free port and start the dev server

```bash
PORT=$(.claude/ds/scripts/find_available_port.sh)
uv run python manage.py runserver $PORT
```

Read `.claude/fls-dev/config.md` for admin credentials. Base URL: `http://127.0.0.1:$PORT/`.

### 4b: Confirm the branch badge

Navigate to `http://127.0.0.1:$PORT/` using Playwright MCP. Look for the `debug-branch-badge` element on the page. It must name the current branch. If it names a different branch, there is a port collision — go back to 4a and find a different port.

### 4c: Capture screenshots

Use Playwright MCP tools (`browser_navigate`, `browser_snapshot`, `browser_take_screenshot`, `browser_click`, etc.) to capture the updated UI. Use the **DemoDev** site and demo content for seed data — if required data is missing, delegate to the `fls-dev:qa-data-helper` agent rather than creating data yourself.

Save screenshots into `docs/product/screenshots/` with descriptive names (e.g. `learner_dashboard.png`, `educator_cohort_progress_matrix.png`).

### 4d: Compress screenshots

```bash
uv run --with pillow python ${CLAUDE_PLUGIN_ROOT}/scripts/compress_screenshots.py
```

All screenshots must land under the 1024 KB pre-commit large-file limit.

### 4e: Kill the dev server

```bash
.claude/ds/scripts/kill_runserver.sh $PORT
```

Run this even if step 4c or 4d failed.

### 4f: Reference screenshots from docs

Update the relevant docs to reference new screenshots with plain markdown:

```markdown
![](screenshots/<file>.png)
```

No cotton components, no custom widgets.

## Step 5: Clean up

Delete `.sdd-work/` once all doc edits (and any screenshot references) have been applied:

```bash
rm -rf .sdd-work/
```

## Step 6: Tick the todo

Delegate the todo tick to `sdd:sdd-mechanic`. Spawn the mechanic with this instruction:

> Read the helper file at `claude_plugins/sdd-claude-plugin/commands/protected/update_todo.md` and follow its steps with:
> - `<todo-path>`: the `todo.md` in the spec directory for the current feature
> - `tick:"Run \`/update_product_docs\` to update docs/product/ for this feature"`

The mechanic edits `todo.md` directly. It does not depend on `.sdd-work/`, so running it after the step-5 cleanup is correct.
