We need full documentation of the Freedom LS product. This should be stored in `docs/product/`.

Docs cover features and functionality, not full implementation details. This is NOT a user manual.

These docs will be used for:
- **Compliance demonstration** — the PRIMARY need. We want to show exactly how we meet compliance expectations. Framework-agnostic for now: state security and data-handling capabilities factually so a reviewer can map them to their own framework (POPIA / ISO 27001 / GDPR / SOC 2) later. Do NOT write claims against a specific framework's clauses.
- **Sales support** — secondary, raw material for sales functions. Keep it light.

All docs are markdown files. DO NOT use cotton components or anything fancy — only standard markdown. Screenshots referenced with plain `![](screenshots/...)`.

# Organisation and conventions

Organise `docs/product/` by **product feature** (the categories below). Compliance-relevant facts are surfaced *within* the relevant feature doc rather than in a separate control-mapped file set, plus one cross-cutting **Security & data handling** doc that a reviewer can read top-to-bottom.

- `docs/product/README.md` — index / entry point, one line per doc, grouped (Product features, Security & data, Configuration, Deployment, Roadmap).
- One file per category, kebab-case lowercase names (e.g. `learner-experience.md`).
- Each file: `# Title`, a `_Last updated: YYYY-MM-DD_` line, a short `## Summary` block (3–5 bullets, the sales-friendly excerpt), then the detail.
- Relative cross-links between docs. No duplication — a fact lives in one doc; others link to it.
- Screenshots in `docs/product/screenshots/`, captured via Playwright MCP (see workflow below).

# Documents

## Content editing workflow
Git-based authoring: all content is markdown/YAML files on disk, version-controlled (timestamps, rollback, diff via git). UUIDs written into frontmatter for stable identity. Pydantic validation on save (`content_save` / `content_validate`, idempotent upsert). No GUI editor (by design). No vendor lock-in (plain markdown). "AI-driven content development" is a workflow affordance (authors can use AI to write markdown), NOT a code feature — describe it as such, do not imply built-in AI.

## Authentication
Email-based login (no usernames), mandatory email verification, per-site signup policy (`SiteSignupPolicy`), additional/custom registration forms, post-registration completion step, profile editing, terms/privacy consent recording (append-only `LegalConsent` with git hash + IP + timestamp). Security hardening: Argon2 hashing, django-axes brute-force lockout (5 fails → 1h), signup rate limiting, email-enumeration prevention, password strength rules. Separate API-client (machine-to-machine) auth.
**Correction:** 2FA does NOT exist in the codebase — do not document it as a current feature. Move it to Future work.

## Learner experience
Dashboard (in-progress / recommended / completed courses), course listing with registration status, course detail (outcomes, difficulty, duration), self-registration for courses, course player with sequential item unlock (items blocked until predecessors complete), course parts/chapters, multi-page forms, resume support, quiz feedback (pass/fail, score, optional reveal of incorrect answers), course finish page. Deadlines surface here (hard deadlines can lock content; soft deadlines show overdue).

## Learner tracking
What the learner did and when. Per-user progress records: `TopicProgress`, `FormProgress` (multi-attempt, scores), `CourseProgress` (percentage, last-accessed item for resume), `QuestionAnswer`. Auto-recalculation of course percentage on completion. Currently simple tracking — no time-on-task duration, no score/grade export. Admin has read visibility of all progress.

## Educator interface
Single-page HTMX panel interface (cohorts / users / courses). Cohort detail with a course-progress matrix (students × items: completion, quiz scores, deadlines). Object-level access via django-guardian (educators only see cohorts they are permissioned on). Note current limits honestly: cohort membership, course registration, and deadline-setting are admin-only (not editable from the educator interface); no messaging.

## Admin interface
Brief writeup. Django admin enhanced with Unfold; django-guardian object permissions. Configurable admin URL (`DJANGO_ADMIN_URL`). `LegalConsent` is read-only. Webhook admin includes test-send. Not a full model/feature list.

## Webhooks (NEW — was missing from original idea)
Outbound webhook system: events `user.registered`, `course.completed`, `course.registered`; HMAC signing or custom auth; per-site secrets encrypted at rest (Fernet); Jinja2 body/header templates; retry + circuit breaker; SSRF protection (HTTPS-only, no private/loopback IPs in production); admin test-send. Compliance-relevant as an outbound third-party data flow.

## Multi-site / tenant isolation (NEW — cross-cutting)
A single FLS install can serve multiple sites (domains), each with isolated users, content, and settings. `SiteAwareModel` / `SiteAwareManager` auto-filter every query to the current site. Surface this in BOTH the Security doc (isolation guarantee) and Configuration doc.

## Security & data handling
Cross-cutting doc a reviewer can read end-to-end.
- **Dev-time:** pre-commit hooks — detect-secrets, detect-private-key, bandit, ruff, mypy, shellcheck, large-file/merge-conflict/AST checks. GitHub security features checklist (Dependabot, secret scanning, branch protection, CodeQL).
- **Runtime:** CSRF, Content Security Policy (note: currently **report-only**, not enforcing), nh3 markdown sanitiser (allowlist), clickjacking protection, HSTS rollout guidance, django-axes, Argon2, Whitenoise, SecurityMiddleware, multi-site isolation, webhook secret encryption at rest + SSRF protection.
- **Data handling (state honestly):** what personal data is collected, where it lives, encryption in transit (TLS/HSTS) and at rest (webhook secrets only — note DB-level encryption is provider-dependent). Topics with little/no code today — incident response, data retention/deletion automation, data-subject-rights tooling — are documented as **current-state**: say plainly what exists, what is manual/operational, and what is not yet built. Do not guess; cross-reference Future work / roadmap.
- A `docs/deployment-security-checklist.md` already exists and should be referenced, not duplicated.
- **ISO 27001 shared-responsibility split** (from `deployment-playbook.md`): Vultr's certification covers physical/infra/hypervisor security; we own OS hardening, encryption (TLS via Caddy, encrypted backups, PostgreSQL SSL), access control, logging/monitoring, backup/DR, incident response, change management (git/PR), vulnerability management (Trivy/Dependabot), and ISMS documentation. Document each honestly as current-state (built vs planned vs operational). **POPIA data residency:** Vultr JNB keeps data in South Africa — a practical compliance advantage, not a legal mandate (per playbook).

## Configuration and extension
Basic branding options (logo, favicon, header title, email branding). Three-tier theming: (1) CSS custom-property tokens, (2) cotton slots + mergeable classes, (3) whole-file template shadowing. Two bundled themes (`default`, `first_class`). Pluggable icon set (`FREEDOM_LS_ICON_SET`, currently heroicons). Custom-app extension model: FLS installs into a host Django project; downstream apps and templates take priority; downstream cotton components can be registered as markdown widgets. Per-site signup policy / additional registration forms.

## Deployment
The V1 deployment strategy is defined in `deployment-playbook.md` (this directory) — that is the **source of truth** for this doc. The repo's older `DOCKER_DEPLOY.md` (nginx) and CapRover how-tos are **superseded** by the playbook; flag them as such, don't document them as current strategy.
- **Target architecture (per playbook):** single **Vultr Johannesburg** VPS — ISO 27001:2022 certified provider with a South African point-of-presence for latency. Docker Compose running **Caddy** (reverse proxy + automatic HTTPS) + Gunicorn + Django 6 + containerized PostgreSQL (named volume). Cloudflare free tier for CDN/WAF. **Ansible** for server provisioning/hardening (Terraform deferred to a later phase). CI/CD: GitHub Actions → GHCR → SSH pull. Background tasks via Django 6's built-in `django-tasks` (DatabaseBackend) — no Celery/Redis at launch.
- **Backups:** `pg_dump` on cron with encrypted offsite sync (Backblaze B2). Documented schedule + tested restores are part of the V1 plan — describe as the strategy, noting which parts are operational vs not-yet-automated.
- **Scale (estimates, not load-tested):** Phase 1 single VPS targets ~50–200 concurrent users / ~1,000 registered students; later phases (separate DB, horizontal, orchestration) are triggered by monitoring data, per the playbook's phased model.
- **Application-level facts the code already ships:** Whitenoise static handling, S3-compatible media storage, health-check endpoint, env-var driven config, required Tailwind build at image-build time.

## Future work
Half-built / planned features, stated honestly:
- **2FA** — not built (was wrongly listed as current).
- **RBAC** — role models and sync/validate commands exist (`SystemRoleAssignment`, `SiteRoleAssignment`, `ObjectRoleAssignment`; roles site_admin/instructor/ta) but minimally wired; many perms are `# FUTURE`; educator access actually flows through django-guardian, not the role system.
- **xAPI tracking** — placeholder only (model code commented out, app not installed).
- **`SiteGroup`** user groups — commented out.
- Educator-interface gaps (membership/registration/deadline editing, messaging).

# IMPORTANT
- Base docs on KNOWN FACTS. DO NOT GUESS or be creative. Where a capability is absent or manual, say so plainly — that is factual, not guessing.
- Don't be wordy. List features/functionality with clear, basic descriptions.
- For visual features, include screenshots captured via Playwright MCP.

# Repeatable workflow (decided: SDD command + step)

This is the first documentation pass; docs must be updated as features ship. Build a reusable mechanism wired into the SDD flow:
- New command `fls-claude-plugin/commands/sdd/update_product_docs.md` (depth-0 orchestrator). It reads the spec/plan to identify affected `docs/product/` files, fans out `fls:sdd-worker` units (one per affected doc section) to draft updates, then synthesises. For visual features it starts a dev server on a free port, captures screenshots via Playwright MCP (reuse `find_available_port.sh`, `compress_screenshots.py`, `kill_runserver.sh` per the `do_qa.md` pattern), then kills the server. Final step delegates the todo tick to `fls:sdd-mechanic`. `mcp__playwright*` in `allowed-tools`.
- Add a documentation step to the SDD todo template (`protected/setup_todo_list.md`), positioned **between QA and Pull request** (code is final and the UI is live for screenshots, and the PR carries the doc changes): one `(cmd)` "Run /update_product_docs" item and one `(user)` "Review updated docs" item. Shift Pull request / Cleanup section numbers accordingly.
- Update `fls-claude-plugin/commands/sdd/README.md` to mention the new step.

# Research artifacts
See `research_doc_structure.md`, `research_codebase_features.md`, `research_sdd_doc_workflow.md`, and `deployment-playbook.md` (the decided V1 deployment architecture) in this directory for the factual basis of the above.
