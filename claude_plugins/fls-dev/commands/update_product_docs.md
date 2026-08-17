---
description: Update docs/product/ for the current feature after it ships
allowed-tools: Read, Glob, Write, Edit, Bash, Agent, mcp__playwright__*, mcp__plugin_ds_playwright__*
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

## Step 4: Screenshots (visual features only)

Skip this step if the feature has no visible UI changes (e.g. a backend-only or CLI feature). Proceed if the feature touches any of: learner-experience, educator-interface, admin-interface, or any other doc that requires screenshots.

**Reuse before you capture.** `/do_qa` has almost certainly already photographed this feature. Do not start a dev server until you have checked the QA screenshots and found a real gap.

### 4a: List the images each doc needs

From the Step 1 doc list and the Step 3 edits, write down the images the docs actually need — one line per image: which doc, what the image must show, and a descriptive product-doc filename (e.g. `educator_cohort_progress_report.png`). Keep this list short; a product doc needs an image where the UI *is* the point being made, not one per screen the feature touches.

### 4b: Shop the QA screenshots first

QA output lives alongside the spec:

```bash
ls "spec_dd/2. in progress/<feature>/screenshots/"
```

Files are named `<viewport>_<test-id>_<short-description>.png` (e.g. `desktop_1.4_generate_page.png`); some may have been converted to `.jpg` by QA's compression step. Read `qa_report.md` in the same directory to learn what each one actually shows and which ones are failure evidence.

For each needed image, pick a QA screenshot only if it:

- shows the feature **working as intended** — never a bug repro, error page, 403/404, or mid-flow half-filled state, even if the bug has since been fixed
- is a `desktop_` capture, unless the doc's point is specifically responsive/mobile behaviour
- is current — captured after the last commit that changed that UI. If the UI has since been redesigned, the shot is stale; treat it as a gap.

Copy the winners into place, renaming to the product-doc name from 4a (QA test IDs mean nothing to a product-doc reader):

```bash
mkdir -p docs/product/screenshots
cp "spec_dd/2. in progress/<feature>/screenshots/desktop_1.4_generate_page.png" \
   docs/product/screenshots/educator_generate_report.png
```

Copy — never move or symlink. The QA artifacts stay intact for the QA report.

If every needed image was satisfied here, skip to 4d — no dev server, no Playwright.

### 4c: Capture only the gaps

Only for images with no suitable QA screenshot.

**Teardown must run even if capture fails** — use a trap or run the kill step explicitly after any error.

1. **Start a dev server on a free port:**

   ```bash
   PORT=$(.claude/ds/scripts/find_available_port.sh)
   uv run python manage.py runserver $PORT
   ```

   Read `.claude/fls-dev/config.md` for admin credentials. Base URL: `http://127.0.0.1:$PORT/`.

2. **Confirm the branch badge.** Navigate to `http://127.0.0.1:$PORT/` using Playwright MCP and look for the `debug-branch-badge` element. It must name the current branch. If it names a different branch there is a port collision — go back to step 1 and pick another port.

3. **Capture.** Use Playwright MCP tools (`browser_navigate`, `browser_snapshot`, `browser_take_screenshot`, `browser_click`, etc.) at a desktop viewport. Use the **DemoDev** site and demo content for seed data — if required data is missing, delegate to the `fls-dev:qa-data-helper` agent rather than creating data yourself. Save into `docs/product/screenshots/` under the names from 4a.

4. **Kill the dev server** — run this even if capture failed:

   ```bash
   .claude/ds/scripts/kill_runserver.sh $PORT
   ```

### 4d: Check file sizes

Every image under `docs/product/screenshots/` must land under the 1024 KB pre-commit large-file limit:

```bash
find docs/product/screenshots -type f \( -name '*.png' -o -name '*.jpg' \) -size +1024k
```

Anything listed will trip the pre-commit hook. Screenshots copied in 4b are already compressed by `/do_qa`, so any offender is normally a fresh capture from 4c — re-capture it at a smaller viewport or downscale it. Note that `scripts/compress_screenshots.py` only scans `spec_dd/`, so it will not fix files under `docs/`.

### 4e: Reference screenshots from docs

Update the relevant docs to reference the screenshots with plain markdown:

```markdown
![](screenshots/<file>.png)
```

Use the extension the file actually has (`.jpg` if QA's compression converted it). No cotton components, no custom widgets.

## Step 5: Clean up

Delete `.sdd-work/` once all doc edits (and any screenshot references) have been applied:

```bash
rm -rf .sdd-work/
```

## Step 6: Tick the todo

Delegate the todo tick to `sdd:sdd-mechanic`. Spawn the mechanic with this instruction:

> Read the helper file at `claude_plugins/sdd/commands/protected/update_todo.md` and follow its steps with:
> - `<todo-path>`: the `todo.md` in the spec directory for the current feature
> - `tick:"Run \`/update_product_docs\` to update docs/product/ for this feature"`

The mechanic edits `todo.md` directly. It does not depend on `.sdd-work/`, so running it after the step-5 cleanup is correct.
