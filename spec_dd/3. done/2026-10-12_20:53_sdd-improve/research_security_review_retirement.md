# Research: retiring the security commands

Scope: the owner's claim (`idea.md:13`) that the threat-model and security review commands "go too wide and too paranoid", are not run, and can go, with a lighter "new threats?" check added to `/sdd:plan_from_spec` beside the structure check.

## What the three commands do today

**`/ds:threat-model`** (`claude_plugins/django-stack/commands/threat-model.md:1-8`). An 8-line prompt with no frontmatter, no tools list and no output path. Input: `$ARGUMENTS` (a free-text feature name). Steps: list assets, list threat actors, "map attack vectors ... against OWASP Top 10:2025", define controls per vector, check whether code has them, list gaps. Output: whatever the model prints; nothing is written to a file and nothing ties it to the spec. `spec_review.md:56` says the spec may be "amended by `/threat-model`", and `plan_security_review.md:30` reads "threat model notes in the spec or directory". Why it reads as wide and paranoid: it sweeps assets, actors and OWASP categories for the whole feature, whatever the spec changes. A typo fix or a theme-token change gets the same sweep as a new upload endpoint. It has no severity floor and no "nothing new" exit, so it produces a list every time. The artifacts it left are long (`spec_dd/3. done/2026-05-05_08:18_better-registration/threat_model.md` has 24 headings or table rows).

**`/ds:security-review`** (`claude_plugins/django-stack/commands/security-review.md:1-9`). 7-item checklist run against "the current changes": `uv run bandit -r . -x ./tests`, `uvx pip-audit`, `detect-secrets scan`, a review of new or modified views for auth decorators and ownership, ORM raw SQL and injection, CSRF on state-changing views, and `manage.py check --deploy`. Input: `$ARGUMENTS` as "focus areas". Output: conversational. The first three items and the last scan the whole repo, not the diff. The `check --deploy` run reports production-settings warnings that no feature work causes. Items 4-6 are the only diff-scoped part and are the part worth keeping.

**`/fls-dev:plan_security_review`** (`claude_plugins/fls-dev/commands/plan_security_review.md`). A depth-0 fan-out command with the shared recipe (`:14-24`). Inputs: `2. plan.md`, `1. spec.md`, any threat-model notes (`:26-30`). It spawns one `sdd:sdd-worker` that walks a 12-heading scan spec (`:51-101`): data access, AuthN/AuthZ, input handling, CSRF, secrets, dependencies, error disclosure, rate limiting, logging and audit, and a consistency check against the threat model and `CLAUDE.md`. The worker writes `.sdd-work/plan_security_findings.md`. The orchestrator edits `2. plan.md` for clear fixes and adds `> **Security concern:**` callouts for judgement calls (`:105-107`). It then ticks the todo, adds one `(user)` todo per callout (`:130`), commits and pushes (`:134-136`). Why it reads as paranoid: the scan spec is a generic audit list (rate limiting, logging, "new third-party packages ... not widely used", user enumeration) that fires on any plan, whether or not the plan adds an endpoint. It is not framed as "what does this plan add". Every callout becomes a user todo, which is a stall point. The N+1 bullet (`:58`) is a performance concern, not security.

## Evidence of use

Counted over every `todo.md` under `spec_dd/` (done, in progress and next):

| Item | Ticked `[x]` | Unticked `[ ]` |
|---|---|---|
| `threat-model` | 39 lines in 39 files, one of them in-progress `qa-boy-scout-throwaway` | not counted separately |
| `plan_security_review` | 34 files | not counted separately |
| `security-review` (code review, incl. the "re-run after QA fixes" item) | 39 lines in 28 files | not counted separately |
| All three, unticked | n/a | 391 lines in 116 files (this includes the sdd-improve spec itself and everything in `spec_dd/1. next` and `2. in progress` that has a todo) |

- Ticks stop in the summer. Latest ticked `threat-model`: `spec_dd/3. done/2026-06-26_14:55_concrete-implementation-helpers/todo.md:20`. Latest ticked `security-review`: `.../2026-06-18_14:35_more_course_widgets/todo.md:46`. Latest ticked `plan_security_review`: `.../2026-07-17_09:57_support-concrete-project-deployment-1-prod-settings/todo.md:30`. Every spec dated after 2026-07-17 that I could see has all three unticked (for example `2026-08-22_15:42_learner-terminology-rename/todo.md:20,30,45,53`, `2026-09-12_17:33_referral-links/todo.md:20,30,45,53`).
- The ticked ones cluster in May-June 2026 and include tickets with no security surface (`toasts-bottom-viewport`, `layout-spacing-cleanup`, `testing-best-practice-phase-3-*`). That supports "wide": the commands ran on CSS and test-only specs.
- Artifacts in `3. done/`: four threat-model files (`2026-04-28_07:25_testing-best-practice/threat_model.md`, `2026-05-02_18:13_testing-best-practice-phase-3-cleanup-flaky-and-redundant-tests/threat_model.md`, `2026-05-05_08:18_better-registration/threat_model.md`, `2026-06-01_13:49_student-interface-content-widgets-on-brand/threat-model.md`). Specs with a `> **Security concern:**` callout in `2. plan.md`: 4 (`2026-08-21_14:12_make-qa-more-efficient`, `2026-06-01_19:34_student-interface-all-courses-list`, `2026-06-01_12:31_sdd-token-efficiency-and-structure`, `2026-04-29_09:05_testing-best-practice-phase-2-tooling-quick-wins`), 5 hits in total. No security-review output file exists, because the command writes none.
- Real security thinking happened elsewhere, as targeted research on a specific risk: `2026-09-10_09:45_simple-application-forms/research_file_upload_security.md`, `2026-07-09_09:42_support-concrete-project-deployment-master-decomposed-into-specs/research_prod_settings_security_defaults.md`, `2026-03-13_21:21_security-audit/research_security_tools.md`. That is the shape of the replacement: look when the plan adds something risky.
- Caveat: unticked is not proof the commands were never run. Some may have been run and not ticked. The owner's statement and the absence of artifacts after July both agree.

## Removal surface

Delete:
- `claude_plugins/django-stack/commands/threat-model.md`
- `claude_plugins/django-stack/commands/security-review.md`
- `claude_plugins/fls-dev/commands/plan_security_review.md` (it is replaced, see below)

Edit:
- `claude_plugins/sdd/commands/protected/setup_todo_list.md:41` (the "threat-model items" sentence), `:74-76` (section "3. Threat model"), `:84-86` (section "5. Plan security review"), `:99-101` (section "8. Code security review") and `:109` (the "re-run `/ds:security-review`" item). Renumber the sections that follow. The generated `todo.md` is the main reason the removal has to land: all 116 unticked files come from this template.
- `claude_plugins/sdd/commands/next.md:52` (example list names `/ds:threat-model`).
- `claude_plugins/sdd/commands/plan_from_spec.md:23` ("DO NOT mention the security review in the plan file"). Change it to match the new plan-step dimension.
- `claude_plugins/sdd/commands/spec_review.md:55-57` (says the spec is "amended by `/threat-model`").
- `claude_plugins/sdd/commands/README.md:8,9,11,49-52,63-67,73,81-83,98` (workflow overview, "Step 2.5: Threat model", "Step 3.5: Plan security review", "Step 5: Code security review", the QA re-run line).
- `claude_plugins/sdd/README.md:6-7` (lists both command names as fls-dev and ds commands).
- `claude_plugins/fls-dev/README.md:29` (lists `plan_security_review`).
- `claude_plugins/django-stack/README.md:42` (lists `security-review`, `threat-model`).
- `claude_plugins/fls-dev/commands/plan_structure_review.md:8` ("This mirrors `/plan_security_review`"). Reword it.
- Existing `todo.md` files under `spec_dd/1. next/` and `2. in progress/` (13 or so files carry the four items). Leave `3. done/` alone. Command names inside live todos will dangle: `/sdd:next` extracts the command from item text (`next.md:52`), so it needs a rule for a retired command (skip and tick) or those in-flight todos need the lines removed.

Checked and clean (no references): `.claude/` (no settings allow-lists or config entries name these commands), `docs/`, `CLAUDE.md` (only `:81` "without security review", a convention, not a command ref), root `README*`, `spec_dd/1. next/` non-todo files.

Dependency to check before deleting `plan_security_review.md`: it holds a `delete_sdd_work_files.sh` call (`:121`) that other commands also use, so the script stays.

Generic/overlay rule (`CLAUDE.md` "Plugins"): `plan_security_review` lives in `fls-dev` but its scan list is already generic apart from `fls:multi-tenant` (`:57`). `threat-model` and `security-review` are in the generic `django-stack` plugin and name no FLS thing. Deleting them breaks no rule.

## The replacement: a scoped security dimension in the plan step

### Shape

Add one dimension to the review fan-out in `plan_from_spec.md` Step 6 (`:125-136`), which already spawns one `sdd:sdd-worker` per dimension writing `.sdd-work/plan_review_<dim>.md`. The new unit is `plan_review_security`. It needs no new command, no extra commit and no extra todo item, because the plan step already commits (`:155-159`) and ticks itself (`:147-153`). That is the main saving: today's `plan_security_review` costs a separate command, a pre-step rebase, a worker, a commit, a push and a todo round-trip.

The structure check (`plan_structure_review`) is a separate fls-dev command today (`plan_structure_review.md`) with the `> **Structure concern:**` callout and an approval flow. The idea pairs both checks in the plan step. If the owner folds structure in as a second dimension, security follows the same pattern. Keep the callout name `> **Security concern:**` (4 plans already use it) so downstream readers do not change.

### Behaviour (what keeps it narrow)

1. The worker reads the plan and applies the checklist below only to what the plan adds or changes: each new or edited URL, view, model, field, form, template, file field, external call, role or permission. It does not audit existing code and does not read the whole spec for assets and actors.
2. Output is one finding per checklist hit: the plan step, the checklist item, and either a concrete fix or "judgement call".
3. **No hits is the normal result.** It writes `status: ok` with "no new threats" and the orchestrator adds nothing. A plan that adds no endpoint, model, input, file or role produces no findings.
4. Clear fixes: the orchestrator edits the plan directly. Judgement calls: a `> **Security concern:**` callout. To keep it unblocking, this should be batched into the same front-loaded `AskUserQuestion` the rest of the plan step already uses (`plan_from_spec.md:50`), and should not become a `(user)` todo. A callout whose fix is obvious should be applied by default and recorded, not asked about.
5. No severity scale, no rate limiting, no audit-logging, no dependency-reputation checks. These are the "paranoid" items in `plan_security_review.md:82-97`. Dropping them is a deliberate scope cut. `CLAUDE.md` already says "Don't add logging unless asked".

### Checklist

Generic items, safe to carry in the `sdd` plugin command text (no project name, path or value):

| # | Trigger in the plan | Check |
|---|---|---|
| G1 | New or changed view or endpoint | It has an explicit authentication and permission check, and the object is looked up through something that scopes it to the user (not "fetch by id from URL"). Server-side enforcement, not template-hidden buttons. |
| G2 | New state-changing request (POST/PUT/PATCH/DELETE, HTMX equivalents) | CSRF protection is in place (the project's global mechanism counts). |
| G3 | New raw SQL or other ORM escape hatch, or string-built queries | Rejected unless the plan states why the ORM cannot do it. (`CLAUDE.md` Conventions: "ORM only ... without security review".) |
| G4 | New user input (form, query param, path param, JSON body) | It goes through a validating form or serializer. |
| G5 | User-supplied content rendered in a template | Escaped by default; any `safe`, `mark_safe` or markdown path names its sanitiser. |
| G6 | Redirect target taken from input | Checked with `url_has_allowed_host_and_scheme` (named as a pitfall in `registration/SKILL.md:235`). |
| G7 | New file upload or `FileField` | Size, type and content validation named; filenames not user-controlled. |
| G8 | New outbound call to an external service | Credentials come from environment variables; no secret on a model, in a log or in an error response. (`CLAUDE.md`: "Never hardcode credentials".) |
| G9 | New role, permission or "act on behalf of" parameter | Checked server-side; no code path takes a user id from the request to act as that user. |
| G10 | New error handling | No stack traces to the user; no bare `except Exception` that swallows a security-relevant failure (`CLAUDE.md`: "be specific ... Avoid silent failures"). |

Project-supplied items, which must NOT be written into the generic command. They go in a project hook file named by a new key in `.claude/sdd/config.md`, following the existing pattern (`.claude/sdd/config.md:13-15` "Design Hooks / Design check", read by `implement_plan.md:74` with the `config.local.md` override and "blank or absent skips"). Proposed section and key: `## Security Hooks` with `Security checklist: claude_plugins/fls-dev/resources/security_checklist.md` (path would be new). The hook file is an FLS overlay in `fls-dev`, which `CLAUDE.md` says is where FLS content lives. Contents grounded in FLS skills:

| # | Trigger | Check | Source |
|---|---|---|---|
| P1 | New model | Extends `SiteAwareModel` (or `SiteAwareModelBase` with a custom pk), unless the plan justifies why it is global. `site_id` is never set by hand. | `claude_plugins/fls-dev/skills/multi-tenant/SKILL.md:23-26` |
| P2 | Any query or view | Relies on the automatic site-filtering manager; flag any plan step that uses a manager that skips it, or reaches across sites, without a stated reason. | `multi-tenant/SKILL.md:25`; cross-site escape hatch referenced at `registration/SKILL.md:141` |
| P3 | New `FileField` / `ImageField` | Uses a named storage alias with a module-level callable resolved via `storage_for_alias`; the alias matches the bucket for the file's sensitivity (learner-identifying or user-supplied files never in `course_media` or `public`); `upload_to` is namespaced to its alias; a public-bucket key is uuid-derived, never a learner id. | `claude_plugins/fls-dev/skills/file-storage/SKILL.md:49-68,96-108,114-118` |
| P4 | New post-verification registration form | Does not define a field named `user`, `user_id` or `email`; `applies_to` and `is_complete` return strict booleans and are not wrapped in a swallowing `try`; any `?next=` uses `url_has_allowed_host_and_scheme`. | `claude_plugins/fls-dev/skills/registration/SKILL.md:27-28,182-184,214-216,235` |
| P5 | Anything that records or reads consent | `LegalConsent` is append-only; no admin "give consent" action; client IP via `get_client_ip`. | `registration/SKILL.md:133-137,225` |
| P6 | HTMX validation | Returns 422 and relies on the global `hx-headers` CSRF setup (this is G2's project form). | `CLAUDE.md` Conventions |
| P7 | Educator-side views and permissions | Uses the project's educator permission mechanism (educator-interface-5-permissions spec; I did not read it for this note, and the author of the hook file should cite its skill). | assumption, to verify |

The generic command says: "Read `Security checklist` under `## Security Hooks` in `.claude/sdd/config.md` (`config.local.md` wins). Blank, absent file or absent section means run only the generic list." That keeps `sdd` free of FLS words, as `plan_structure_review.md:68-72` already requires of structure checks.

## What happens to the post-implementation code security review

**Drop `/ds:security-review` as a workflow step.** The case:
- Not ticked since June (see Evidence of use).
- Its mechanical half (bandit, pip-audit, detect-secrets, `check --deploy`) scans the whole repo, not the change, and belongs in pre-commit or CI where it runs without anyone remembering to. `CLAUDE.md` already says commits run through pre-commit hooks. The idea file does not ask for CI changes, so this is a pointer, not a requirement. If the owner wants to keep a safety net, moving bandit/detect-secrets to pre-commit config is a separate, small change.
- Its judgement half (auth decorators, ownership, raw SQL, CSRF on new views) is G1-G3 plus P1-P2 and is cheaper at plan time. The code-level version of that half is where the implement step's reviewer fits.

**Should the per-batch reviewer carry the checklist on the diff?** The idea (`idea.md:14-16`) already wants the per-batch reviewer to gain comment/docstring and test-standard checks. The batch loop is in `implement_plan.md:45-50`: one general-purpose sub-agent per batch, committing itself. Whether there is a separate reviewer sub-agent within it, I did not map (my grep of `implement_plan.md` found only the Step 1 "Read and Review the Plan" heading, line 23, and the Design check at `:70-81`). If a per-batch reviewer exists or is added, the cheapest option is to hand it the same checklist (generic G1-G10 plus the hook file) scoped to that batch's diff, and let it report only hits. This costs one extra read per batch, not a new step, and catches what the plan missed (a view added during implementation that was not in the plan). Recommendation: yes, carry the same checklist, diff-scoped, with the same "no hits is normal" rule.

**What is lost by dropping built-in-style review.** Anthropic's built-in `/security-review` (not the same file as `/ds:security-review`; the plugin command is namespaced, so deleting it does not remove the built-in) reviews pending changes on the current branch and covers SQL injection, XSS, authentication and authorization flaws, insecure data handling and dependency vulnerabilities; a third-party FAQ adds command injection, hardcoded secrets, weak cryptography and CORS. Anthropic says it is no replacement for dependency scanning, secret scanning, static analysis or human review. Sources:
- https://www.anthropic.com/news/automate-security-reviews-with-claude-code
- https://support.claude.com/en/articles/11932705-automated-security-reviews-in-claude-code
- https://claudelog.com/faqs/what-is-claude-code-security-review/

What the plan checklist does not give you vs. a code-level review: it sees only what the plan says. Bugs introduced in code that the plan did not describe (an unscoped queryset, an unescaped `|safe`) are invisible to it. The diff-scoped reviewer covers that. A full-diff semantic scan, including dependency CVEs and secrets, is not replaced by anything in the SDD flow; the built-in command remains available ad hoc, and pre-commit/CI is the home for the scanners.

## Open questions for the owner

1. Is the security dimension allowed to ask questions (a `> **Security concern:**` callout resolved during the plan step's front-loaded questions), or should it decide and record, never ask? The idea's goal is fewer stalls, so I lean to "apply the safe default and record it; ask only if the choice changes scope".
2. Where do the two scanner halves go: nowhere, or bandit/detect-secrets into pre-commit? (Out of scope of the idea as written.)
3. Does the dimension sit inside `plan_from_spec` Step 6 as a worker beside the structure check, or does the structure check stay a separate fls-dev command with only security folded in? The idea reads "alongside the structure check".
4. Do the 13 or so in-flight `todo.md` files get their threat/security lines deleted, or should `/sdd:next` skip any item naming a command that no longer exists?
5. Does the per-batch reviewer exist as a separate sub-agent today? I did not find it in `implement_plan.md`, so the implement-step item in the idea may need to create it rather than extend it.
6. P7 (educator permissions) needs its source skill named by whoever writes the hook file; I did not verify it.

status: ok
