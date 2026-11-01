---
name: registration
description: Signup, T&C/Privacy consent, legal documents and post-verification registration forms, configured through SiteSignupPolicy. Use when configuring the signup flow (signup, consent, terms, privacy, clickwrap), adding or editing legal documents under legal_docs/, writing a registration form that gates platform access, or querying LegalConsent.
allowed-tools: Read, Grep, Glob
---

# Registration, Consent, and Legal Documents

How to **use and configure** the FLS signup pipeline: per-site signup policy, T&C/Privacy clickwrap consent, legal documents, and additional post-verification registration forms. This covers the public interface only; for internals (middleware wiring, loader checks, cache keys) read the code.

## Key Rules

- Per-site config lives on `SiteSignupPolicy` (one row per site). With no row, each field falls back to the matching global setting (`REQUIRE_NAME`, `REQUIRE_TERMS_ACCEPTANCE`, `ADDITIONAL_REGISTRATION_FORMS`). A row always wins.
- Legal-doc content is read from the **git blob at HEAD**, never the working tree. Editing a file under `legal_docs/` is not enough: commit the change before any environment (including the local dev server) serves it. See "Editing a document" below.
- Every legal-doc file MUST have YAML frontmatter with `version`, `title`, `type`, `effective_date`. Bump `version` on every meaningful edit — business queries key on it.
- `LegalConsent` is append-only and admin-read-only. Never write a code path that updates an existing row, and never register an admin "give consent" action.
- A post-verification form must subclass `forms.Form` (or the convenience base `RegistrationForm`, which inherits from `forms.Form` and provides a default `applies_to` returning `True`). It must implement `is_complete(user)` and `save(user)`, plus `applies_to(user)` if the default isn't right (the protocol requires all three methods on the class; the base class supplies the default `applies_to`). It MUST NOT define a field named `user`, `user_id`, or `email` — those names are forbidden and loading the form list will raise `ImproperlyConfigured`.
- `applies_to` / `is_complete` MUST return strictly `True` or `False` — not `None`, not a truthy/falsy other value.

## Per-Site Configuration: `SiteSignupPolicy`

One row per `Site` controls signup behaviour for that site; see Key Rules for the fallback.

| Field                            | Type      | Settings fallback               | Effect when set |
|----------------------------------|-----------|---------------------------------|-----------------|
| `allow_signups`                  | Boolean   | `ALLOW_SIGN_UPS`                | Master switch — `False` blocks signup entirely |
| `require_name`                   | Boolean   | `REQUIRE_NAME`                  | When effectively `False`, `first_name` becomes optional |
| `require_terms_acceptance`       | Boolean   | `REQUIRE_TERMS_ACCEPTANCE`      | When effectively `True`, the signup form adds `accept_terms` / `accept_privacy` checkboxes — but only if the corresponding legal doc resolves |
| `additional_registration_forms`  | JSONField | `ADDITIONAL_REGISTRATION_FORMS` | List of dotted paths to `forms.Form` subclasses required after email verification |

### How to set it

- **Per site:** Django admin → `Accounts → Site signup policies → Add`. Pick the site, set the fields, save.
- **In a test:** create the row with `SiteSignupPolicy.objects.create(site=…, …)`. To test the global default, flip the setting via the `settings` fixture and create no row.
- **Reading the effective value in code:** use the helpers in `freedom_ls.accounts.utils`:
  - `get_effective_require_name(site)`
  - `get_effective_require_terms_acceptance(site)`
  - `get_effective_additional_registration_forms(site)`

  Don't re-implement the fallback inline.

## Settings

| Setting | Purpose |
|---|---|
| `REQUIRE_NAME` | Global fallback for `SiteSignupPolicy.require_name` when no policy row exists. Default `True`. |
| `REQUIRE_TERMS_ACCEPTANCE` | Global fallback for `SiteSignupPolicy.require_terms_acceptance`. Default `False` in base, `True` in dev. |
| `ADDITIONAL_REGISTRATION_FORMS` | Global fallback for `SiteSignupPolicy.additional_registration_forms`. Default `[]`. |
| `ALLOW_SIGN_UPS` | Global fallback for `SiteSignupPolicy.allow_signups`. |
| `TRUSTED_PROXY_IP_HEADER` | e.g. `"X-Real-IP"`. `None` (default) → fall back to `REMOTE_ADDR`. Read by `get_client_ip` when recording consent. Set this if your app sits behind a trusted proxy or load balancer. |

The signup form is wired via `ACCOUNT_FORMS` / `ACCOUNT_SIGNUP_FIELDS` in `settings_base.py`; leave them alone.

For production deployment of legal documents (manifest builds, `LEGAL_DOCS_MANIFEST_PATH`, etc.), see `docs/deployment-security-checklist.md`.

## Legal Documents

### File location

```
legal_docs/
├── _default/
│   ├── terms.md
│   └── privacy.md
└── <site_domain>/        # optional per-site overrides
    ├── terms.md
    └── privacy.md
```

Lookup order for a given site and doc type:

1. `legal_docs/<site.domain>/<doc_type>.md`
2. `legal_docs/_default/<doc_type>.md`
3. Not found — the signup checkbox for that doc is suppressed, and a startup warning fires if `require_terms_acceptance` is effectively `True`.

### File format

```markdown
---
version: "1.2"
title: "Terms and Conditions"
type: "terms"
effective_date: "2026-04-27"
---

# Heading

Body content here.
```

All four frontmatter keys are required. `version` is a human-readable string used for "has this user accepted v2 or later?" queries — any string is acceptable but stable semver-ish values are easiest to query.

### Editing a document

Legal-doc content is loaded from the **git blob at `HEAD`**, not the working tree, on the local dev server too. Editing the file alone changes nothing user-visible.

Workflow when changing a Terms/Privacy doc:

1. Edit the file under `legal_docs/<site_domain>/` or `legal_docs/_default/` (e.g. `legal_docs/_default/terms.md`).
2. **Bump `version`** in the YAML frontmatter (and update `effective_date` if appropriate). This is what business queries key on.
3. **Commit** — e.g. `uv run git add legal_docs/_default/terms.md && uv run git commit -m "..."`. Until then, `runserver` keeps serving the **previously committed** version: uncommitted, staged and dirty-tree edits all behave the same way.
4. Reload the page on `runserver`. The new version is now what users see and what `LegalConsent.git_hash` records.

### Why "git blob at HEAD"?

The `git_hash` on `LegalConsent` is the blob SHA of the document as the user saw it. Sourcing `legal_docs/` from `HEAD` (or a manifest baked at build time) means a tampered working tree cannot change what users see or what is recorded.

## Consent Tracking: `LegalConsent`

One row is written per `(user, document_type, document_version, git_hash)` consent event. `LegalConsent` is a `SiteAwareModel` — see `fls:multi-tenant` for what that implies for queries.

| Field              | Notes |
|--------------------|-------|
| `site`             | FK to `Site`, set automatically from the user's site at create time. The default manager is site-scoped. |
| `user`             | FK to `accounts.User` |
| `document_type`    | `"terms"` or `"privacy"` |
| `document_version` | From frontmatter at acceptance time |
| `git_hash`         | Blob SHA at acceptance time — cryptographic proof of the exact text |
| `timestamp`        | UTC, set automatically |
| `ip_address`       | Nullable; populated via `get_client_ip(request)` |
| `consent_method`   | Currently `"signup_checkbox"` |

### Append-only

- `LegalConsent` rows are append-only; any attempt to update one raises.
- The admin is read-only: no add, no change, no delete. Do not register "give consent" admin actions or write views that record consent on behalf of a user-id parameter.
- Email rebind does **not** invalidate consent — consent is bound to the `User`, not the email address.

### Querying

`LegalConsent.objects` is the site-scoped default manager — queries return only consents for the current site. To audit consents across sites, use the cross-site escape hatch in `fls:multi-tenant`, not the manager directly.

```python
# All users on the current site who accepted a specific version of the terms
LegalConsent.objects.filter(
    document_type="terms",
    document_version="1.2",
).select_related("user")

# Users who have NOT yet accepted v2.0 of privacy
from django.db.models import Exists, OuterRef
accepted_v2 = LegalConsent.objects.filter(
    user=OuterRef("pk"),
    document_type="privacy",
    document_version="2.0",
)
User.objects.annotate(has_accepted=Exists(accepted_v2)).filter(has_accepted=False)
```

## Additional Registration Forms (Post-Verification)

Add a `forms.Form` subclass to a site's `additional_registration_forms` to require the user to fill it in **after** email verification before they can use the rest of the platform.

### The protocol

```python
@runtime_checkable
class RegistrationFormProtocol(Protocol):
    @classmethod
    def applies_to(cls, user: AbstractBaseUser) -> bool: ...

    @classmethod
    def is_complete(cls, user: AbstractBaseUser) -> bool: ...

    def save(self, user: AbstractBaseUser) -> None: ...
```

- `applies_to` — return `False` for users this form should never block (staff, users without the relevant profile, etc.). If you inherit from `RegistrationForm`, the default returns `True` (form applies to everyone the middleware would otherwise gate); only override when you need to opt users out.
- `is_complete` — return `True` if the data is already on file. The form will not be rendered for users where this is true.
- `save(user)` — persist cleaned data to `user`. The completion view always passes `request.user` in; **the form must not look the user up itself.**

### Forbidden field names

A form that defines a field named `user`, `user_id`, or `email` raises `ImproperlyConfigured` at load time. The completion view always passes `request.user`, and a user-identifying field is a confused-deputy hazard, so this fails loud: fix the field name, don't suppress the error.

### Worked example

```python
# downstream_project/profiles/forms.py
from django import forms

class PhoneNumberForm(forms.Form):
    phone_number = forms.CharField(max_length=20, label="Phone Number")

    @classmethod
    def applies_to(cls, user) -> bool:
        if user.is_superuser or user.is_staff:
            return False
        return hasattr(user, "learner_profile")

    @classmethod
    def is_complete(cls, user) -> bool:
        return bool(getattr(user, "phone_number", "") or "")

    def save(self, user) -> None:
        user.phone_number = self.cleaned_data["phone_number"]
        user.save(update_fields=["phone_number"])
```

Then add `"downstream_project.profiles.forms.PhoneNumberForm"` to the relevant `SiteSignupPolicy.additional_registration_forms` list (via admin or a data migration).

### Behaviour you can rely on

- Any load-time misconfiguration (bad dotted path, target isn't a `Form` subclass / doesn't satisfy the protocol, declares a forbidden user-identifying field) raises `ImproperlyConfigured`. The loader never silently skips — silent skip = a registration step quietly stops gating users.
- Bugs inside your `applies_to` / `is_complete` propagate. **Don't** wrap them in `try: ... except Exception: pass` — silent skip = bypass.
- `applies_to` / `is_complete` must return `True` or `False`. Returning `None` (or any non-bool) raises `TypeError` at gate-check time. The strict check exists because `None` would otherwise be falsy and treated as "does not apply", silently bypassing a gate that should have applied.
- Superusers are always exempt from registration completion checks.

## Testing Patterns

- Use the `mock_site_context` fixture (see `fls:multi-tenant`) anywhere you create site-aware records.
- Create a `SiteSignupPolicy` row for non-default behaviour; to test the global default, flip the setting via the `settings` fixture instead.
- Reuse the test form fixtures in `freedom_ls/accounts/tests/_registration_form_fixtures.py` and `_completion_view_fixtures.py` — don't import private real forms from downstream projects in tests.
- For tests that touch `legal_docs.py`, the `_git_helpers.py` test helper sets up tiny git repos so you don't depend on the actual project HEAD.
- Use `get_client_ip(request)` (not `request.META["REMOTE_ADDR"]`) so trusted-proxy logic is exercised consistently.

## Common Pitfalls

- **Editing a legal doc and not committing.** Content is read from `HEAD` — your edit is invisible until committed.
- **Updating a legal doc without bumping `version`.** The recorded `git_hash` will differ on new consents, but business queries that filter by version won't notice the change.
- **Defining a `user` / `user_id` / `email` field on a registration form.** Loading the form list will raise `ImproperlyConfigured`. Rename the field.
- **Wrapping `applies_to` / `is_complete` in `try/except Exception`.** Bugs there should propagate; silent skip = bypass.
- **Returning `None` (or implicit `return`) from `applies_to` / `is_complete`.** Raises `TypeError`. Always return an explicit `True` or `False`.
- **Adding a `?next=` redirect off the completion view without `url_has_allowed_host_and_scheme`.** Open-redirect bug.
