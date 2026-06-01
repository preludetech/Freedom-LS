---
description: Review the implementation plan for security issues before any code is written
allowed-tools: Read, Glob, Grep, Edit, Bash, Agent
---

You are doing a security review of an **implementation plan** (not code). The plan describes *how* a feature will be built. Your job is to catch insecure design choices in the plan before implementation time is spent on them.

This is distinct from:
- `/threat-model` — runs against the spec (the *what*), earlier in the workflow.
- `/security-review` — runs against the code diff (the *how*, after implementation).

This command sits between them: it reviews the plan's *how* before code exists.

## Fan-out recipe (shared)

This command runs at **depth 0** and fans work out to sub-agents. See the `claude-code-authoring` skill for *why* it works this way (no subagent nesting, fan-out only at depth 0, `AskUserQuestion` is orchestrator-only, file-based hand-off, model tiering). Orchestrating units U1…Un:

1. **Declare inputs up front.** Gather any user input the phase needs now, via `AskUserQuestion`. Bake the answers into each worker prompt.
2. **One output path per unit.** Durable artifacts keep their real names (e.g. `research_<topic>.md`); intermediate outputs go in `.sdd-work/` inside the spec directory, named `<phase>_<unit-id>.md`.
3. **Resume scan.** Skip any unit whose output file already exists and ends with `status: ok`; spawn only missing/not-ok units.
4. **One worker per unit**, in parallel, via the `Agent` tool with `subagent_type: "fls:sdd-worker"` (or `"fls:sdd-mechanic"` for mechanical units). Pass the exact output path and the baked-in inputs. Never one worker looping over the batch.
5. **Collect structured returns:** `ok` → done; `failed` → retry the same unit (≤2 attempts, include the prior error); `blocked` → gather the listed `needs` via `AskUserQuestion`, then re-spawn a fresh worker with the original brief + answers (pointing it at any partial file).
6. **Synthesis is a separate step** — read the output *files* (pass paths, never dump contents into the prompt) and produce the artifact; it can be retried without re-running workers.
7. **Clean up on success.** Delete `.sdd-work/` once the phase artifact is finalised. Durable artifacts are not deleted; an abandoned `.sdd-work/` from an interrupted run is intentional (it makes resume cheap).

# Inputs

- `2. plan.md` — the implementation plan under review
- `1. spec.md` — the spec the plan is derived from (for context and success criteria)
- Any threat model notes in the spec or directory

# Output

- Edit `2. plan.md` directly to fix concrete issues where the fix is clear.
- Where a fix requires a judgement call, add a clearly marked `> **Security concern:**` callout in the relevant section of the plan and ask the user for input.
- Print a short summary of what you changed and what still needs user input.

# Step 1: Confirm inputs

Confirm `1. spec.md` and `2. plan.md` exist. If the spec or plan is missing, stop and ask the user.

# Step 2: Delegate the scan (fan-out)

Spawn **one `fls:sdd-worker`** to read `1. spec.md`, `2. plan.md`, any `research*.md`/threat-model notes, and the project conventions, then scan the plan against the insecure-design patterns in the **Scan specification** below. It writes its findings to `.sdd-work/plan_security_findings.md` (atomically, with a `status:` footer), one finding per issue with: the plan section, the pattern matched, severity, and a suggested fix or a note that it needs a user judgement call. Apply resume/retry/blocked per the recipe.

## Scan specification (the worker's brief)

Walk through the plan looking for each of the following.

### Data access and queries
- Raw SQL or ORM escape hatches without a strong justification (project rule: ORM-only without explicit security review).
- Plan steps that bypass automatic multi-tenant filtering — e.g. using a manager that skips site filtering, or reaching across tenants deliberately — without a clear justification. Site filtering is automatic via `SiteAwareModel`; the plan should rely on it, not reimplement it. See the `fls:multi-tenant` skill.
- Missing `select_related` / `prefetch_related` where related objects are accessed in loops (N+1).
- Queries built from user input via string interpolation or formatting rather than parameterised ORM calls.

### AuthN / AuthZ
- Views or endpoints without explicit auth decorators or permission checks.
- Missing ownership/tenant checks (e.g. "get object by id from URL" without verifying the user owns it).
- Admin-only functionality not gated to staff/superuser.
- Role checks based only on frontend state (buttons hidden in templates) without server-side enforcement.

### Input handling
- Accepting user input without validation (forms, query params, path params, JSON bodies).
- File uploads without size, type, or content-type validation.
- Rich-text or markdown rendering paths that might bypass existing sanitisation.
- Redirect targets taken from user input (open redirect).

### State-changing requests
- State-changing views (POST/PUT/PATCH/DELETE, HTMX equivalents) without CSRF protection.
- Idempotency not considered where it matters (duplicate submissions, retries).

### Secrets and credentials
- Credentials or API keys mentioned as plan steps without noting that they come from env vars.
- New environment variables introduced without being documented.
- Secrets written to logs, error responses, or stored on models.

### Dependencies
- New third-party packages with a security-sensitive role (auth, crypto, parsing, templating, serialization) that aren't widely used or maintained.
- Pinning to old versions of packages with known CVEs.

### Error handling and information disclosure
- Exception details or stack traces returned to the user.
- Overly broad exception handlers that could swallow security-relevant errors.
- Differentiated error messages that could enable user enumeration (e.g. "user not found" vs "wrong password").

### Rate limiting and abuse
- New endpoints that could enable brute force (login, password reset, token validation, search) without rate limiting noted.
- Expensive operations reachable by unauthenticated users.

### Logging and audit
- Security-sensitive operations (auth, permission changes, data export) without a note about audit logging where the project expects it.
- Logging that might capture sensitive data (passwords, tokens, PII).

### Consistency checks
- If a threat model exists (in the spec or as a separate file), verify the plan addresses each mitigation it calls out; note any missing mitigation.
- Scan `CLAUDE.md` files and any `${CLAUDE_PLUGIN_ROOT}/resources/` documentation for security-adjacent rules (ORM-only, HTMX CSRF header setup, multi-tenancy isolation, custom user model usage, etc.) and note any plan step that contradicts them.

# Step 3: Apply the findings (depth 0)

Read `.sdd-work/plan_security_findings.md` (the file, not dumped contents). For each finding:
- If the fix is clear, **edit `2. plan.md` directly**.
- If it requires a judgement call, add a `> **Security concern:**` callout in the relevant section of the plan and ask the user for input.

# Step 4: Write the summary

Print a short summary with:
- What you edited directly in the plan
- What is flagged as `> **Security concern:**` callouts that need user decisions
- Whether the plan is safe to proceed with, or whether the user must resolve flagged concerns first

# Step 5: Clean up

Delete the `.sdd-work/` scratch directory once the review is complete (recipe step 7).

# Step 6: Update the todo list

Delegate to `fls:sdd-mechanic`: invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the same directory as `2. plan.md`
- `tick:"Run `/plan_security_review` to check the plan for insecure design choices before implementation"`
- For each `> **Security concern:**` callout you added to `2. plan.md`, pass one `add:"Plan security review|user|Resolve plan security concern: <short label>"`. If you added no callouts, omit `add:`.

# Out of scope

- Do not review or write code — the code does not exist yet.
- Do not add implementation detail beyond what is needed to close a specific security gap.
- Do not re-do the threat model; this is about the *plan*, not the *spec*.
