# DAST (Dynamic Application Security Testing)

Set up automated dynamic security scanning that tests the running application for vulnerabilities that static analysis cannot detect.

## Why this matters

Static analysis (Bandit, Semgrep, Ruff) catches insecure code patterns, but it cannot find:
- Runtime authentication bypass (e.g. a view that checks permissions incorrectly but passes static review)
- Missing security headers on specific responses
- XSS that only manifests when the template engine renders real data
- CSRF issues in HTMX flows
- Information disclosure through error pages, debug output, or verbose API responses
- Server misconfiguration (exposed admin, directory listing, default credentials)

DAST tools act like an automated attacker - they probe the running app and report what they find. ISO 27001 A.8.29 specifically requires DAST scanning in staging/pre-production environments.

OWASP ZAP's baseline scan catches entire categories of bugs that would otherwise require manual penetration testing.

## When to do this

**After a staging environment exists.** DAST needs to hit a running application - either a CI test server or a staging deployment. This should be prioritised once FLS has:
1. A staging environment (even a CI-launched Django test server counts for baseline scans)
2. The security audit hardening spec completed (so DAST validates the hardening rather than finding obvious gaps)

## In scope

### CI baseline scan (OWASP ZAP)
- ZAP baseline scan against a Django test server started in CI
- Run on every PR to catch regressions
- Custom rules file to suppress expected findings (e.g. CSP report-only if still in that phase)
- SARIF output uploaded to GitHub Code Scanning

### Full scan against staging (OWASP ZAP)
- Weekly or pre-release ZAP full scan against staging
- Authenticated scanning (ZAP logs in as a test user to scan protected views)
- HTML report generated as CI artifact

### Nuclei scanning
- Run Nuclei with Django-specific templates against staging
- Catches known CVE patterns and common misconfigurations
- Complementary to ZAP (different detection approach)

## Research

See `spec_dd/2. in progress/00. security-audit/research_security_tools.md` sections 3 (DAST Tools) for tool evaluation and working CI configurations.
