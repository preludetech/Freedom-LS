# Email Template System

## Overview

FLS provides professional branded HTML+text multipart emails for all django-allauth email flows. Emails use table-based layouts with CSS inlining for maximum email client compatibility. Brand colors are automatically pulled from the Tailwind CSS configuration.

## Base Email Template Structure

All email templates extend one of two base templates:

| Template | Purpose |
|---|---|
| `emails/base_email.html` | HTML base with `{% premailer %}` CSS inlining, table-based layout, header, greeting, content, CTA, sign-off, footer |
| `emails/base_email.txt` | Plain text base with greeting, content, sign-off, site info |
| `emails/base_notification_email.html` | Extends `base_email.html`, adds a security info section (IP, browser, timestamp) |
| `emails/base_notification_email.txt` | Extends `base_email.txt`, adds plain text security info |

### Block Structure

**`base_email.html`** provides:
- `{% block subject %}` -- Email subject line (used in `<title>`)
- `{% block content %}` -- Main email body
- `{% block cta %}` -- Call-to-action button area (below content)

**`base_notification_email.html`** adds:
- `{% block notification_content %}` -- Use this instead of `content` when extending the notification base
- `{% block security_info %}` -- Security details block (IP, browser, timestamp); pre-filled, override to customize

## Overridable Include Files

These files are included by the base templates. Downstream projects override them by placing a file at the same template path.

| Include | Format | Purpose |
|---|---|---|
| `emails/includes/greeting.html` | HTML | Opening greeting (e.g., "Hi {{ user.first_name }}") |
| `emails/includes/greeting.txt` | Text | Plain text opening greeting |
| `emails/includes/sign_off.html` | HTML | Closing sign-off |
| `emails/includes/sign_off.txt` | Text | Plain text closing sign-off |
| `emails/includes/header.html` | HTML | Email header with optional logo or site name |
| `emails/includes/footer_links.html` | HTML | Footer links section (empty by default) |

To override, create a file at the same path in your project's templates directory (which must appear before FLS in `TEMPLATES` dirs or `INSTALLED_APPS`).

## Context Variables

| Variable | Source | Description |
|---|---|---|
| `email_color_primary` | `settings.EMAIL_COLOR_PRIMARY` | Header background, button background, link color |
| `email_color_foreground` | `settings.EMAIL_COLOR_FOREGROUND` | Body text color |
| `email_color_muted` | `settings.EMAIL_COLOR_MUTED` | Footer text, secondary text, security info |
| `email_font_family` | `settings.EMAIL_FONT_FAMILY` | Font stack for the email body |
| `email_logo_static_path` | `settings.EMAIL_LOGO_STATIC_PATH` | Optional path to logo in static files |
| `current_site` | Django Sites framework | Site name and domain for footer |
| `user` | `AccountAdapter.send_notification_mail()` | User object, injected for notification emails |

Context variables are injected by the `email_settings` context processor in `freedom_ls/accounts/context_processors.py`.

## Allauth Email Types

All templates are in `freedom_ls/accounts/templates/account/email/`.

| Email Type | Template Prefix | Base Template | Key Context Variables |
|---|---|---|---|
| Email confirmation | `email_confirmation` | `base_email` | `activate_url` |
| Email confirmation (signup) | `email_confirmation_signup` | Includes `email_confirmation` | `activate_url` |
| Password reset | `password_reset_key` | `base_email` | `password_reset_url` |
| Unknown account | `unknown_account` | `base_email` | `signup_url` |
| Login code | `login_code` | `base_email` | `code` |
| Account already exists | `account_already_exists` | `base_email` | `password_reset_url` |
| Password changed | `password_changed` | `base_notification_email` | `user`, `ip`, `user_agent`, `timestamp` |
| Password set | `password_set` | `base_notification_email` | `user`, `ip`, `user_agent`, `timestamp` |
| Email changed | `email_changed` | `base_notification_email` | `user`, `from_email`, `to_email` |
| Email confirmed | `email_confirm` | `base_notification_email` | `user` |
| Email deleted | `email_deleted` | `base_notification_email` | `user`, `deleted_email` |

Each type has three files: `*_subject.txt`, `*_message.html`, `*_message.txt`.

## Configuration

Settings are defined in `config/settings_base.py`.

| Setting | Default | Description |
|---|---|---|
| `EMAIL_LOGO_STATIC_PATH` | `None` | Path to logo image in static files (e.g., `"images/logo.png"`) |
| `EMAIL_COLOR_PRIMARY` | Parsed from Tailwind (`--color-primary`) or `#2B6CB0` | Header background, button color |
| `EMAIL_COLOR_FOREGROUND` | Parsed from Tailwind (`--color-foreground`) or `#1A2332` | Body text color |
| `EMAIL_COLOR_MUTED` | Parsed from Tailwind (`--color-muted`) or `#4A5568` | Footer and secondary text color |
| `EMAIL_FONT_FAMILY` | `"Arial, Helvetica, sans-serif"` | Font stack |
| `ACCOUNT_EMAIL_NOTIFICATIONS` | `True` | Enable allauth notification emails (password changed, etc.) |

## How CSS Inlining Works

The `base_email.html` template wraps its entire content in `{% premailer %}...{% endpremailer %}` (from `django-premailer`). This converts the `<style>` block into inline `style` attributes on each HTML element at render time. Since this is in the base template, all child templates get CSS inlining automatically.

## How Brand Colors Work

The color parser in `freedom_ls/accounts/email_utils.py` reads `--color-*` custom properties from `tailwind.components.css` at Django startup:

```python
_tw_colors = parse_tailwind_colors(str(BASE_DIR / "tailwind.components.css"))
EMAIL_COLOR_PRIMARY = _tw_colors.get("primary", "#2B6CB0")
```

Changing `--color-primary`, `--color-foreground`, or `--color-muted` in `tailwind.components.css` automatically updates email colors on the next server restart.

## Previewing Emails in Development

Dev settings (`config/settings_dev.py`) use the file-based email backend:

```python
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = "gitignore/emails"
```

Trigger any email flow (signup, password reset, etc.) and check the generated files in `gitignore/emails/`.

## Adding a New Email Type

Extend the base template and use the `content` and `cta` blocks:

```html
{% extends "emails/base_email.html" %}

{% block content %}
<p style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.5;">Your custom email content here.</p>
{% endblock %}

{% block cta %}
<table role="presentation" cellpadding="0" cellspacing="0" style="margin: 24px 0;">
  <tr>
    <td style="background-color: {{ email_color_primary }}; border-radius: 6px;">
      <a href="{{ action_url }}" style="display: inline-block; padding: 12px 32px; color: #FFFFFF; text-decoration: none; font-weight: bold; font-size: 16px;">Take Action</a>
    </td>
  </tr>
</table>
{% endblock %}
```

For notification-style emails (with security info), extend `emails/base_notification_email.html` and use `{% block notification_content %}` instead.
