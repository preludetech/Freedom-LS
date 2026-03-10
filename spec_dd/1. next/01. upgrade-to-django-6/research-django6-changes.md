# Django 6.0 Research: Release Notes, Breaking Changes, and Migration Guide

Research date: 2026-03-10

## 1. Release Status

Django 6.0 was **released on December 3, 2025**. It is stable and has had several patch releases:

- 6.0.1 — January 6, 2026
- 6.0.2 — February 3, 2026
- 6.0.3 — March 3, 2026

Django 5.2.x is the last version supporting Python 3.10 and 3.11. Django 5.2 continues to receive bugfix and security updates as an LTS release.

## 2. Python Version Requirements

**Django 6.0 requires Python 3.12, 3.13, or 3.14.** Python 3.10 and 3.11 are no longer supported.

FLS currently uses Python 3.13, so no Python version change is required.

### Minimum dependency versions for Python 3.12+ compatibility

| Package | Minimum Version |
|---------|----------------|
| psycopg | 3.1.12+ |
| psycopg2 | 2.9.9+ |
| Pillow | 10.1.0+ |
| PyYAML | 6.0.2+ |
| sqlparse | 0.5.0+ |
| asgiref | 3.9.1+ |
| argon2-cffi | 23.1.0+ |
| redis-py | 5.1.0+ |

## 3. Major Breaking Changes (Django 5.x to 6.0)

### 3.1 DEFAULT_AUTO_FIELD now defaults to BigAutoField

`DEFAULT_AUTO_FIELD` now defaults to `django.db.models.BigAutoField` instead of `AutoField`. Most projects created since Django 3.2 already set this explicitly (Django 3.2+ emitted **models.W042** warnings), so this is likely a no-op for FLS. Verify that our settings explicitly set this or that we are okay with BigAutoField.

### 3.2 Email API Overhaul

This is a significant change and directly relevant to the concern in idea.md about email encoding.

**What changed:**

- `EmailMessage.message()` now returns a `email.message.EmailMessage` instance (Python's modern email API) instead of `SafeMIMEText`/`SafeMIMEMultipart`.
- `SafeMIMEText` and `SafeMIMEMultipart` classes are **deprecated** (will be removed in Django 7.0).
- `BadHeaderError` is deprecated in favor of `ValueError`.
- The `mixed_subtype` and `alternative_subtype` properties have been removed.
- The `encoding` property no longer accepts Python legacy `email.charset.Charset` objects.
- The `sanitize_address()` function is deprecated.
- Positional arguments beyond the first 4 in `EmailMessage`, `EmailMultiAlternatives`, `send_mail()`, `send_mass_mail()`, `mail_admins()`, `mail_managers()`, `get_connection()` are deprecated — must use keyword arguments.
- `EmailMessage.attach()` now accepts `MIMEPart` objects (modern API) instead of legacy `MIMEBase`.

**Impact on FLS:**

- Any custom email code that subclasses `EmailMessage` or uses internal underscore methods needs review.
- allauth email sending should be tested carefully — the encoding of email addresses (especially with display names containing non-ASCII characters) may behave differently with the modern email API.
- The modern API is more Unicode-friendly, which should improve email address handling, but testing is essential.

### 3.3 ORM Expression as_sql() must return tuple params

Custom ORM expressions' `as_sql()` method must now return params as a **tuple**, not a list. Any custom lookups, expressions, or annotations in FLS should be reviewed.

### 3.4 Database Backend Changes

- `return_insert_columns()` renamed to `returning_columns()`
- `fetch_returned_insert_rows()` renamed to `fetch_returned_rows()`
- MariaDB 10.5 support dropped (minimum 10.6+). Not relevant to FLS since we use PostgreSQL.

### 3.5 JSON Serializer

JSON serializer now writes a newline at end of output, even without `indent`. This may affect fixtures or test snapshots that compare exact JSON output.

### 3.6 Field.pre_save() may be called multiple times

Custom `pre_save()` implementations must be idempotent and free of side effects, as they may be called multiple times during a single save.

### 3.7 asgiref minimum version

Increased from 3.8.1 to 3.9.1.

## 4. Features Removed in 6.0

These were deprecated in Django 5.0/5.1 and are now fully removed:

- `DjangoDivFormRenderer` and `Jinja2DivFormRenderer` transitional form renderers
- `BaseDatabaseOperations.field_cast_sql()`
- Default URL scheme for `forms.URLField` changed from `"http"` to `"https"` (the `FORMS_URLFIELD_ASSUME_HTTPS` transitional setting is removed)
- `cx_Oracle` database backend support
- `ChoicesMeta` alias (use `django.db.models.enums.ChoicesType`)
- Various `get_prefetch_queryset()` / `get_joining_columns()` methods
- Positional arguments to `BaseConstraint`
- `django.urls.register_converter()` overriding existing converters
- Positional arguments to `Model.save()` and `Model.asave()`
- `CheckConstraint.check` keyword argument
- `FileSystemStorage.OS_OPEN_FLAGS` attribute

## 5. New Features in Django 6.0

### 5.1 Template Partials (Built-in)

Django 6.0 now includes built-in template partials, making the `django-template-partials` package unnecessary.

**Syntax:**

```django
{% partialdef partial_name %}
  <!-- reusable content -->
{% endpartialdef %}

{% partial partial_name %}
```

**Key features:**

- `{% partialdef %}` / `{% endpartialdef %}` to define partials
- `{% partial %}` to render them
- `template_name#partial_name` syntax for `get_template()`, `render()`, `{% include %}`
- Partials render with the current template context

**Migration from django-template-partials:**

1. Remove `{% load partials %}` from all templates
2. Remove `django-template-partials` from `INSTALLED_APPS`
3. Uninstall the package (`uv remove django-template-partials`)
4. The tag names (`partialdef`, `partial`) are the same, so template content should work without changes
5. Test all templates that use partials

A migration guide is available at: https://github.com/carltongibson/django-template-partials/blob/main/Migration.md

### 5.2 Content Security Policy (CSP) Support

Built-in CSP middleware and configuration:

```python
from django.utils.csp import CSP

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF, "https:"],
}
```

Components:
- `ContentSecurityPolicyMiddleware`
- `csp()` context processor for nonces
- `SECURE_CSP` and `SECURE_CSP_REPORT_ONLY` settings
- Per-view decorators

**Recommendation for FLS:** Consider adopting this for production security hardening after upgrade.

### 5.3 Background Tasks Framework

Built-in task framework for running code outside the request-response cycle:

```python
from django.tasks import task

@task
def email_users(emails, subject, message):
    send_mail(subject, message, None, emails)

email_users.enqueue(emails=[...], subject="...", message="...")
```

- Configured via `TASKS` setting
- Two built-in backends for development/testing
- Requires external workers for production execution
- Not a replacement for Celery in complex scenarios, but good for simple background tasks

**Recommendation for FLS:** Evaluate whether this can replace any existing async/background processing needs.

### 5.4 Other Notable New Features

- **AsyncPaginator** — async implementation of Paginator
- **`forloop.length`** — new variable in `{% for %}` loops
- **`StringAgg`** — now available on all databases, not just PostgreSQL
- **`AnyValue` aggregate** — returns arbitrary non-null value
- **`Model.NotUpdated` exception** — specialized exception for failed forced updates
- **Management commands:** `startproject`/`startapp` create target directory if missing; `shell` auto-imports common utilities
- **PBKDF2 iterations** increased from 1,000,000 to 1,200,000
- **Squashed migrations** can now be squashed again before transitioning

## 6. django-template-partials: Migration to Built-in

**Status:** The django-template-partials package is now superseded by Django 6.0's built-in template partials. The package author (Carlton Gibson) developed the feature that was merged into Django core.

**Migration steps for FLS:**

1. Remove `{% load partials %}` from every template that uses it
2. Remove `template_partials` / `django-template-partials` from `INSTALLED_APPS` in settings
3. Remove the package from dependencies (`pyproject.toml` / `uv`)
4. Verify all `partialdef` / `partial` / `#partial_name` usage works with the built-in implementation
5. Run full template test suite

**Differences to watch for:**

- The built-in implementation uses the same tag names and syntax
- The `template_name#partial_name` addressing syntax is the same
- The package may have had edge-case behaviors that differ from the built-in — test thoroughly

## 7. Email Handling and Encoding Changes

This is flagged as a key concern in the upgrade spec.

### What changed

Django 6.0 migrated from Python's legacy email API (Compat32) to the modern email API (`email.message.EmailMessage`). The modern API:

- Is more Unicode-friendly — handles non-ASCII characters in email addresses and headers more naturally
- Uses `email.policy.default` policy by default
- Eliminates the need for Django's custom `SafeMIMEText`/`SafeMIMEMultipart` wrappers

### Impact on email address encoding

The modern email API handles RFC 2047 encoding (for non-ASCII headers) and internationalized email addresses differently. Key areas to test:

1. **Display names with special characters** — e.g., `"Büro Admin" <admin@example.com>`
2. **Non-ASCII email addresses** — internationalized domain names
3. **allauth email sending** — registration confirmations, password resets
4. **Subject line encoding** — non-ASCII subjects
5. **HTML email alternatives** — `EmailMultiAlternatives` behavior

### Recommendation

Add explicit email sending tests to the QA plan covering:
- Account verification emails via allauth
- Password reset emails
- Any custom notification emails
- Test with non-ASCII display names and subjects

## 8. Migration Path Recommendations

### Pre-upgrade checklist

1. **Ensure FLS is on Django 5.2 LTS** with no deprecation warnings (run with `python -Wd`)
2. **Verify Python 3.12+** (FLS uses 3.13, so this is satisfied)
3. **Check all third-party packages** for Django 6.0 compatibility:
   - django-allauth
   - django-template-partials (will be removed)
   - django-cotton
   - Any other packages in pyproject.toml
4. **Review DEFAULT_AUTO_FIELD** setting

### Upgrade steps

1. Update Django version in `pyproject.toml` to `>=6.0,<6.1`
2. Update `asgiref` to `>=3.9.1`
3. Remove `django-template-partials` package and update templates
4. Run `uv run python manage.py makemigrations` to check for migration changes
5. Run `uv run python manage.py migrate`
6. Run full test suite: `uv run pytest`
7. Fix any deprecation warnings
8. Perform full UI QA testing with focus on:
   - Email sending and encoding
   - Template rendering (especially partials)
   - Form handling (URL field default scheme change)
   - Admin interface

### Post-upgrade opportunities

1. **Adopt CSP support** for security hardening
2. **Evaluate background tasks framework** for email sending and other async work
3. **Use `forloop.length`** where applicable in templates
4. **Update .claude files** as noted in idea.md

## 9. Deprecations to Address Proactively

These are deprecated in Django 6.0 and will be removed in Django 7.0. Fix them now to ease future upgrades:

- Convert positional args in email functions to keyword args
- Replace `BadHeaderError` catches with `ValueError`
- Replace `MIMEBase` attachments with `MIMEPart`
- Update `ADMINS`/`MANAGERS` settings if using tuple format
- Replace `django.contrib.postgres.aggregates.StringAgg` with `django.db.models.StringAgg`

## References

- [Django 6.0 Release Notes (official)](https://docs.djangoproject.com/en/6.0/releases/6.0/)
- [Django 6.0.1 Release Notes](https://docs.djangoproject.com/en/6.0/releases/6.0.1/)
- [Django 6.0.2 Release Notes](https://docs.djangoproject.com/en/6.0/releases/6.0.2/)
- [Django 6.0.3 Release Notes](https://docs.djangoproject.com/en/6.0/releases/6.0.3/)
- [django-template-partials Migration Guide](https://github.com/carltongibson/django-template-partials/blob/main/Migration.md)
- [django-template-partials GitHub](https://github.com/carltongibson/django-template-partials)
- [Django 6.0 Template Partials Documentation](https://docs.djangoproject.com/en/6.0/ref/templates/language/)
- [Django Upgrade Guide](https://docs.djangoproject.com/en/6.0/howto/upgrade-version/)
- [Django 6.0 Key Features and Breaking Changes (Medium)](https://ak-sy.medium.com/django-6-0-release-key-features-breaking-changes-upgrade-guide-4f9dd3af785f)
- [Django Releases on PyPI](https://pypi.org/project/Django/)
- [Django End of Life Dates](https://endoflife.date/django)
- [Django 6.0 Deep Dive: Template Partials, CSP, and Background Tasks (Medium)](https://medium.com/@yogeshkrishnanseeniraj/django-6-0-deep-dive-template-partials-csp-and-background-tasks-what-actually-changes-your-5aec496627c2)
- [Django: What's New in 6.0 — Adam Johnson](https://adamj.eu/tech/2025/12/03/django-whats-new-6.0/)
