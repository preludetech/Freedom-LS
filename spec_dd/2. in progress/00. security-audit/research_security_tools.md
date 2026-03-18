# Security Automation Tools: Extended Research

This document extends the research in `research.md` with deeper analysis of security tool categories not yet covered. All tools listed here are genuinely free and open source unless explicitly noted otherwise. Tools are rated for **usefulness** (how much security value they add) and **ease of integration** (effort to set up in our Django/uv/GitHub stack).

Ratings: [5] = essential, [4] = strongly recommended, [3] = useful, [2] = niche, [1] = low value

---

## 1. Claude Code Hooks and Skills for Security Enforcement

Our project already uses Claude Code hooks (see `.claude/settings.json`). This section documents additional security patterns that can be layered on.

### Current State

We already have:
- **PostToolUse hook**: Runs `ruff_fix.sh` after every Edit/Write
- **PreToolUse hook**: Runs ruff, mypy, and pytest before every git commit
- **Deny rules**: Blocks reading `.env` files, writing to `config/settings_prod.py`, `--no-verify` commits, and force pushes

### Additional Security Hook Patterns

#### Pattern 1: PreToolUse Security Guard Script

Block dangerous operations before they execute. Exit code 2 blocks the tool call entirely.

```json
{
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
  ]
}
```

The script reads JSON from stdin containing `tool_name` and `tool_input`. It can:
- Block Bash commands containing `rm -rf`, `curl | sh`, `wget | bash`
- Block writes to migration files (preventing migration tampering)
- Block edits that introduce `raw()`, `extra()`, `RawSQL`, `mark_safe()`, `@csrf_exempt`, `eval()`, `pickle.loads()`
- Block access to private key files, credential files

**Usefulness: [5]** - Deterministic enforcement that cannot be bypassed by the LLM
**Ease of integration: [4]** - Simple bash script, reads JSON via jq

#### Pattern 2: PostToolUse Bandit Scan on Modified Files

Run Bandit on every Python file after it is edited:

```bash
#!/bin/bash
set -euo pipefail
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""')
if [[ "$FILE_PATH" =~ \.py$ ]]; then
    RESULTS=$(uv run bandit -q -ll "$FILE_PATH" 2>&1) || true
    if [[ -n "$RESULTS" ]]; then
        echo "Bandit found issues in $FILE_PATH:"
        echo "$RESULTS"
    fi
fi
exit 0
```

**Usefulness: [4]** - Catches insecure patterns immediately, before they reach commit
**Ease of integration: [5]** - Drop-in script

#### Pattern 3: Permissions Deny List for Security-Sensitive Operations

Extend our existing deny rules:

```json
{
  "deny": [
    "Read(.env)",
    "Read(.env.*)",
    "Read(**/*.pem)",
    "Read(**/*.key)",
    "Write(config/settings_prod.py)",
    "Write(**/migrations/*.py)",
    "Bash(git commit --no-verify:*)",
    "Bash(git push --force:*)",
    "Bash(curl | *)",
    "Bash(wget:*)"
  ]
}
```

**Usefulness: [5]** - Prevents accidental secret exposure and migration tampering
**Ease of integration: [5]** - Configuration only

#### Pattern 4: Claude Code Custom Slash Commands for Security

Create `.claude/commands/security-review.md`:

```markdown
Perform a security review of the current changes:
1. Run `uv run bandit -r . -x ./tests` and analyze results
2. Run `uv run pip-audit` for dependency vulnerabilities
3. Run `detect-secrets scan` for hardcoded secrets
4. Review all new/modified views for auth decorators and ownership checks
5. Check all ORM queries for raw SQL or injection risks
6. Verify CSRF protection on all state-changing views
7. Run `uv run python manage.py check --deploy`
Focus areas: $ARGUMENTS
```

Create `.claude/commands/threat-model.md`:

```markdown
Perform threat modeling for: $ARGUMENTS

1. Identify assets at risk (user data, credentials, sessions, etc.)
2. List threat actors (unauthenticated users, authenticated users, admins, external attackers)
3. Map attack vectors relevant to this feature against OWASP Top 10:2025
4. Define required security controls for each vector
5. Check if existing code implements those controls
6. List any gaps that need to be addressed
```

**Usefulness: [4]** - Standardizes security review process
**Ease of integration: [5]** - Markdown files, zero setup

---

## 2. Django-Specific Security Testing Tools

### django-security-check

- **URL**: https://pypi.org/project/django-security-check/
- **License**: MIT
- **Verdict**: Largely redundant with Django's built-in `manage.py check --deploy` which already covers 15+ security warnings (W001-W022).

**Usefulness: [2]** - Redundant with `manage.py check --deploy`
**Recommendation**: Skip this. Use `manage.py check --deploy --fail-level WARNING` instead.

### Safety (formerly safety-db)

- **URL**: https://github.com/pyupio/safety
- **License**: MIT (tool), but vulnerability database has restrictions
- **Critical change in 2024-2025**: Safety now requires account creation and uses a **reduced vulnerability database** in free tier. Full database costs ~$25/seat/month.

**Usefulness: [2]** - Inferior to pip-audit in the free tier
**Recommendation**: Use pip-audit instead. It is strictly better for free usage.

### manage.py check --deploy (built-in)

- **URL**: https://docs.djangoproject.com/en/5.1/ref/checks/#security
- **License**: BSD (part of Django)
- Validates 15+ security settings against best practices.

**Usefulness: [5]** - Free, maintained by Django core team
**Recommendation**: Essential. Must be a blocking CI check.

### django-axes

- **URL**: https://github.com/jazzband/django-axes
- **License**: MIT
- Brute-force protection for Django authentication. Django has zero built-in brute-force protection.

**Usefulness: [5]**
**Recommendation**: Essential.

### django-ratelimit

- **URL**: https://github.com/jsocol/django-ratelimit
- **License**: Apache-2.0
- Decorator-based rate limiting for any Django view. Complements django-axes for non-auth endpoints.

**Usefulness: [4]** - Complements django-axes for non-auth endpoints
**Recommendation**: Add for password reset, registration, and any API endpoints.

### django-csp

- **URL**: https://github.com/mozilla/django-csp
- **License**: BSD-3
- Note: Django 6.0+ includes native CSP middleware support. Evaluate built-in support first.

**Usefulness: [5]** - Critical XSS mitigation
**Recommendation**: Essential. Evaluate Django 6.x native CSP first.

---

## 3. DAST (Dynamic Application Security Testing) Tools

### OWASP ZAP (Zed Attack Proxy)

- **URL**: https://www.zaproxy.org/
- **License**: Apache-2.0
- The most widely used free DAST tool. Finds XSS, SQL injection, CSRF issues, missing security headers, information disclosure, and more.

**Django integration approaches:**

**Approach 1: Baseline scan in CI** (easiest)
```yaml
- name: Start Django dev server
  run: uv run python manage.py runserver 0.0.0.0:8000 &
  env:
    DJANGO_SETTINGS_MODULE: config.settings.test

- name: ZAP Baseline Scan
  uses: zaproxy/action-baseline@v0.14.0
  with:
    target: "http://localhost:8000"
    rules_file_name: ".zap/rules.tsv"
    cmd_options: "-a"
```

**Approach 2: Full scan against staging** (more thorough)
```bash
docker run -t zaproxy/zap-stable zap-full-scan.py \
  -t https://staging.yourdomain.com \
  -r zap-report.html
```

**Usefulness: [5]** - Catches entire categories of bugs that static analysis cannot
**Ease of integration: [3]** - Requires running the app; baseline scan is easy
**Recommendation**: Essential. Start with baseline scan in CI.

### Nuclei

- **URL**: https://github.com/projectdiscovery/nuclei
- **License**: MIT
- Fast, template-based vulnerability scanner with 8,000+ community-contributed templates. Django-specific templates exist.

**Usefulness: [4]** - Broader coverage than Nikto, good CVE-specific scanning
**Recommendation**: Run against staging for known CVE detection.

### DAST Integration Strategy for Django Dev Workflow

1. **Local development**: Run ZAP in proxy mode while manually testing
2. **CI (every PR)**: ZAP baseline scan against Django test server (~2-5 minutes)
3. **Weekly/pre-release**: ZAP full scan + Nuclei scan against staging
4. **Before deployment**: Nikto against the deployed infrastructure

---

## 4. Infrastructure-as-Code Security Scanning

### Trivy

- **URL**: https://github.com/aquasecurity/trivy
- **License**: Apache-2.0
- All-in-one security scanner for containers, filesystems, git repos, Kubernetes, and IaC.

**Usefulness: [5]** - Swiss-army knife; replaces multiple single-purpose tools
**Ease of integration: [5]** - Single binary, GitHub Action available, SARIF output
**Recommendation**: Essential if using Docker.

### Hadolint

- **URL**: https://github.com/hadolint/hadolint
- **License**: GPL-3.0
- Dockerfile linter against best practices.

**Usefulness: [4]** - Essential for Dockerfile quality
**Recommendation**: Add if using Docker.

### Checkov

- **URL**: https://github.com/bridgecrewio/checkov
- **License**: Apache-2.0
- IaC static analysis for Terraform, CloudFormation, Kubernetes, Helm, Docker.

**Usefulness: [4]** - Comprehensive IaC scanning
**Recommendation**: Add when infrastructure code exists.

---

## 5. GitHub Security Features (Free Tier)

### Free for ALL repositories (public and private)

| Feature | What it does | Action |
|---------|-------------|--------|
| Dependabot Alerts | Detects known vulnerabilities in dependencies | Enable now |
| Dependabot Security Updates | Auto-creates PRs for vulnerable deps | Enable now |
| Dependabot Version Updates | Keeps deps up to date on schedule | Add dependabot.yml |
| Secret Scanning | Scans commits for known secret patterns | Enable now |
| Security Advisories | Private workspace for vulnerability disclosure | Enable now |
| Dependency Graph | Visualizes all dependencies | Enabled by default |

### Free for PUBLIC repositories only

| Feature | What it does | Action |
|---------|-------------|--------|
| CodeQL Analysis | Semantic code analysis for security vulnerabilities | Add GitHub Action |
| Secret Push Protection | Blocks pushes containing detected secrets | Enable |
| Code Scanning (SARIF) | Unified security dashboard from any tool | Already using via SARIF uploads |

**Usefulness: [5]** - All essential and free
**Recommendation**: Enable ALL immediately.

---

## 6. Pre-commit Hooks: Additional Security Hooks

Beyond what's in research.md and our current config:

### Recommended additions

1. **pygrep-hooks: python-no-eval** - blocks `eval()` calls
   ```yaml
   - repo: https://github.com/pre-commit/pygrep-hooks
     rev: v1.10.0
     hooks:
       - id: python-no-eval
   ```

2. **shellcheck** - static analysis for shell scripts (we have `.claude/hooks/`)
   ```yaml
   - repo: https://github.com/shellcheck-py/shellcheck-py
     rev: v0.10.0.1
     hooks:
       - id: shellcheck
   ```

3. **hadolint-docker** - when Docker is added

---

## 7. Compliance-as-Code Tools

### For GDPR / POPIA Compliance

No fully automated tools exist for GDPR/POPIA compliance verification. Best approach:

1. **Custom Django management commands** that verify:
   - All models storing PII have documented personal data fields
   - User data export endpoint exists and works
   - User data deletion cascade works correctly
   - Consent records exist for data processing activities
   - Data retention policies are enforced

2. **`manage.py check --deploy`** covers many ISO 27001 Annex A technical controls
3. **pip-audit** covers supply chain security (ISO 27001 A.12.6.1)
4. **Secret scanning** covers credential management controls
5. **django-axes** covers access control and account lockout controls
6. **Security logging** covers audit logging controls

**Usefulness: [4]** - Practical compliance without framework overhead

---

## 8. SBOM (Software Bill of Materials) Generation

### Syft (recommended)

- **URL**: https://github.com/anchore/syft
- **License**: Apache-2.0
- Generates SBOMs from container images, filesystems, and archives. Supports CycloneDX and SPDX.

```bash
# From filesystem
syft dir:. -o cyclonedx-json > sbom.cdx.json

# From Docker image
syft myapp:latest -o spdx-json > sbom.spdx.json
```

**Usefulness: [5]** - Most versatile SBOM generator
**Recommendation**: Prefer over cyclonedx-python if using Docker.

### Grype (companion to Syft)

- **URL**: https://github.com/anchore/grype
- **License**: Apache-2.0
- Vulnerability scanner that works on SBOMs, container images, and filesystems.

```bash
syft myapp:latest -o cyclonedx-json | grype
```

**Usefulness: [4]** - Comprehensive vulnerability scanning from SBOMs
**Recommendation**: Use alongside Syft for container scanning.

### SBOM Strategy for FLS

1. **Development**: pip-audit for Python dependency scanning
2. **CI/Release**: Generate SBOM with Syft, scan with Grype
3. **Container builds**: `syft myapp:latest -o cyclonedx-json > sbom.cdx.json`
4. **Compliance**: Store SBOMs as release artifacts

---

## Summary: Tool Priority Matrix

### Tier 1: Implement Immediately

| Tool | Category | Action Needed |
|------|----------|---------------|
| `manage.py check --deploy` | Django security | Add as CI blocking check |
| Dependabot alerts + updates | Supply chain | Enable in GitHub settings |
| GitHub secret scanning | Secret detection | Enable in GitHub settings |
| Claude Code security hooks | AI guardrails | Add security-guard.sh PreToolUse hook |
| Claude Code slash commands | AI workflow | Add security-review.md command |

### Tier 2: Implement This Sprint

| Tool | Category | Action Needed |
|------|----------|---------------|
| OWASP ZAP baseline scan | DAST | Add to CI pipeline |
| CodeQL (if public repo) | SAST | Add GitHub Action |
| Trivy | Container/IaC scanning | Add when Docker is used |
| Syft + Grype | SBOM + vuln scanning | Add to release pipeline |
| shellcheck pre-commit | Shell script quality | Add to .pre-commit-config.yaml |

### Tier 3: Implement When Relevant

| Tool | Category | When |
|------|----------|------|
| Hadolint | Dockerfile linting | When Dockerfiles are added |
| Checkov | IaC scanning | When Terraform/K8s configs are added |
| Nuclei | DAST | When staging environment exists |
| django-ratelimit | Rate limiting | When API endpoints are added |

### Tools to Skip

| Tool | Reason |
|------|--------|
| django-security-check | Redundant with `manage.py check --deploy` |
| django-doctor | Freemium; Semgrep covers it for free |
| Safety (free tier) | pip-audit is strictly better for free usage |

---

## Reference URLs

### Claude Code
- Claude Code hooks documentation: https://docs.anthropic.com/en/docs/claude-code/hooks
- Claude Code custom commands: https://docs.anthropic.com/en/docs/claude-code/slash-commands

### Django Security Tools
- django-axes: https://github.com/jazzband/django-axes
- django-csp: https://github.com/mozilla/django-csp
- django-ratelimit: https://github.com/jsocol/django-ratelimit
- django-cors-headers: https://github.com/adamchainz/django-cors-headers
- django-permissions-policy: https://github.com/adamchainz/django-permissions-policy
- Django deployment checklist: https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

### DAST Tools
- OWASP ZAP: https://www.zaproxy.org/
- ZAP GitHub Action: https://github.com/zaproxy/action-baseline
- Nikto: https://github.com/sullo/nikto
- Nuclei: https://github.com/projectdiscovery/nuclei

### Infrastructure Security
- Trivy: https://github.com/aquasecurity/trivy
- Hadolint: https://github.com/hadolint/hadolint
- Checkov: https://github.com/bridgecrewio/checkov

### GitHub Security
- GitHub security features: https://docs.github.com/en/code-security/getting-started/github-security-features
- Dependabot: https://docs.github.com/en/code-security/dependabot
- CodeQL: https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning
- Secret scanning: https://docs.github.com/en/code-security/secret-scanning

### Pre-commit Hooks
- pygrep-hooks: https://github.com/pre-commit/pygrep-hooks
- shellcheck: https://github.com/koalaman/shellcheck

### SBOM Tools
- Syft: https://github.com/anchore/syft
- Grype: https://github.com/anchore/grype
- CycloneDX Python: https://github.com/CycloneDX/cyclonedx-python

### Dependency Scanning
- pip-audit: https://github.com/trailofbits/pip-audit
