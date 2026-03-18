# Securing Django apps built with Claude Code

**AI coding assistants produce insecure code 45–62% of the time**, according to multiple 2024–2025 studies. For a small team using Claude Code to build a Django application, this means security can't be an afterthought — it must be woven into every workflow, from the CLAUDE.md rules that guide code generation to the CI pipeline that catches what slips through. This guide maps the newly released OWASP Top 10:2025 to Django-specific risks, documents the most dangerous patterns AI assistants produce, and provides working configurations for a zero-cost security toolchain. Every recommendation was selected for maximum impact with minimal budget: free tools, open-source middleware, and Claude Code configurations that cost nothing but dramatically reduce your attack surface.

---

## The OWASP Top 10:2025 through a Django lens

The OWASP Top 10 was **updated in November 2025** — the first revision since 2021. The new list analyzed over 175,000 CVE records and introduced significant re-rankings. Security Misconfiguration jumped from #5 to **#2**, a new "Software Supply Chain Failures" category appeared at #3, and an entirely new entry — "Mishandling of Exceptional Conditions" — debuted at #10. SSRF was absorbed into Broken Access Control. These changes directly affect how Django teams should prioritize defenses.

### A01: Broken Access Control (now includes SSRF)

Django's most common access control failure is missing `@login_required` or `@permission_required` decorators on views, followed by Insecure Direct Object Reference (IDOR) bugs where objects are fetched by ID without ownership checks. AI assistants routinely generate views that fetch objects by primary key without verifying the requesting user owns them.

```python
# INSECURE — AI-generated pattern
def edit_profile(request, user_id):
    profile = Profile.objects.get(id=user_id)  # Anyone can edit any profile
    ...

# SECURE — ownership check enforced
@login_required
def edit_profile(request, user_id):
    profile = get_object_or_404(Profile, id=user_id, user=request.user)
    ...
```

For SSRF, validate and allowlist any URLs your application fetches server-side. Block private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`) before making outbound HTTP requests.

### A02: Security Misconfiguration (rose to #2)

This is Django's most exploitable category. The framework ships with sensible defaults, but **a single misconfigured setting can expose your entire application**. The critical misconfigurations are `DEBUG = True` in production (exposes source code, settings, and database info in stack traces), `ALLOWED_HOSTS = ['*']` (enables host header attacks), and a default or committed `SECRET_KEY` (compromises all sessions, CSRF tokens, and password reset links). Run `python manage.py check --deploy` before every deployment — it catches over a dozen security warnings automatically.

### A03: Software Supply Chain Failures (new)

This expanded category now covers vulnerable and compromised dependencies. Django itself had **20+ CVEs in 2024–2025**, with SQL injection variants in `FilteredRelation`, `QuerySet.values()`, and `HasKey` lookups appearing repeatedly. Pin your dependencies, scan them with **pip-audit**, subscribe to the `django-announce` mailing list, and always run a supported Django version.

### A04: Cryptographic Failures

Django defaults to PBKDF2 for password hashing, but **Argon2 is significantly more resistant to GPU-based attacks**. Install `argon2-cffi` and make `Argon2PasswordHasher` your primary hasher. Ensure `SECRET_KEY` is generated with `secrets.token_urlsafe(64)` and stored exclusively in environment variables. Force HTTPS with `SECURE_SSL_REDIRECT = True` and mark all cookies secure.

### A05: Injection (dropped to #5 but still critical)

Django's ORM provides parameterized queries by default, making standard usage safe. However, **Django had at least 8 SQL injection CVEs in 2024–2025** — all in edge-case ORM features like `raw()`, `extra()`, `FilteredRelation`, JSONField's `HasKey` lookup, and `QuerySet.values()` with crafted JSON keys. The rule is absolute: use the ORM for all queries, avoid `raw()` and `extra()`, and if raw SQL is unavoidable, always use parameterized queries with `%s` placeholders and list parameters.

### A06–A10: Remaining categories

**Insecure Design (A06)** — use `django-axes` for brute-force protection and perform threat modeling before implementation. **Authentication Failures (A07)** — configure all four `AUTH_PASSWORD_VALIDATORS`, set minimum length to 12, and use `django-allauth` with MFA. **Software/Data Integrity (A08)** — never use pickle-based sessions; use database-backed or signed-cookie sessions. **Security Logging Failures (A09)** — Django CVE-2025-48432 introduced log injection via unescaped request paths; keep Django updated and log all authentication events. **Mishandling of Exceptional Conditions (A10)** — set `DEBUG = False` in production, create custom error templates, and implement fail-closed exception handling.

---

## Why AI-generated code demands extra scrutiny

The data on AI code security is sobering. Veracode's 2025 study found LLMs chose an insecure method over a secure one **45% of the time** across 80 curated tasks. Cross-site scripting had an **86% failure rate**; log injection hit **88%**. An analysis of 7,703 GitHub files attributed to AI tools found **4,241 CWE instances across 77 vulnerability types**, with Python showing the highest vulnerability rate at 16–18%. Apiiro's enterprise research documented a **10× spike in security findings** from AI-generated code over six months, with privilege escalation paths jumping **322%**.

The most dangerous finding may be psychological: Perry et al. demonstrated that developers using AI assistants wrote "significantly less secure code" while exhibiting a **false sense of security** — rating their insecure solutions as secure. The AI doesn't just introduce bugs; it creates confidence that those bugs don't exist.

### The twelve patterns to watch for

LLMs producing Django code consistently generate these insecure patterns:

- **SQL injection via raw queries** — using f-strings in `User.objects.raw()` instead of parameterized queries or the ORM
- **Hardcoded secrets** — embedding API keys and database passwords directly in `settings.py` or view code
- **Missing input validation** — reading directly from `request.POST` without Django Forms or DRF Serializers
- **XSS via `mark_safe()` or `|safe`** — marking user-controlled content as safe HTML, bypassing Django's auto-escaping
- **Insecure deserialization** — using `pickle.loads()` or `yaml.load()` (unsafe Loader) on untrusted data instead of JSON or `yaml.safe_load()`
- **Path traversal** — joining user-supplied filenames to a base path without resolving and validating the result
- **SSRF** — making server-side HTTP requests to user-supplied URLs without scheme or IP validation
- **`@csrf_exempt` on state-changing views** — LLMs add this decorator to "fix" 403 errors, removing CSRF protection entirely
- **Mass assignment** — using `setattr()` loops or `**request.POST.dict()` to update models, allowing users to set `is_staff` or `is_superuser`
- **Weak random generation** — using Python's `random` module instead of `secrets` for tokens, reset codes, and session identifiers
- **Insecure file uploads** — accepting any file type, using original filenames, and storing files in the web root
- **Removing security controls during refactoring** — AI treats security walls as bugs preventing code from running, often stripping validation, authentication, or middleware to resolve errors

### Real-world failures from AI-assisted development

Multiple startups built primarily with AI coding tools have suffered public security incidents. **Enrichlead** was found "full of newbie-level security flaws" allowing anyone to access paid features or alter data. **Moltbook** leaked **1.5 million API keys and 35,000 email addresses** through a misconfigured database. The **Tea dating app** leaked user selfies, personal data, and EXIF location data. These aren't hypotheticals — they're the documented consequences of trusting AI-generated code without security review.

---

## Prioritized security checklist ranked by impact

This checklist is ordered by the combination of exploitability, impact, and implementation effort. Items at the top protect against the most common and damaging attacks with the least work.

### Tier 1: Do immediately (critical impact, easy to implement)

| Action | Why | How |
|---|---|---|
| Set `DEBUG = False` in production | Exposes source code, settings, DB credentials | Use environment variable: `DEBUG = os.environ.get('DEBUG', 'False') == 'True'` |
| Move `SECRET_KEY` to environment | Compromise = total session/token takeover | `SECRET_KEY = os.environ['DJANGO_SECRET_KEY']` |
| Set `ALLOWED_HOSTS` explicitly | Prevents host header attacks and cache poisoning | `ALLOWED_HOSTS = ['yourdomain.com']` |
| Enable HTTPS settings | Prevents traffic interception | `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True` |
| Install and run pip-audit | Catches known vulnerable dependencies | `pip install pip-audit && pip-audit` |
| Add Bandit to pre-commit | Catches insecure code patterns before commit | See pre-commit config below |
| Run `manage.py check --deploy` | Validates 12+ security settings automatically | Add to CI pipeline and pre-deployment script |

### Tier 2: Do this week (high impact, moderate effort)

| Action | Why | How |
|---|---|---|
| Configure HSTS | Forces browsers to use HTTPS permanently | `SECURE_HSTS_SECONDS = 31536000` (start with 3600, increase after testing) |
| Set up password validators | Prevents weak passwords | Configure all four `AUTH_PASSWORD_VALIDATORS` with min_length=12 |
| Switch to Argon2 hashing | PBKDF2 is vulnerable to GPU attacks | `pip install argon2-cffi`, set as primary `PASSWORD_HASHER` |
| Install django-axes | Blocks brute-force attacks | `pip install django-axes`, configure with `AXES_FAILURE_LIMIT = 5` |
| Add Content Security Policy | Mitigates XSS even when code is vulnerable | Use `django-csp` 4.0 or Django 6.0 native CSP |
| Set up GitHub Actions security pipeline | Automated scanning on every PR | See CI pipeline YAML below |
| Add detect-secrets to pre-commit | Prevents committing API keys and passwords | See pre-commit config below |

### Tier 3: Do this month (important, requires design decisions)

| Action | Why | How |
|---|---|---|
| Implement object-level permissions | Prevents IDOR attacks | Use `django-guardian` or manual ownership checks in every view |
| Set up security logging | Enables incident detection and forensics | Configure `django.security` and `django.request` loggers |
| Add rate limiting to sensitive endpoints | Prevents credential stuffing and abuse | Use `django-ratelimit` decorator on login, registration, password reset |
| Configure CORS properly | Prevents cross-origin attacks | `django-cors-headers` with explicit `CORS_ALLOWED_ORIGINS` |
| Add Permissions-Policy headers | Disables unnecessary browser features | `django-permissions-policy` with empty lists for camera, microphone, geolocation |
| Change default admin URL | Reduces automated attack surface | `path('your-secret-path/', admin.site.urls)` |
| Implement file upload validation | Prevents malicious file uploads | Allowlist extensions, limit size, randomize filenames with `uuid4()` |

---

## Claude Code workflow for secure Django development

Claude Code's **CLAUDE.md** is the highest-leverage security configuration point available. It loads automatically at session start, providing persistent rules that guide every code generation task. Combined with **hooks** (deterministic shell commands that run at lifecycle points) and **prompt patterns** (techniques that reduce insecure output by 41–68% in research), these three mechanisms form a layered defense.

### CLAUDE.md security rules

Keep CLAUDE.md concise — the model reliably follows approximately **150–200 instructions total** (the system prompt already contains ~50). Use "MUST", "NEVER", and "IMPORTANT:" for non-negotiable rules. Store detailed security documentation in separate files (`docs/security_requirements.md`) and reference them from CLAUDE.md so Claude loads them on demand.

```markdown
# Project: [Your Django Project]
Django 5.x web application with PostgreSQL. Python 3.12, managed with uv.

## Commands
- `uv run python manage.py test` — Run all tests
- `uv run python manage.py test app.tests.TestClass.test_method` — Single test
- `uv run ruff check . && uv run ruff format .` — Lint and format
- `uv run bandit -r . -x ./tests` — Security scan
- `uv run pip-audit` — Dependency vulnerability check
- `uv run python manage.py check --deploy` — Deployment security checklist

## Architecture
- `apps/` — Django applications
- `config/` — Settings (base.py, local.py, production.py), URLs, WSGI
- `templates/` — Django templates
- See `docs/architecture.md` for detailed overview

## Security Rules
IMPORTANT: These rules are NON-NEGOTIABLE for ALL code generation.

### Data & Queries
- MUST use Django ORM exclusively. NEVER use raw SQL with string formatting.
- If raw SQL is required, MUST use parameterized queries with %s and list params.
- MUST validate ALL user input via Django Forms or DRF Serializers.
- NEVER use `mark_safe()` or `|safe` on user-supplied content.
- NEVER use `pickle.loads()`, `eval()`, or `yaml.load()` on untrusted data.
- NEVER pass `**request.POST.dict()` or `**request.GET.dict()` to ORM methods.

### Auth & Access
- MUST use `@login_required` or `LoginRequiredMixin` on ALL views. Default deny.
- MUST verify object ownership in every view that accesses user-specific data.
- NEVER use `@csrf_exempt` on state-changing views.
- NEVER roll custom authentication. Use Django's auth system or django-allauth.

### Secrets & Config
- NEVER hardcode credentials, API keys, tokens, or secrets in code.
- NEVER modify .env files, production settings, or migration files.
- Use `secrets.token_urlsafe()` for all token generation, NEVER `random`.

### Files
- MUST validate file uploads: allowlist extensions, check size, randomize names.
- NEVER use user-supplied filenames for storage. Use `uuid4()`.

## Workflow
- Run `uv run ruff check . && uv run python manage.py test` before completing any task.
- Create a new branch for each feature. Never commit to main directly.
- See `docs/security_requirements.md` for threat model and compliance details.
```

### Hooks for deterministic security enforcement

Unlike CLAUDE.md rules (which are advisory), hooks are **deterministic** — they execute shell commands at specific lifecycle points and can block operations with exit code 2. Configure them in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/security-guard.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/post-edit-scan.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ruff check . && uv run python manage.py test --failfast 2>&1 | tail -20"
          }
        ]
      }
    ]
  },
  "permissions": {
    "allow": ["Bash(uv run *)", "Bash(python manage.py test *)"],
    "deny": ["Read(./.env*)", "Read(./**/*.pem)", "Bash(curl:*)", "Bash(wget:*)"]
  }
}
```

The **PreToolUse** hook (`.claude/hooks/security-guard.sh`) blocks dangerous operations before they execute:

```bash
#!/bin/bash
set -euo pipefail
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input')

if [[ "$TOOL_NAME" == "Bash" ]]; then
    COMMAND=$(echo "$TOOL_INPUT" | jq -r '.command')
    # Block destructive and exfiltration commands
    if [[ "$COMMAND" =~ rm\ -rf ]] || [[ "$COMMAND" =~ git\ push.*--force ]]; then
        echo "BLOCKED: Destructive command." >&2; exit 2
    fi
    if [[ "$COMMAND" =~ \.env ]] || [[ "$COMMAND" =~ id_rsa ]]; then
        echo "BLOCKED: Access to secrets not permitted." >&2; exit 2
    fi
fi

if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
    FILE_PATH=$(echo "$TOOL_INPUT" | jq -r '.file_path // .path // ""')
    if [[ "$FILE_PATH" =~ \.env ]] || [[ "$FILE_PATH" =~ settings/production ]]; then
        echo "BLOCKED: Cannot modify $FILE_PATH." >&2; exit 2
    fi
fi
exit 0
```

The **PostToolUse** hook runs Bandit on every modified Python file automatically:

```bash
#!/bin/bash
set -euo pipefail
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""')
if [[ "$FILE_PATH" =~ \.py$ ]]; then
    RESULTS=$(bandit -q -ll "$FILE_PATH" 2>&1) || true
    if [[ -n "$RESULTS" ]]; then
        echo "⚠ Bandit found issues in $FILE_PATH:"
        echo "$RESULTS"
    fi
fi
exit 0
```

### Prompt patterns that reduce vulnerabilities

Academic research confirms specific prompting techniques measurably reduce insecure code generation:

**Recursive Criticism and Improvement (RCI)** is the most effective technique, reducing vulnerabilities by **41–68%**. After Claude generates code, prompt it to review its own output:

> "Review the code you just wrote for security vulnerabilities. Specifically check for: injection risks in any database queries, missing authentication on views, hardcoded secrets, unsafe deserialization, and XSS via mark_safe or |safe. Fix any issues found and explain each fix."

**Security-focused persona prompting** changes how the model approaches problems:

> "Act as a senior Django security engineer. Implement a user registration endpoint with proper password hashing via Django's auth system, input validation via DRF serializers, rate limiting, and protection against OWASP Top 10 vulnerabilities. Explain your security decisions."

**Threat modeling before implementation** forces security-first design:

> "Before writing code for this feature: (1) List the assets, threat actors, and attack vectors. (2) Identify relevant OWASP Top 10 risks. (3) Define required security controls. (4) Then implement with those controls built in."

Create a reusable slash command at `.claude/commands/security-review.md`:

```markdown
Perform a security review of the current changes:
1. Run `bandit -r . -x ./tests` and analyze results
2. Run `pip-audit` for dependency vulnerabilities
3. Run `detect-secrets scan` for hardcoded secrets
4. Review all new/modified views for auth decorators
5. Check all ORM queries for injection risks
6. Verify CSRF protection on all forms
7. Run `python manage.py check --deploy`
Focus areas: $ARGUMENTS
```

---

## Recommended free tools with justification

### Static analysis

**Bandit** (v1.8.6, Apache-2.0) is the standard Python security linter with **47+ AST-based checks** covering injection, cryptography, XSS, and hardcoded credentials. It integrates natively with pre-commit and produces SARIF output for GitHub Code Scanning. **Ruff** (MIT) reimplements all Bandit rules under its `S` prefix and runs **10–100× faster** — use it for real-time linting during development and Bandit in CI for authoritative results. **Semgrep** (community rules free) provides a dedicated Django ruleset (`semgrep --config p/django`) with framework-native taint tracking that traces data flows through the ORM, views, and templates with an **84% true positive rate**.

### Dependency scanning

**pip-audit** (v2.10.0, Apache-2.0) is the clear choice for budget-conscious teams. Developed by Trail of Bits with Google backing, it requires **no account, no API key**, and checks against the Python Packaging Advisory Database and OSV. It supports auto-fix (`--fix`), multiple output formats including SARIF, and has a first-party GitHub Action. Safety (the main alternative) now requires account creation and limits its free tier to a reduced vulnerability database — its full database costs **$25/seat/month**.

### Secret detection

**Gitleaks** (v8.22.1, MIT) provides fast pre-commit scanning with **100+ regex patterns**. **detect-secrets** (v1.5.0, Apache-2.0) from Yelp adds baseline management — scan your repo once, audit the results, and future scans only flag new secrets. Use both: Gitleaks for speed in pre-commit, detect-secrets for comprehensive auditing.

### Django security middleware

**django-axes** (v8.3.1, MIT) blocks brute-force attacks after configurable failed login attempts — essential since Django has no built-in rate limiting on authentication. **django-csp** (v4.0, BSD-3) adds Content Security Policy headers that mitigate XSS even when code is vulnerable; note that Django 6.0 includes native CSP support, so evaluate whether you need the third-party package. **django-permissions-policy** (v4.28.0, MIT) disables dangerous browser features like camera, microphone, and geolocation access. **django-cors-headers** (MIT) provides proper CORS configuration with explicit origin allowlisting.

---

## Working configuration files

### Pre-commit hooks (`.pre-commit-config.yaml`)

```yaml
# .pre-commit-config.yaml
repos:
  # Bandit: Python security static analysis
  - repo: https://github.com/PyCQA/bandit
    rev: "1.8.6"
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml", "-ll", "-x", "./tests"]
        additional_dependencies: ["bandit[toml]"]

  # detect-secrets: Prevent committing secrets
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ["--baseline", ".secrets.baseline"]

  # Gitleaks: Fast secret scanning
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.22.1
    hooks:
      - id: gitleaks

  # Ruff: Fast linting with Bandit security rules
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: ["--select", "S", "--fix"]
      - id: ruff-format
```

**Setup commands:**

```bash
pip install pre-commit detect-secrets
detect-secrets scan > .secrets.baseline    # Create initial baseline
detect-secrets audit .secrets.baseline     # Review and mark false positives
pre-commit install                         # Activate hooks
pre-commit run --all-files                 # Initial scan of existing code
```

### GitHub Actions CI pipeline (`.github/workflows/security.yml`)

```yaml
name: Security Scanning

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"  # Weekly Monday scan

permissions:
  contents: read
  security-events: write

jobs:
  bandit:
    name: Bandit SAST
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "bandit[sarif]"
      - run: bandit -r . -x ./tests -f sarif -o bandit.sarif --severity-level medium || true
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: bandit.sarif

  pip-audit:
    name: Dependency Audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - uses: pypa/gh-action-pip-audit@v1.1.0

  semgrep:
    name: Semgrep SAST
    runs-on: ubuntu-latest
    container:
      image: semgrep/semgrep
    steps:
      - uses: actions/checkout@v4
      - run: semgrep scan --config auto --sarif -o semgrep.sarif
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: semgrep.sarif

  gitleaks:
    name: Secret Scanning
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  django-check:
    name: Django Deployment Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python manage.py check --deploy --fail-level WARNING
        env:
          DJANGO_SETTINGS_MODULE: config.settings.production
          DJANGO_SECRET_KEY: "ci-test-key-not-for-production"  # pragma: allowlist secret
          DATABASE_URL: "sqlite:///ci-test.db"
```

Add Dependabot for automated dependency updates (`.github/dependabot.yml`):

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

### Django settings.py security hardening

```python
import os

# ── Core Security ──────────────────────────────────────────────
DEBUG = False                                          # W018: Never True in production
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]           # W009: Never use default
ALLOWED_HOSTS = ["yourdomain.com", "www.yourdomain.com"]  # Never use ['*']

# ── HTTPS / TLS ────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True                             # W008: Redirect HTTP → HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # If behind proxy

# ── HSTS (HTTP Strict Transport Security) ──────────────────────
SECURE_HSTS_SECONDS = 31536000                         # W004: 1 year (start with 3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True                  # W005: Apply to subdomains
SECURE_HSTS_PRELOAD = True                             # W021: Enable preload list

# ── Cookie Security ────────────────────────────────────────────
SESSION_COOKIE_SECURE = True                           # W012: HTTPS only
SESSION_COOKIE_HTTPONLY = True                          # Default; blocks JS access
SESSION_COOKIE_SAMESITE = "Lax"                        # Prevents CSRF via cross-site
SESSION_COOKIE_AGE = 1209600                           # 2 weeks
CSRF_COOKIE_SECURE = True                              # W016: HTTPS only
CSRF_COOKIE_SAMESITE = "Lax"

# ── Content Security ───────────────────────────────────────────
X_FRAME_OPTIONS = "DENY"                               # W019: Prevent clickjacking
SECURE_CONTENT_TYPE_NOSNIFF = True                     # W006: Prevent MIME sniffing
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"  # W022
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"      # Django 4.0+

# ── Password Security ──────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
     "OPTIONS": {"max_similarity": 0.7}},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Argon2 primary hasher (pip install argon2-cffi)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# ── Middleware (order matters) ─────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",       # W001: Must be first
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",                # Before CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",                         # django-csp
    "django_permissions_policy.PermissionsPolicyMiddleware",
    "axes.middleware.AxesMiddleware",                       # Must be last
]

# ── Upload Limits ──────────────────────────────────────────────
DATA_UPLOAD_MAX_MEMORY_SIZE = 5_242_880                # 5 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5_242_880                # 5 MB

# ── Security Logging ───────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "security_file": {
            "class": "logging.FileHandler",
            "filename": "/var/log/django/security.log",
        },
    },
    "loggers": {
        "django.security": {"handlers": ["security_file"], "level": "INFO"},
        "django.request": {"handlers": ["security_file"], "level": "WARNING"},
    },
}

# ── Database (credentials from environment) ────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}
```

Each `W0XX` comment corresponds to the specific `security.W0XX` warning that `manage.py check --deploy` validates. Configure all of them and the deployment check will pass clean.

---

## Django misconfigurations that attackers find first

Beyond the settings checklist, these are the misconfigurations that consistently appear in penetration test findings and Django security audits:

**Admin at `/admin/`** is the most predictable target for automated scanners. Change it to an unpredictable path: `path('manage-8f3k2x/', admin.site.urls)`. This is security through obscurity — it won't stop a determined attacker — but it eliminates a massive volume of automated probes.

**CORS set to `CORS_ALLOW_ALL_ORIGINS = True`** effectively disables same-origin policy. Always use an explicit allowlist in `CORS_ALLOWED_ORIGINS`. Similarly, watch for `CORS_ALLOW_CREDENTIALS = True` combined with permissive origins, which enables cross-origin session theft.

**Missing CSP headers** mean any XSS vulnerability has maximum impact. Even a basic `default-src 'self'` policy drastically reduces the damage an XSS exploit can cause. Start in report-only mode to identify violations, then enforce. With django-csp 4.0's new dict-based configuration:

```python
from csp.constants import SELF, NONCE, NONE

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "script-src": [SELF, NONCE],
        "style-src": [SELF, NONCE],
        "img-src": [SELF, "data:"],
        "frame-ancestors": [NONE],
    },
}
```

**No brute-force protection** on login endpoints allows credential stuffing attacks to run unchecked. Django has no built-in rate limiting. Install `django-axes` with a 5-attempt lockout and 1-hour cooldown as your minimum viable defense.

**Serving user uploads from the same origin** as the application allows uploaded files to execute in the application's security context. If budget allows, serve `MEDIA_URL` from a completely separate domain (not a subdomain).

**Pickle-based session serializer** is a remote code execution vector. Django defaults to JSON serialization since version 1.6, but some tutorials and AI-generated code switch to pickle for convenience. Verify your `SESSION_SERIALIZER` is set to `django.contrib.sessions.serializers.JSONSerializer` or left at the default.

---

## Conclusion

The security landscape for Django teams using AI coding assistants in 2025–2026 comes down to a simple principle: **treat AI-generated code with the same suspicion you'd give an untrusted third-party library**. The research is clear that LLMs produce insecure code roughly half the time, that developers over-trust AI output, and that the most dangerous vulnerabilities are architectural — the kind that static analysis tools miss.

The three highest-leverage actions for a small team are: (1) writing a tight CLAUDE.md with non-negotiable security rules and enforcing them with deterministic hooks, (2) installing the free pre-commit + CI pipeline described above so that Bandit, pip-audit, Gitleaks, and Semgrep catch what slips through, and (3) using RCI prompting — asking Claude to review its own code for security issues after every implementation — which research shows reduces vulnerabilities by up to 68%.

The OWASP Top 10:2025 elevation of Security Misconfiguration to #2 is a direct signal to Django teams: the `settings.py` hardening checklist in this guide isn't optional. A single misconfigured setting — `DEBUG = True`, an exposed `SECRET_KEY`, a wildcard in `ALLOWED_HOSTS` — can render every other security measure irrelevant. Run `manage.py check --deploy` on every deployment and make it a blocking CI check. The 20+ Django CVEs from 2024–2025 also demonstrate that keeping Django updated is itself a critical security control, not just good housekeeping.
