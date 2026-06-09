# Codebase Feature Inventory: Freedom LS

Research date: 2026-06-09
Purpose: Factual map of what exists in code to validate planned product-doc categories.
Repo root: `/home/sheena/workspace/lms/freedom-ls-worktrees/product-documentation`

---

## 1. Content Editing Workflow

### What exists

- **Git-based file authoring.** All course content lives as Markdown (`.md`) or YAML (`.yaml`/`.yml`) files on disk. UUIDs are written back into frontmatter on first `content_save`, creating a stable identifier per file that survives editing.
  - `freedom_ls/content_engine/management/commands/content_save.py`
  - `freedom_ls/content_engine/management/commands/content_validate.py`
  - `freedom_ls/content_engine/management/commands/danger_content_delete.py`
  - `demo_content/` — sample courses demonstrating all content types

- **Pydantic validation layer.** `content_validate` parses all YAML/Markdown through Pydantic models before save. Strict mode (`extra="forbid"`) rejects unknown fields.
  - `freedom_ls/content_engine/schema.py`

- **Management command workflow:** `content_save <path> <site_name>` scans, validates, and upserts to the database in a single atomic transaction. Re-running the command is idempotent (update-or-create by UUID).

- **Content types defined:** `TOPIC`, `ACTIVITY`, `FORM`, `COURSE`, `COURSE_PART`, `FORM_PAGE`, `FORM_QUESTION`, `FORM_CONTENT`
  - `freedom_ls/content_engine/models.py`
  - `freedom_ls/content_engine/schema.py`

- **Markdown pipeline.** Content is rendered through `render_markdown()`: python-markdown → nh3 sanitiser (allowlist) → django-cotton component compilation → Django template render.
  - `freedom_ls/markdown_rendering/markdown_utils.py`
  - Allowed cotton tags configured in `config/settings_base.py` (`MARKDOWN_ALLOWED_TAGS`)

- **Content widgets (cotton components):**
  - `c-youtube`, `c-picture` (with lightbox), `c-callout`, `c-content-link`, `c-pdf-embed`, `c-file-download`, `c-pull-quote`, `c-equation`, `c-image-grid`, `c-table`, `c-code-block`
  - Template files: `freedom_ls/content_engine/templates/cotton/`

- **File assets** (images, PDFs, audio, video) uploaded and stored via `content_save` alongside text content.
  - `File` model: `freedom_ls/content_engine/models.py`

- **Obsidian-compatible image syntax.** `markdown_translate()` in `content_save.py` converts `![[image.jpg]]` and `![[image.jpg | title]]` to `<c-picture>` tags automatically at save time.

- **Legal docs (terms / privacy) read from git blob at HEAD** — tamper-resistant; git hash recorded on consent. Production mode uses a pre-built manifest if `.git` is absent.
  - `freedom_ls/accounts/management/commands/build_legal_docs_manifest.py`
  - `docs/deployment-security-checklist.md` section 11

### Gaps / Unknowns

- No GUI editor; content editing requires direct file editing + CLI `content_save`. No admin-side content authoring. This is by design (git-based) but should be noted clearly.
- "AI-driven content development" is not a code feature — it is a workflow affordance (authors can use AI tools to write markdown). No AI integration exists in the codebase.
- No concept of content versioning / diff history beyond what git provides.

---

## 2. Authentication

### What exists

- **Custom site-aware User model.** Email-based login (no username). UUID PK via `SiteAwareModelBase`.
  - `freedom_ls/accounts/models.py` — `User`, `UserManager`

- **Email address is the login identifier.** `USERNAME_FIELD = "email"`, `ACCOUNT_LOGIN_METHODS = {"email"}` in settings.

- **Mandatory email verification.** `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` via allauth. Login on email confirmation is enabled.
  - `config/settings_base.py`

- **Registration policy per site** (`SiteSignupPolicy`): `allow_signups`, `require_name`, `require_terms_acceptance`, `additional_registration_forms` (JSONField list of dotted-path form class strings).
  - `freedom_ls/accounts/models.py`

- **Post-registration completion step.** `RegistrationCompletionMiddleware` intercepts authenticated users who have incomplete additional registration forms and redirects to `complete_registration` view.
  - `freedom_ls/accounts/views.py`
  - `freedom_ls/accounts/middleware.py` (inferred from middleware list in settings)

- **Terms/Privacy consent recording.** `LegalConsent` model is append-only; records document_type, document_version, git_hash, timestamp, IP, consent_method.
  - `freedom_ls/accounts/models.py`

- **Profile editing.** `edit_profile` view — first name, last name editable. URL: `accounts:account_profile`.
  - `freedom_ls/accounts/urls.py`, `freedom_ls/accounts/views.py`

- **Brute-force protection.** django-axes configured: 5 failures per IP/username triggers 1-hour lockout. Resets on success.
  - `config/settings_base.py` (`AXES_FAILURE_LIMIT`, `AXES_COOLOFF_TIME`)

- **Signup rate limiting.** `ACCOUNT_RATE_LIMITS = {"signup": "5/m/ip,3/m/key"}`.

- **Email enumeration prevention.** `ACCOUNT_PREVENT_ENUMERATION = True`.

- **Argon2 password hashing** (primary hasher, with PBKDF2 fallbacks).
  - `config/settings_base.py`

- **Password strength rules:** minimum 10 characters, common password check, numeric-only check.

- **API client authentication** (`app_authentication`). Separate token-based model for machine-to-machine API access.
  - `freedom_ls/app_authentication/models.py` — `Client` with auto-generated `api_key`

- **Allauth adapter customised** to fire `user.registered` webhook on successful registration.
  - `freedom_ls/accounts/allauth_account_adapter.py`

- **Webhook on registration.** Fires `user.registered` event on new user save.

### Gaps / Unknowns

- **2FA (TOTP/OTP) is NOT present in the codebase.** No allauth MFA app, no django-otp, no 2FA-related models, views, or settings found. The planned doc category claims 2FA exists — it does NOT.
- `additional_registration_forms` mechanism is present in the model but documenting its full extension protocol requires reading `freedom_ls/accounts/registration_forms.py` in detail — not read in this pass.

---

## 3. Learner Experience

### What exists

- **Student dashboard.** Shows current/in-progress courses, recommended courses, completed courses.
  - `freedom_ls/student_interface/views.py` — `dashboard`
  - URLs: `student_interface:dashboard`

- **Course listing page.** All available courses with registration status (registered / not registered / complete).
  - `views.py` — `all_courses`, `student_interface:courses`

- **Course detail page.** Shows learning outcomes, difficulty, estimated duration, description. Start/resume CTA.
  - `views.py` — `course_detail`, `student_interface:course_detail`

- **Self-registration for courses.** `register_for_course` view creates `UserCourseRegistration` and `CourseProgress` records.
  - `student_interface:register_for_course`

- **Sequential item unlock.** Items are BLOCKED until previous items are COMPLETE. First item is always READY. Status constants: BLOCKED, READY, IN_PROGRESS, COMPLETE, FAILED.
  - `freedom_ls/student_interface/utils.py`

- **Course player.** Item-at-index URL pattern: `courses/<slug>/<int:index>/`. Tracks `last_accessed_item` on `CourseProgress` for resume.
  - URLs: `student_interface:view_course_item`

- **Course parts (chapters/sections).** `CoursePart` groups items inside a course. Course parts display COMPLETE/IN_PROGRESS/BLOCKED derived from their children.

- **Multi-page forms.** Full form-filling workflow: start → fill page N → next page → complete.
  - `student_interface:form_start`, `form_fill_page`, `course_form_complete`, `form_submit_and_exit`

- **Resume support.** `last_accessed_item` GenericFK on `CourseProgress`. Bare course URL redirects to last-accessed item.

- **Course finish page.** `student_interface:course_finish`

- **Hard deadline locking.** If a hard deadline has expired for an uncompleted item, it is locked (inaccessible), shown with a lock icon. Soft deadlines show overdue indicator without locking.
  - `freedom_ls/student_management/deadline_utils.py`

- **Course accent palette.** Courses cycle through a 5-slot gradient palette on creation. Drives hero tiles and progress bars.
  - `freedom_ls/content_engine/models.py` — `Course.accent_slot`

- **Course metadata fields.** `learning_outcomes` (array), `difficulty` (beginner/intermediate/advanced/all_levels), `estimated_duration` (DurationField with human display helper), `icon`, `category`, `tags`.

- **Recommended courses.** `RecommendedCourse` model; shown on dashboard.
  - `freedom_ls/student_management/models.py`

- **Quiz feedback.** For QUIZ strategy forms: shows pass/fail, score percentage, and (if `quiz_show_incorrect=True`) reveals incorrect answers on completion.
  - `freedom_ls/student_progress/models.py` — `FormProgress.get_incorrect_quiz_answers()`

### Gaps / Unknowns

- No certificate generation or downloadable completion evidence.
- No discussion/comment features.
- Form strategy `CATEGORY_VALUE_SUM` (scoring categories for surveys/assessments) exists but its learner-facing display was not fully reviewed — needs separate check.

---

## 4. Learner Tracking

### What exists

- **TopicProgress.** Per-user, per-topic record. Fields: `start_time` (auto), `last_accessed_time` (auto-updated), `complete_time`. Unique per user+topic.
  - `freedom_ls/student_progress/models.py`

- **FormProgress.** Per-user, per-form record. Supports multiple attempts (only incomplete or latest is active). Fields: `start_time`, `last_updated_time`, `completed_time`, `scores` (JSON). Methods: `score()`, `passed()`, `quiz_percentage()`, `get_incorrect_quiz_answers()`.
  - `freedom_ls/student_progress/models.py`

- **QuestionAnswer.** Per-answer storage: `selected_options` (M2M to QuestionOption), `text_answer`. One row per question per FormProgress.

- **CourseProgress.** Per-user, per-course. Fields: `start_time`, `last_accessed_time`, `completed_time`, `progress_percentage` (integer, DB-indexed), `last_accessed_item` (GenericFK). Only created on explicit registration.
  - `freedom_ls/student_progress/models.py`

- **Progress percentage auto-calculated.** On `TopicProgress` or `FormProgress` save (when completion field transitions from None to a value), `update_course_progress_on_completion()` recalculates the percentage for all parent courses.

- **`recalculate_progress_percentages` management command.** Recomputes all percentages from scratch.
  - `freedom_ls/student_progress/management/commands/recalculate_progress_percentages.py`

- **Admin visibility.** `FormProgress`, `TopicProgress`, `CourseProgress` are all registered in Django admin with full read access and search.
  - `freedom_ls/student_progress/admin.py`

### Gaps / Unknowns

- XAPI tracking is entirely commented-out placeholder code — not functional.
  - `freedom_ls/xapi_learning_record_store/models.py` — all code is commented out
  - `freedom_ls/xapi_learning_record_store/views.py` — exists but not inspected in detail
- No time-on-task recording (no duration field on TopicProgress).
- No score/grade export functionality.

---

## 5. Educator Interface

### What exists

- **Single-page panel-framework interface** at `educator_interface:interface`. All navigation is HTMX-driven; the panel framework handles OOB sidebar/breadcrumb updates.
  - `freedom_ls/educator_interface/views.py`
  - `freedom_ls/panel_framework/` — shared framework for panel-based admin views

- **Three sections: Cohorts, Users, Courses.**

- **Cohorts view.**
  - List with student count and registered courses.
  - Detail: Name, student members list, course registrations list.
  - Create/Delete cohort actions.
  - **Course Progress tab** — paginated matrix of students × course items showing completion status, quiz scores, pass/fail, deadlines with overdue indicators.
  - Editable cohort name.

- **Users view.**
  - Lists users accessible via cohort membership (educator only sees users in cohorts they have permission on via django-guardian).
  - Detail: name/email, cohort memberships.

- **Courses view.**
  - Lists all courses with active student count, cohort count.
  - Detail: title/category, cohort registrations, direct student registrations.

- **Access control uses django-guardian** object-level permissions. Educators see only cohorts they have `view_cohort` permission on.
  - `freedom_ls/educator_interface/views.py` — `get_objects_for_user`

- **Deadlines visible in course progress matrix.** Cohort deadlines and per-student overrides are both shown.

### Gaps / Unknowns

- No ability to add/remove students from cohorts via the educator interface (admin-only).
- No ability to register cohorts for courses via educator interface (admin-only).
- No educator ability to set deadlines via the interface (admin-only).
- No messaging/email to students from educator interface.
- `educator_interface/admin.py` is empty — no admin registrations for this app.

---

## 6. Admin Interface

### What exists

- **Unfold admin framework** (`unfold` package) providing enhanced UI over Django admin.
  - `config/settings_base.py` — `unfold` installed before `django.contrib.admin`

- **django-guardian** integrated for object-level permissions; `unfold.contrib.guardian` installed.

- **Models registered in admin:**
  - `accounts`: User (with LegalConsent inline), SiteSignupPolicy, LegalConsent (read-only)
  - `content_engine`: Topic, Activity, Course, CoursePart, Form, FormPage, FormContent, FormQuestion, QuestionOption, File, ContentCollectionItem
  - `student_management`: Cohort (with CohortMembership and CohortCourseRegistration inlines), UserCourseRegistration (with StudentDeadline inline), CohortCourseRegistration (with CohortDeadline and UserCohortDeadlineOverride inlines), CohortDeadline, StudentDeadline, UserCohortDeadlineOverride, RecommendedCourse
  - `student_progress`: FormProgress (with QuestionAnswer inline), QuestionAnswer, TopicProgress, CourseProgress
  - `webhooks`: WebhookEndpoint (with test-send action), WebhookEvent (read-only), WebhookDelivery (read-only, with retry action), WebhookSecret (masked value display)
  - `site_aware_models`: (SiteAwareModelAdmin base class — not a standalone registration)

- **Custom admin URL** configurable via `DJANGO_ADMIN_URL` environment variable.

- **LegalConsent admin is fully read-only** — no add, change, or delete.

- **Cohort admin uses GuardedModelAdmin** (django-guardian integration).

- **Webhook test-send** available as a custom action from the WebhookEndpoint admin detail page.

### Gaps / Unknowns

- `Cohort` admin uses `GuardedModelAdmin` but not the `SiteAwareModelAdmin` base — there is a `@claude` TODO comment noting this needs fixing (`freedom_ls/student_management/admin.py` line 44).
- No custom admin branding configured in settings (UNFOLD block is commented out).
- `app_authentication` admin was not found in the glob results — may be missing or the app is commented out of INSTALLED_APPS.

---

## 7. Security

### What exists

**Dev-time (pre-commit hooks):**
- `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, `check-merge-conflict`, `check-added-large-files` (max 1024KB), `check-ast`, `debug-statements`
- `detect-private-key` (pre-commit-hooks)
- `detect-secrets` with baseline (Yelp detect-secrets v1.5.0)
- `ruff-check --fix` and `ruff-format` (code linting/formatting)
- `bandit` (Python security linter; excludes test files; `--ll` = medium and above)
- `shellcheck` (shell script linting)
- `mypy` (type checking; full project, not filenames)
- `.pre-commit-config.yaml`

**Runtime security:**
- **CSRF.** `CsrfViewMiddleware` in middleware. HTMX headers set globally via `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'`.
- **Content Security Policy.** `ContentSecurityPolicyMiddleware` in middleware; `SECURE_CSP_REPORT_ONLY` configured with allowlist for script-src, style-src, img-src, frame-src (YouTube only).
  - `config/settings_base.py`
- **XSS protection in markdown.** `nh3` sanitiser runs on all markdown content before rendering, with strict allowlist. nh3 is Rust-based, memory-safe.
- **Clickjacking.** `XFrameOptionsMiddleware`, `X_FRAME_OPTIONS = "SAMEORIGIN"`.
- **Login rate limiting / brute-force protection.** django-axes (5 failures → 1h lockout per IP+username).
- **Multi-tenant site isolation.** `SiteAwareModel` and `SiteAwareManager` auto-filter all queries to current site derived from request thread-local. Users are site-scoped.
  - `freedom_ls/site_aware_models/models.py`
- **Session-based authentication** via allauth.
- **Argon2 password hashing** (strongest Django hasher).
- **Django security middleware** (`SecurityMiddleware`) in first position.
- **Whitenoise** for static files — no separate file server needed.
- **SSRF protection on webhook URLs.** Production mode validates URLs are HTTPS and do not resolve to private/loopback IPs.
  - `freedom_ls/webhooks/models.py` — `_validate_url_ssrf()`
- **Webhook secrets encrypted at rest.** `django-fernet-encrypted-fields` for `WebhookSecret.encrypted_value`. Salt configurable via `WEBHOOK_ENCRYPTION_SALT` env var.
- **HSTS deployment checklist** with staged rollout instructions.
  - `docs/deployment-security-checklist.md`
- **GitHub security features checklist** included in deployment docs (Dependabot, secret scanning, branch protection, CodeQL).
- **django-axes** also tracks lockout via `AxesStandaloneBackend` in `AUTHENTICATION_BACKENDS`.

**Deployment security checklist exists as a documented artefact:**
- `docs/deployment-security-checklist.md` covers: server hardening, DB security, TLS, HSTS, firewall, backup encryption, log management, monitoring, Django deployment check, env variables, legal docs, GitHub security.

### Gaps / Unknowns

- CSP is in **report-only** mode (`SECURE_CSP_REPORT_ONLY`), not enforcement mode. This is a known limitation.
- 2FA does not exist (see section 2).
- No explicit rate limiting on API client endpoints (only user signup is rate-limited).

---

## 8. Configuration & Extension

### What exists

**Basic options (settings):**
- `HEADER_LOGO_STATIC_PATH` — logo in nav bar
- `FAVICON_STATIC_PATH` — browser favicon
- `HEADER_TITLE` and `HEADER_TITLE_STYLE` — override nav bar title text and inline CSS
- `EMAIL_LOGO_STATIC_PATH`, `EMAIL_FONT_FAMILY` — email template branding
- `ALLOW_SIGN_UPS` — global signup toggle
- `REQUIRE_TERMS_ACCEPTANCE`, `REQUIRE_NAME` — global registration defaults
- `ADDITIONAL_REGISTRATION_FORMS` — list of extra form classes appended at signup
- `FREEDOM_LS_ICON_SET` — swap icon set (default: `heroicons`)
- `FLS_THEME` — active theme slug (read at Tailwind build time AND at runtime)
- `DEADLINES_ACTIVE` — enable/disable deadline UI features
- `config/settings_base.py`

**Three-tier theming system:**
- **Tier 1 — CSS custom properties (tokens):** Override colour palette, shape, typography tokens in `theme.css`. Zero template changes needed.
- **Tier 2 — Cotton slots and mergeable `class`:** Course cards and rows expose named slots (`eyebrow`, `footer`) and a mergeable `class` attribute for layout changes without forking logic.
- **Tier 3 — Whole-file template shadowing:** Drop a file at the same relative path in your project's theme template directory to replace any leaf template.
- Two bundled themes: `default`, `first_class`
  - `freedom_ls/themes/default/`, `freedom_ls/themes/first_class/`
- Documented in: `docs/how tos/incorperate into another project.md`

**Icon system:**
- Semantic icon names mapped to icon-set-specific glyph names. Active set configurable via `FREEDOM_LS_ICON_SET`.
- Currently only `heroicons` set implemented.
- `freedom_ls/icons/mappings.py`, `freedom_ls/icons/semantic_names.py`

**Custom app extension:**
- FLS is designed as a Django package installable via `git submodule add` + `uv add`.
- Downstream projects add their own Django apps to `INSTALLED_APPS` alongside FLS apps.
- Template loading order gives downstream project templates priority over FLS defaults.
- `docs/how tos/incorperate into another project.md`

**Content extension (MARKDOWN_ALLOWED_TAGS):**
- Downstream projects can register additional cotton component tags with their allowed attributes, making them available as markdown widgets.

**Per-site signup policy:**
- `SiteSignupPolicy` model with `additional_registration_forms` JSONField — pluggable registration forms per site.

### Gaps / Unknowns

- `UNFOLD` settings block is commented out in `settings_base.py` — admin branding (site title, header, colours) is not configured.
- No documented way to add custom educator interface panels (panel framework is internal).
- `TRUSTED_PROXY_IP_HEADER` setting exists but not documented — relevant to deployment behind reverse proxies.

---

## 9. Deployment

### What exists (documented artefacts)

- **Docker Compose deployment** with three containers: Django+Gunicorn (`web`), PostgreSQL (`db`), nginx (static/media).
  - `docs/how tos/DOCKER_DEPLOY.md`
  - Architecture: Whitenoise for static files, nginx for media (100MB max upload, 7-day cache), healthchecks on all containers.

- **CapRover deployment** documented.
  - `docs/how tos/Caprover deploy.md`

- **Tailwind build is required before deployment.** `npm run tailwind_build` must run at image-build time; `FLS_THEME` must be set at build time (not runtime).

- **Management commands for initial data:**
  - `create_site <name> <domain>` — creates a Django Site record
  - `content_save <path> <site_name>` — loads content from disk to database

- **Environment variables documented** for: SECRET_KEY, HOST_DOMAIN, DB_*, HSTS_*, DJANGO_ADMIN_URL, LEGAL_DOCS_MANIFEST_PATH, EMAIL_*, AWS/S3 storage.
  - `docs/deployment-security-checklist.md`

- **S3-compatible storage** supported for media files (AWS_* env vars present).

- **Health check endpoint** at `/health/` used by Docker health checks.

- **Deployment security checklist** exists as a documented artefact covering 12 areas.
  - `docs/deployment-security-checklist.md`

### What does NOT exist (aspirational in idea only)

- **"South African service provider with ISO27001 compliance"** — no code or config for this. The idea mentions it as a deployment strategy detail. Cannot be documented as a code-backed feature.
- **"Backups"** — mentioned in Docker deployment guide as a "production consideration" but no backup scripts or automation exist in the codebase.
- **"Expected scale"** — no load testing data, capacity docs, or scaling configuration in the codebase.

### Gaps / Unknowns

- No `Dockerfile` or `docker-compose.yml` found in the repo root during this pass (they may exist but were not found via glob). The Docker deploy doc references them.
- No CI/CD pipeline configuration found (no `.github/workflows/`).

---

## 10. Future / Partial Work

### RBAC (Role-Based Permissions)

**Status: Models and infrastructure fully built; minimally wired into views.**

- Three role assignment models exist: `SystemRoleAssignment`, `SiteRoleAssignment`, `ObjectRoleAssignment`.
- Role definitions exist for: `site_admin`, `instructor`, `ta`, `system_admin` (no perms yet), `student` (no perms yet), `observer` (no perms yet).
- Management commands: `sync_role_permissions`, `validate_role_permissions`.
- Educator interface uses django-guardian `get_objects_for_user` for cohort access, but **role assignments are not the authoritative source** — permissions must be synced separately.
- Many permissions are listed as `# FUTURE` comments with no implementation.
- `freedom_ls/role_based_permissions/roles.py`, `models.py`, `management/commands/`

### XAPI Tracking

**Status: Placeholder only — entirely commented out.**

- `freedom_ls/xapi_learning_record_store/models.py` — all model code is commented out (rough draft sketch of `LearningExperience` model).
- `freedom_ls/xapi_learning_record_store/views.py` — file exists but not inspected; likely empty.
- The app is NOT in `INSTALLED_APPS`.

### Webhooks

**Status: Fully built and functional.**

- Not "future work" — webhooks are a complete, production-ready feature.
- Three event types: `user.registered`, `course.completed`, `course.registered`.
- HMAC signing or custom auth, Jinja2 body/header templates, circuit breaker (auto-disable on failure threshold), retry on failure, per-site encrypted secrets.
- Admin with test-send capability.
- `freedom_ls/webhooks/`

### Sequential Item Unlock

**Status: Fully built.**

- Items are BLOCKED until all predecessors are COMPLETE. First item starts READY.
- Hard deadlines lock uncompleted items after expiry (most permissive deadline governs).

### Deadlines System

**Status: Models and logic fully built; educator UI shows deadlines read-only.**

- Cohort deadlines, per-student deadlines, per-student overrides for cohort deadlines — all modelled and functional.
- Hard deadlines lock content; soft deadlines show overdue indicators.
- `DEADLINES_ACTIVE` setting to disable the entire feature.
- No deadline-setting UI in educator interface — admin only.

### `SiteGroup` (commented-out User groups)

- `freedom_ls/accounts/models.py` bottom — `SiteGroup` model commented out.
- `SiteGroupAdmin` also commented out.

---

## Major Feature Categories NOT in the Planned Doc List

### Webhooks (fully built — not mentioned in idea)

- Outbound webhook system with HMAC signing, encrypted secrets, retry logic, circuit breaker, Jinja2 templating, admin test-send.
- Three events: `user.registered`, `course.completed`, `course.registered`.
- `freedom_ls/webhooks/`

### Deadline Management System (partially in learner tracking, educator view; deserves its own section)

- Cohort-level deadlines, per-student individual deadlines, per-student overrides within cohort.
- Hard (locks content) vs. soft (shows warning) deadline types.
- Models: `CohortDeadline`, `StudentDeadline`, `UserCohortDeadlineOverride`.
- `freedom_ls/student_management/models.py`, `deadline_utils.py`

### Panel Framework (internal framework, not a product feature per se)

- Reusable HTMX-driven panel/table/navigation framework powering the educator interface.
- `freedom_ls/panel_framework/`

### Icons System (configuration-relevant)

- Pluggable icon set (currently heroicons). Semantic names decouple UI from specific icon library.
- `freedom_ls/icons/`

### Multi-Site Architecture (relevant to Configuration & Security)

- All models are site-scoped. A single FLS installation can serve multiple sites (different domains), each with separate users, content, and settings.
- Site isolation is automatic via `SiteAwareManager`.
- This is a significant architectural feature that should appear in both Security and Configuration docs.
- `freedom_ls/site_aware_models/`

### QA Helpers App

- A dedicated `qa_helpers` app with management commands for seeding test data. Ships as part of the package.
- Not relevant for product docs but worth noting as a developer experience feature.
- `freedom_ls/qa_helpers/`

---

status: ok
reason: Full survey of all 10 planned categories plus 5 additional feature categories identified. Key finding: 2FA does not exist in code (planned doc category is inaccurate). XAPI is a stub. Webhooks are a fully-built feature not in the planned doc list. Multi-site architecture is a significant security/config feature.
