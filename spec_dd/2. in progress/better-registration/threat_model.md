# Threat Model — Better Registration

Threat model for `1. spec.md`. Mapped to OWASP Top 10:2025.

## 1. Assets at risk

| # | Asset | Sensitivity | Notes |
|---|-------|-------------|-------|
| A1 | User credentials (email + password hash) | High | Already protected by `Argon2PasswordHasher` and django-axes lockout. |
| A2 | PII collected at signup (first name, last name) | Medium | Names are PII under GDPR/POPIA. |
| A3 | Additional registration form data (e.g. phone, ID, employer) | High | Project-specific but potentially sensitive personal/regulated data. |
| A4 | `LegalConsent` records (user, doc version, git hash, timestamp, IP, method) | High | Legal evidence — must be tamper-resistant and trustworthy. |
| A5 | IP addresses captured at consent | Medium | PII; must be derived correctly behind proxies and stored lawfully. |
| A6 | Legal document content (terms.md, privacy.md) on disk | Medium | Integrity matters — modifying without an audit trail breaks the legal-evidence story. |
| A7 | Authenticated session (already issued by allauth) | High | Middleware that intercepts every authenticated request can become a session-hijack/redirect surface. |
| A8 | Site→policy binding (`SiteSignupPolicy`) | High | Mis-binding lets a tenant impose another tenant's signup rules or dodge consent capture. |

## 2. Threat actors

- **TA1 — Unauthenticated attacker**: hits the public signup form, legal-doc views, and any pre-auth surface.
- **TA2 — Authenticated learner (curious / malicious)**: has a valid session and is being forced through the completion view.
- **TA3 — Authenticated learner from another site (multi-tenant)**: tries to read/write data belonging to a different `Site`.
- **TA4 — Compromised low-privilege staff** (e.g. `is_staff=True` but not superuser): exempt from `applies_to`, may try to escalate.
- **TA5 — Insider with repo access**: can edit `legal_docs/*` markdown files.
- **TA6 — Operator misconfiguration**: deploys a bad dotted path in `additional_registration_forms`, wrong proxy headers, etc. (Not malicious but a real failure mode for this feature.)
- **TA7 — Bot / automated signup actor**: bulk account creation, credential stuffing, mailbomb-by-signup.

## 3. Attack vectors mapped to OWASP Top 10:2025

### A01:2025 — Broken Access Control

**V1.1 Cross-tenant `LegalConsent` read/write.** `LegalConsent` is `SiteAwareModel`; if any new view, admin inline, or queryset bypasses the site-aware manager, TA3 can read or fabricate consent for another tenant's user.

- **Required control**: All reads/writes use the default site-aware manager; admin inline scoped to current site; FK to `User` validated to belong to the same site as the consent row's site.
- **Status**: Not yet implemented. Spec mandates `SiteAwareModel`. Plan must explicitly verify (a) admin uses `SiteAwareModelAdmin`, (b) any helper that records consent uses `request.user` directly (no IDOR via form-supplied user_id).
- **Gap**: Add to plan: confirm `LegalConsent.site` is set automatically on creation and that no view accepts a user-id parameter when recording consent.

**V1.2 Middleware exempt-URL bypass.** `RegistrationCompletionMiddleware` exempts login/logout/email-verification/static/health/the completion view. A loose pattern (e.g. prefix match on `/accounts/`) lets TA2 reach arbitrary unfinished-registration pages.

- **Required control**: Exempt list is an explicit allow-list of resolved URL names or path prefixes. Match on `request.path` with `startswith` against an exact set, not a substring.
- **Gap**: Spec lists categories but not the matching strategy. Spec/plan should say "exact path or url-name match" and include an explicit list (incl. `account_logout`, `account_email_verification_sent`, `account_confirm_email`, the legal-doc views, `/accounts/complete-registration/`, `/static/`, `/media/`, `/health/`, password reset URLs).
- **Concrete risk to call out**: password-reset URLs must be exempt — otherwise a logged-in user with incomplete registration who follows a reset link is bounced into the completion view and cannot reset.

**V1.3 Middleware bypass via early-return for non-applicable forms.** Spec already short-circuits superusers and `applies_to=False` users. Make sure `is_staff` users are evaluated per-form, not blanket-exempted (spec is correct, but the implementation can drift).

**V1.4 Forced redirect / open-redirect on completion submit.** If the completion view honors a `next` query string blindly, TA2 can craft a phishing redirect.

- **Required control**: Use Django's `url_has_allowed_host_and_scheme` with `request.get_host()` for any post-submit redirect; default to a safe internal URL.
- **Gap**: Not in spec. Add to plan.

**V1.5 Per-form data scope.** Each form's `save(user)` writes to fields on `user` or related objects. A buggy form could accept a `user_id` field and overwrite another user's data.

- **Required control**: The completion view always passes `request.user` to `save()`; the protocol forbids forms from accepting user identifiers. Document this in the form-protocol section of the spec.
- **Gap**: Spec doesn't explicitly say forms must not accept user-identifying fields. Add a sentence.

### A02:2025 — Cryptographic Failures

**V2.1 `git_hash` integrity.** Spec leans on the git hash as "cryptographic proof" of what was accepted. If the hash is computed from the working tree (e.g. via `git hash-object` on a file mutated post-deploy) it can be tampered with.

- **Required control**: Compute the git hash from `HEAD`'s tree (e.g. `git ls-tree HEAD <path>` or via gitpython) at deploy time, not from filesystem contents. Document that the deployed copy of the file is whatever git says. If running outside a checkout (Docker image without `.git`), embed the commit SHA + per-file SHA at build time.
- **Gap**: Spec says "git hash of the file at time of acceptance" without specifying the source of truth. Plan must specify the resolution mechanism and behavior when `.git` isn't present.

**V2.2 IP storage.** `ip_address` is PII under GDPR. Storing it is justified for consent evidence but must be addressed in the privacy policy itself.

- **Required control**: Document the lawful basis (legitimate interest / legal obligation for consent records) in the privacy policy template; define a retention period.
- **Gap**: Add a note to the spec that the default `_default/privacy.md` must mention the IP capture; retention is project-specific but should be called out.

### A03:2025 — Injection

**V3.1 Markdown rendering of legal documents.** Sites host their own `legal_docs/<domain>/...`. If an attacker can drop a markdown file (TA5/TA6), unsanitized rendering lets stored XSS into the legal-doc view, which is loaded inside an authenticated frame.

- **Existing control**: `freedom_ls.content_engine.markdown_utils.render_markdown` uses `nh3.clean` with allowlisted tags/attrs. Reusing it neutralizes XSS.
- **Required control**: The legal-doc view must call `render_markdown` (or an equivalently sanitized renderer), NOT `markdown.markdown(...)|safe`. Pin this in the plan.
- **Gap**: Spec doesn't specify how the markdown is rendered. Add to plan: "render via `freedom_ls.content_engine.markdown_utils.render_markdown`".

**V3.2 Frontmatter parsing.** YAML frontmatter must be parsed with `yaml.safe_load`, not `yaml.load`.

- **Gap**: Plan must specify `safe_load`.

**V3.3 Path traversal on `legal_docs/<site_domain>/...`.** Site domain comes from the `Site` model — DB-controlled. Less risky than user input but a misconfigured `Site.domain` containing `..` or `/` could escape. Defense-in-depth: validate the domain against a regex before using as a path component, and resolve+verify the path stays under `legal_docs/`.

- **Gap**: Add to plan.

**V3.4 Dotted-path import for `additional_registration_forms`.** TA6 / a compromised admin can set the JSONField to `os.system` or another callable. `import_string` will happily import any module.

- **Required control**: After importing, verify the class is a `forms.Form` subclass and implements `applies_to`/`is_complete`/`save`. Refuse otherwise. Catch `ImportError`/`AttributeError` and fail safely (log + skip the form, do NOT crash the request). The admin field for this JSON config should ideally validate against a curated allow-list of form classes.
- **Gap**: Spec describes the loader but not the validation. Add to plan.

### A04:2025 — Insecure Design

**V4.1 Consent unbundling.** Spec already handles this (separate checkboxes, neither pre-ticked). Good.

**V4.2 Replay / fabrication of consent.** A user who never ticked a box could be marked as having consented via a server-side path that bypasses the form (e.g. an admin "give consent" action). Limit the code paths that create `LegalConsent` rows.

- **Required control**: `LegalConsent.objects.create()` is only called from the signup adapter and the (future) re-consent flow. Admin should expose `LegalConsent` as read-only.
- **Status**: Spec says "register `LegalConsent` as read-only inline on User" — good. Plan must enforce read-only at the admin level (`has_add_permission=False`, `has_change_permission=False`, `has_delete_permission=False`).

**V4.3 Session-cached completion status drift.** Spec proposes a hash of the dotted-path list as part of the cache key, and clears the cache on submit. The originally-flagged extension (also invalidate when the user record changes — e.g. on admin edit) was considered and **explicitly de-scoped** on 2026-04-27 in favour of simplicity.

- **Resolution**: Same-request invalidation on admin profile edits is NOT required. If an admin wipes data, the affected user may remain "complete" for the remainder of their current session and only be redirected on the next session. This is an accepted trade-off: incomplete state will surface on next login rather than mid-session. The cache is keyed on the dotted-path list and cleared on completion-view submit; that is the full set of invalidation triggers.

**V4.4 Default-True for `require_terms_acceptance`?** Spec defaults to `False`. From a compliance posture, defaulting to `True` would be safer for new sites. Flagging as a design discussion point — not strictly a security gap, but worth raising with the user.

### A05:2025 — Security Misconfiguration

**V5.1 Missing `legal_docs/_default/*.md`.** If site-specific docs and the default are both missing and `require_terms_acceptance=True`, the signup form has no link target.

- **Required control**: Render a clear server-side error (or refuse to enable the policy) instead of a blank link or 500.
- **Gap**: Spec says fallback exists; plan must specify behavior when both are missing (refuse to render the checkbox / disable signup with a clear admin warning).

**V5.2 Middleware ordering.** `RegistrationCompletionMiddleware` must run after `AuthenticationMiddleware` and `AccountMiddleware`, before view dispatch. Wrong order = either request.user undefined or middleware never fires.

- **Gap**: Plan must specify exact placement in `MIDDLEWARE`.

**V5.3 IP extraction behind proxy.** `request.META["REMOTE_ADDR"]` behind a proxy is the proxy IP. Need a vetted helper that uses `X-Forwarded-For` only when `USE_X_FORWARDED_HOST`/proxy-trust settings are correct.

- **Required control**: Add an `accounts.utils.get_client_ip(request)` helper that reads from a configurable trusted-proxy header, with a sensible default for dev. Document it.
- **Gap**: No existing helper found. Plan must add one.

### A06:2025 — Vulnerable and Outdated Components

- **Status**: allauth, django-axes, nh3 are existing deps. Spec adds no new third-party deps beyond a YAML parser and (possibly) GitPython. Standard `dependabot`/`pip-audit` coverage applies.
- **Gap**: If GitPython is added, capture in the plan and in CI dep-scanning.

### A07:2025 — Identification and Authentication Failures

**V7.1 Removing `email2` weakens nothing** — mandatory verification still gates account use. Good (spec rationale is sound).

**V7.2 Credential stuffing / mass signup (TA7).** Removing a friction field marginally increases signup-bot throughput. django-axes covers login but **not signup**.

- **Required control**: Rate-limit the signup endpoint (e.g. django-ratelimit or allauth's rate limits — `ACCOUNT_RATE_LIMITS` exists in newer allauth). Honeypot field (django-honeypot) is a cheap additional control. CAPTCHA is optional but should be considered, especially if abuse is observed.
- **Gap**: Spec is silent on signup rate-limiting. Plan must add either `ACCOUNT_RATE_LIMITS` for `signup` or document that an existing global limit covers it.

**V7.3 Email enumeration on signup.** Already a concern with the existing flow — submitting an existing email returns a different response than a new one. Out of scope for this spec but worth noting allauth has a setting (`ACCOUNT_PREVENT_ENUMERATION`) that should be confirmed enabled.

- **Gap**: Confirm in plan.

**V7.4 Re-binding email after consent.** If a user changes email after accepting T&Cs, the consent is still valid (it's tied to the user, not the email). Document this so it's not surprising.

### A08:2025 — Software and Data Integrity Failures

**V8.1 Tampering with `legal_docs/*` between deploy and runtime.** If an attacker (TA5 or compromised CI) modifies the file post-deploy, users see different text from what's recorded under that version. Mitigated if `git_hash` is computed from `HEAD` at runtime and compared on render: a mismatch means the file was tampered.

- **Required control**: At read time, recompute the hash and refuse to render if it doesn't match the committed hash for `HEAD:path`. Or simpler: always read the file content via `git show HEAD:legal_docs/...` rather than from the filesystem.
- **Gap**: Spec is silent. Plan must specify whether file-system or git-blob is the source of truth at request time. Strong recommendation: read from git blob.

**V8.2 Pickle / unsafe deserialization.** `additional_registration_forms` is JSON, not pickle. OK.

### A09:2025 — Security Logging and Monitoring Failures

**V9.1 Consent log is the audit log.** `LegalConsent` itself is the audit trail. Make sure it's append-only at the DB layer (no `UPDATE` from app code, only admin-level read access).

- **Required control**: Admin read-only (covered by V4.2). No `update()` calls in app code. Consider a DB-level constraint or a soft-immutable pattern (e.g. raise on `save()` if pk exists).
- **Gap**: Plan should add a `save()` guard against updating existing rows.

**V9.2 No alerting on misconfiguration.** If a deployed site has `require_terms_acceptance=True` but no doc files, every signup silently fails the checkbox link. Log a warning at app startup or on first miss.

- **Gap**: Plan should add a startup check or a one-shot warning log.

### A10:2025 — Server-Side Request Forgery (SSRF)

Not applicable — no outbound URL fetches in this feature. (Webhook system is pre-existing and unchanged.)

## 4. Summary of gaps to feed back into the spec / plan

The following items should be added to the spec (or deferred to the plan with explicit notes) before moving on:

1. **Git-blob source of truth for legal docs** (V2.1, V8.1) — specify that the deployed legal text is read via `git show HEAD:...` (or pinned at build time) rather than the working filesystem; the recorded `git_hash` must match.
2. **Markdown rendering must use `render_markdown` (nh3-sanitized)** (V3.1).
3. **Frontmatter parsed with `yaml.safe_load`** (V3.2).
4. **Path-traversal guard on `<site_domain>` directory lookup** (V3.3).
5. **Dotted-path loader validates target is a `forms.Form` subclass implementing the protocol; failure logs and skips, never 500s** (V3.4).
6. **Middleware exempt list is an explicit allow-list (path or URL-name); password-reset and email-verification flows must be on it** (V1.2).
7. **No-`user_id`-in-form rule explicitly stated; completion view always uses `request.user`** (V1.5).
8. **Open-redirect protection on the completion view's post-submit redirect** (V1.4).
9. **Trusted IP-extraction helper** (V5.3).
10. **Signup rate-limiting** (V7.2) — either via `ACCOUNT_RATE_LIMITS` or a documented existing limit.
11. **`ACCOUNT_PREVENT_ENUMERATION` confirmed enabled** (V7.3).
12. **`LegalConsent` admin is fully read-only and the model rejects updates after creation** (V4.2, V9.1).
13. **Cache-invalidation triggers for completion-status session cache enumerated** (V4.3) — resolved as: dotted-path hash + completion-view submit only. Admin-edit drift accepted; corrects on next session.
14. **Behavior when both site-specific and `_default/` docs are missing is well-defined** (V5.1).
15. **Middleware placement in `MIDDLEWARE` is specified** (V5.2).
16. **Default `_default/privacy.md` mentions IP capture; retention policy noted** (V2.2).
17. **(Discussion) Consider defaulting `require_terms_acceptance` to `True` for safer compliance posture** (V4.4).

These can be addressed by the user in the next checklist step ("Update the spec to close any security gaps surfaced") and/or carried forward into the implementation plan.
