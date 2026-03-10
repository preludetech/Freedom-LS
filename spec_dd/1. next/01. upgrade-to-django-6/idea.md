# Upgrade Django 5.2 to Django 6.0

Django 6.0 was released December 2025 and is stable (6.0.3 as of March 2026). Our project is on Django 5.2.9 with Python 3.13, which meets Django 6's requirement of Python 3.12+.

## Core upgrade tasks

### 1. Fix deprecation warnings first

Before upgrading, run the test suite with deprecation warnings enabled (`python -Wd`) on Django 5.2 and fix all warnings. This ensures a smooth transition since deprecated features in 5.x are removed in 6.0.

### 2. Upgrade Django and update package constraints

Update `pyproject.toml`:
- Django: `>=6.0,<6.1`
- django-allauth: `>=65.14.0` (Django 6 support since 65.13.1)
- django-cotton: relax upper bound from `<2.5` to allow 2.6+ (supports Django 6)
- django-guardian: `>=3.3.0`
- django-ninja: `>=1.5.0`
- django-unfold: `>=0.83.0`
- django-debug-toolbar: `>=6.2.0`
- heroicons, django-storages, django-watchfiles, django-browser-reload: should work as-is, verify

### 3. Migrate django-template-partials to Django 6 built-in partials

Django 6.0 includes template partials natively (same syntax: `partialdef`/`partial`). Migration steps:
- Remove `template_partials.apps.SimpleAppConfig` from `INSTALLED_APPS`
- Remove `template_partials.loader.Loader` from the template loaders config
- Remove `template_partials.templatetags.partials` from template builtins
- Remove the `django-template-partials` package dependency
- Templates don't use `{% load partials %}` (it's configured as a builtin), so template files themselves should need no changes
- Verify all 5 template files using partials still work correctly

### 4. Handle django-premailer

`django-premailer` is unmaintained since 2016 (officially supports Django 1.6-1.9). It's used in `base_email.html` for inlining CSS in emails. It's a thin wrapper so it likely still works. Test that it works with Django 6 and verify the resulting emails render correctly. Only replace if it breaks.

### 5. Handle django-stubs

django-stubs doesn't fully support Django 6 yet. Accept partial type coverage initially — may need temporary `# type: ignore` comments for new Django 6 APIs until django-stubs catches up.

## Things to pay attention to

### Email encoding (Django 6 overhauled the email API)

Django 6 migrated from legacy MIME API to Python's modern `email.message.EmailMessage`. This changes how email encoding works under the hood. The modern API is more Unicode-friendly but needs careful testing:
- allauth confirmation emails with special characters in email addresses (`+`, `.`)
- Password reset emails
- Non-ASCII display names and subjects
- Confirmation link encoding (historical allauth issues with HMAC keys containing `:`)
- HTML email rendering via django-premailer

### DEFAULT_AUTO_FIELD

Already set to `BigAutoField` in settings — no action needed.

### Removed features that might affect us

- `Model.save()` no longer accepts positional arguments (must use keyword args)
- `format_html()` can no longer be called without args/kwargs
- `forms.URLField` default scheme changed from "http" to "https"
- Positional arguments to `send_mail()`, `EmailMessage()` etc. deprecated (must use keyword args)

## Post-upgrade: update .claude files

Go over all files in `.claude/` and make minimal required changes. Key areas:
- Update any Django version references
- Update documentation that mentions django-template-partials
- Review skill files that reference deprecated patterns

### 6. Adopt Content Security Policy (CSP)

Django 6 includes built-in CSP middleware (`ContentSecurityPolicyMiddleware`). Set up `SECURE_CSP` settings and the `csp()` context processor for nonce support. This hardens production security. `django-browser-reload` already auto-includes CSP nonces on Django 6.

### 7. Adopt Background Tasks Framework

Django 6 includes a built-in task framework for running code outside the request-response cycle. Evaluate where this can be used in FLS (e.g. sending emails, data processing). Not a Celery replacement for complex scenarios, but good for simple background work.

## QA plan requirements

Do a full user interface QA test including:
- All email flows (registration, confirmation, password reset) with various email address formats
- Template rendering (especially partials after migration)
- Form submissions (URL fields, form validation)
- Admin interface
- Student and educator interfaces
- Course content rendering
