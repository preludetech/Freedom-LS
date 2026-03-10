# Research: Django 5.x to 6.x Upgrade Best Practices

Date: 2026-03-10

## 1. Recommended Upgrade Strategy

Django's official documentation is clear: **upgrade incrementally through each feature release** rather than jumping multiple versions at once.

For this project (Django 5.x to 6.0), the recommended path is:

1. **Upgrade to Django 5.2 LTS first** (if not already on it). Django 5.2 is the last release in the 5.x series and the bridge to 6.0.
2. **Resolve all deprecation warnings on 5.2** before attempting the 6.0 upgrade.
3. **Upgrade to Django 6.0** (released December 3, 2025; bugfix 6.0.1 is also available).

This incremental approach is important because Django's deprecation policy guarantees that features deprecated in version X are removed in version X+2. So anything deprecated in 5.0 is removed in 6.0. By going through 5.2, you get warnings about everything that will break in 6.0.

**Python version**: Django 6.0 drops support for Python 3.10 and 3.11. It supports Python 3.12, 3.13, and 3.14. This project uses Python 3.13+, so this should not be an issue.

### References

- [How to upgrade Django to a newer version (official docs)](https://docs.djangoproject.com/en/6.0/howto/upgrade-version/)
- [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)
- [Django 5.2 release notes](https://docs.djangoproject.com/en/6.0/releases/5.2/)

---

## 2. Common Pitfalls and Gotchas in Major Django Upgrades

### Third-party dependency compatibility

This is typically where **most of the upgrade time is spent**. Third-party packages often use deeper Django APIs that change between versions. If a package hasn't released a Django 6.0-compatible version, you may need to wait or find alternatives.

Key packages to check for this project:
- **django-allauth** -- v65.13.1+ supports Django 6.0
- **django-template-partials** -- replaced by Django 6.0 core (see section 6)
- Any other packages in requirements

### Breaking changes removed in Django 6.0

Notable removals that could affect this codebase:

- **`Model.save()` and `Model.asave()` no longer accept positional arguments** -- all parameters must be keyword arguments
- **`format_html()` can no longer be called without args or kwargs**
- **`forms.URLField` default scheme changed from "http" to "https"**
- **`DjangoDivFormRenderer` and `Jinja2DivFormRenderer` transitional renderers removed**
- **`django.urls.register_converter()` no longer allows overriding existing converters**
- **`ModelAdmin.lookup_allowed()` now requires `request` in signature of subclasses**
- **`Prefetch.get_current_queryset()` removed**; use `get_current_querysets()` instead
- **`get_prefetch_queryset()` method of related managers removed**

### Email API overhaul

Django 6.0 modernized the email API to use Python's modern `email.message.EmailMessage` class instead of the legacy MIME-based API. This is a significant change:

- `EmailMessage.message()` now returns `email.message.EmailMessage` instead of `SafeMIMEText`/`SafeMIMEMultipart`
- `SafeMIMEText` and `SafeMIMEMultipart` are **deprecated**
- `BadHeaderError` is deprecated (Python's modern API raises `ValueError` instead)
- Optional parameters to `send_mail()`, `EmailMessage()`, etc. **must now be keyword arguments**
- The `sanitize_address()` and `forbid_multi_line_headers()` functions are deprecated

This is particularly relevant since the project uses allauth for email sending.

### Caching

Clear all caches after upgrading. Pickled objects cached by one Django version are not guaranteed to be compatible with another version.

### DEFAULT_AUTO_FIELD

Django 6.0 defaults `DEFAULT_AUTO_FIELD` to `django.db.models.BigAutoField`. If the project already sets this explicitly (which most Django 5.x projects do), this is a non-issue. If not, existing migrations may need attention.

### References

- [Django 6.0 release notes -- backwards incompatible changes](https://docs.djangoproject.com/en/6.0/releases/6.0/)
- [Django Deprecation Timeline](https://docs.djangoproject.com/en/dev/internals/deprecation/)
- [Django 6.0.1 bugfix release notes](https://docs.djangoproject.com/en/6.0/releases/6.0.1/)

---

## 3. How to Handle Deprecation Warnings Effectively

Python silences deprecation warnings by default. You must explicitly enable them.

### Step 1: Enable warnings before upgrading

```bash
# Run tests with all warnings visible
python -Wa manage.py test

# Or with pytest (pytest shows warnings by default, but to be explicit):
PYTHONWARNINGS=all uv run pytest

# Or set in pytest config:
# [tool.pytest.ini_options]
# filterwarnings = ["default::DeprecationWarning"]
```

### Step 2: Configure pytest to catch Django-specific warnings

Django uses version-specific warning classes (e.g., `RemovedInDjango60Warning`). Configure pytest to turn these into errors so they cannot be missed:

```toml
# pyproject.toml
[tool.pytest.ini_options]
filterwarnings = [
    "error::django.utils.deprecation.RemovedInDjango60Warning",
]
```

### Step 3: Fix all warnings on current version BEFORE upgrading

This is the critical step. Fix every deprecation warning while still on Django 5.2. Once all warnings are resolved, the upgrade to 6.0 should be much smoother since the deprecated features are what get removed in the next major version.

### Step 4: After upgrading, watch for new deprecations

Django 6.0 introduces `RemovedInDjango61Warning` and `RemovedInDjango70Warning` for features that will be removed in future versions. Address these proactively.

### References

- [How to have Python show warnings when running Django](https://www.untangled.dev/2023/04/26/py-django-warnings/)
- [Show Python deprecation warnings (James Bennett)](https://www.b-list.org/weblog/2023/dec/19/show-python-deprecation-warnings/)
- [Upgrading Django with python -Wa manage.py test](https://dev.to/azayshrestha/upgrading-django-with-python-wa-managepy-test-2l69)
- [pytest: How to capture warnings](https://docs.pytest.org/en/stable/how-to/capture-warnings.html)

---

## 4. Testing Strategies for Major Upgrades

### Pre-upgrade testing

1. **Run the full test suite on the current version** with deprecation warnings turned into errors (see section 3). This establishes a clean baseline.
2. **Check third-party package compatibility** before starting. Verify each dependency supports Django 6.0.
3. **Read the full release notes** for every version between current and target (5.1, 5.2, 6.0).

### During upgrade

1. **Upgrade Django only** first (don't upgrade other packages simultaneously). This isolates Django-specific breakage.
2. **Run the test suite** immediately after upgrading. Fix failures before proceeding.
3. **Upgrade third-party packages** one at a time, running tests after each.

### Post-upgrade testing

1. **Run the full test suite** with all warnings enabled.
2. **Manual QA of the full user interface** -- particularly:
   - Email sending (registration, confirmation, password reset)
   - Template rendering (especially partials)
   - Form submissions (especially URL fields due to the http->https default change)
   - Admin interface (if using custom ModelAdmin subclasses)
   - Any cached data (clear caches first)
3. **Check for silent behavioral changes** that tests might not catch:
   - Email encoding and formatting
   - URL generation
   - Form validation defaults

### References

- [How to upgrade Django to a newer version (official)](https://docs.djangoproject.com/en/6.0/howto/upgrade-version/)
- [Open edX Django Upgrade Checklist](https://openedx.atlassian.net/wiki/spaces/AC/pages/160612349/Django+Upgrade+Checklist)
- [Upgrading Django FAQ](https://upgradedjango.com/faq/)

---

## 5. Allauth Email Encoding Issues

### Historical issues

django-allauth has had several documented issues with email handling:

- **Confirmation link encoding** (issue #2807): Users unable to click confirmation email links due to special characters in confirmation keys (e.g., characters like `:` in HMAC-based keys such as `NDYx:1lLQg2:IpA1jpkyIo5ZsgBqpb5lF9HC08qUxr5ophVZ3ENr2Y8`). Some email clients improperly handle these characters.
- **URL-encoded email addresses**: Email addresses containing special characters (like `+` in `user+tag@example.com`) can be percent-encoded in confirmation URLs, causing lookup failures when the receiving view doesn't decode them properly.
- **HTTP vs HTTPS in confirmation links** (issue #2525): Confirmation emails generating `http://` links even when `ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"` is set.
- **NoReverseMatch errors** (issue #2509): Account confirmation emails failing when the URL reverse for `account_confirm_email` receives an empty key argument.

### Django 6.0 email API impact on allauth

Django 6.0's modernized email API (using `email.message.EmailMessage` instead of legacy MIME classes) changes how email encoding works under the hood. The new API is "Unicode-friendly," which could affect how email addresses with special characters are handled in headers and message bodies.

**django-allauth v65.13.1+ officially supports Django 6.0.** However, given the project's concern about email encoding, thorough testing is essential:

- Test confirmation emails with email addresses containing `+`, `.`, and other special characters
- Verify confirmation links are clickable in major email clients (Gmail, Outlook, Apple Mail)
- Verify HTTPS is used in all confirmation URLs
- Test password reset emails
- Test email change workflows (particularly with `ACCOUNT_CHANGE_EMAIL = True`, which had a security flaw fixed in allauth 65.12.1)

### References

- [django-allauth: Users unable to click links in confirmation email (#2807)](https://github.com/pennersr/django-allauth/issues/2807)
- [django-allauth: Account confirmation emails failing (#2509)](https://github.com/pennersr/django-allauth/issues/2509)
- [django-allauth: Confirmation email stuck using HTTP (#2525)](https://github.com/pennersr/django-allauth/issues/2525)
- [django-allauth release notes (65.13.1)](https://docs.allauth.org/en/dev/release-notes/recent.html)
- [django-allauth: Sending Email documentation](https://docs.allauth.org/en/dev/common/email.html)

---

## 6. django-template-partials to Django Core Transition

### Background

Django 6.0 integrates template partials directly into the Django Template Language. This feature was originally developed by Carlton Gibson as the third-party `django-template-partials` package, and has been adopted into core with the same syntax.

### Syntax compatibility

The syntax is the same between the package and Django 6.0 core:

```html
{# Define a partial (both package and core use the same syntax) #}
{% partialdef user-info %}
  <div class="user">{{ user.name }}</div>
{% endpartialdef %}

{# Render a partial #}
{% partial user-info %}

{# Inline partial (defined and rendered in place) #}
{% partialdef sidebar inline %}
  <nav>...</nav>
{% endpartialdef %}

{# Reference from another template #}
{% include "template.html#partial_name" %}
```

The tag names `partialdef`/`endpartialdef` and `partial` are identical. The `inline` argument works the same way.

### Migration steps

The official migration guide from the django-template-partials repository:

1. **Remove from INSTALLED_APPS**: Remove `"template_partials"` (or `"template_partials.apps.SimpleAppConfig"`) from `INSTALLED_APPS`.
2. **Remove template loader configuration**: Delete any manual template loader configurations or builtins that reference `"template_partials.templatetags.partials"`. This includes removing any `wrap_loaders()` calls if used.
3. **Remove `{% load partials %}` from all templates**: Since partials are now built-in to the template engine, the load tag is no longer needed.
4. **Remove the package dependency**: Uninstall `django-template-partials` and remove it from requirements/pyproject.toml.

### Things to verify after migration

- All existing partials render correctly
- Inline partials still work as expected
- Cross-template partial references (`template.html#partial_name`) work
- Context handling is preserved (partials should render with the current template context)

### References

- [django-template-partials Migration Guide](https://github.com/carltongibson/django-template-partials/blob/main/Migration.md)
- [Django 6.0: Template Partials documentation](https://docs.djangoproject.com/en/6.0/ref/templates/language/)
- [Django forum: Adding template fragments/partials for the DTL](https://forum.djangoproject.com/t/adding-template-fragments-or-partials-for-the-dtl/21500)
- [Adam Johnson: What's new in Django 6.0](https://adamj.eu/tech/2025/12/03/django-whats-new-6.0/)
- [What's new on Django 6 -- Template Partials (Medium)](https://medium.com/@nur.hakim.arif/whats-new-on-django-6-template-partials-04f100e4283e)

---

## 7. Other Notable Django 6.0 Features to Consider

While not directly related to the upgrade process, these new features may be worth adopting:

### Background Tasks Framework

Django 6.0 includes a built-in task framework for running code outside the request-response cycle. This could replace Celery or other task queue solutions for simpler use cases like sending emails or processing data.

### Content Security Policy (CSP) Support

Built-in CSP support via `ContentSecurityPolicyMiddleware`, configured through `SECURE_CSP` and `SECURE_CSP_REPORT_ONLY` settings. Includes nonce support via the `csp()` context processor.

### References

- [Django 6.0 Deep Dive: Template Partials, CSP, and Background Tasks (Medium)](https://medium.com/@yogeshkrishnanseeniraj/django-6-0-deep-dive-template-partials-csp-and-background-tasks-what-actually-changes-your-5aec496627c2)
- [Django 6.0 released (official weblog)](https://www.djangoproject.com/weblog/2025/dec/03/django-60-released/)
- [InfoQ: Django Releases Version 6.0](https://www.infoq.com/news/2026/01/django-6-release/)
