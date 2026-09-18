---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/partials/login_prompt.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: bug-authentication-next-target-sometimes-lost

The header Login and Sign up buttons now keep the request's `next` target when it is present and safe, the same way allauth's own in-form links do. Before this change, a visitor who reached `/accounts/login/?next=<url>` and signed up through the header button landed on `LOGIN_REDIRECT_URL` after confirming their email instead of on `<url>`.

The fix adds a template tag library, `accounts_tags` (`freedom_ls/accounts/templatetags/accounts_tags.py`), with one tag, `{% url_with_next "<url_name>" %}`. It reverses the URL name and adds the current request's `next` through `allauth.account.utils.passthrough_next_redirect_url`. With no `next`, an unsafe `next`, or no `request` in the context, it returns the plain URL.

## Breaking changes

None. No models, settings, URLs or dependencies changed.

## Manual steps

If your project overrides `partials/login_prompt.html` (FLS source: `freedom_ls/base/templates/partials/login_prompt.html`), your override still has the bug. Update it to match:

```django
{% load accounts_tags %}
{% url_with_next "account_login" as login_url %}
...
{% url_with_next "account_signup" as signup_url %}
```

Any other template you own that links to `account_login` or `account_signup` from a page that may carry `next` can use the same tag.

If you don't override that partial, no action is needed.
