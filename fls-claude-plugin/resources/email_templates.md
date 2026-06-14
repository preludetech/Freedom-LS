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

| Variable | Source (`EmailTheme` field) | Description |
|---|---|---|
| `email_color_primary` | `color_primary` | Button background, link color |
| `email_color_foreground` | `color_foreground` (role `on-surface`) | Body text color |
| `email_color_muted` | `color_muted` | Footer text, secondary text, security info |
| `email_color_surface` | `color_surface` | Email/card background |
| `email_color_surface_2` | `color_surface_2` | Secondary surface (e.g. security info block) |
| `email_color_on_primary` | `color_on_primary` | Text/logo color on the primary background |
| `email_color_border` | `color_border` | Divider and border color |
| `email_color_header` | `color_header` | Header band background (own role; defaults to primary) |
| `email_color_on_header` | `color_on_header` | Header text-label colour (own role; defaults to on-primary) |
| `email_font_family` | `font_family` | Email-safe font stack derived from the theme |
| `email_button_radius` | `button_radius` | CTA button corner radius (from `--fls-radius-md`) |
| `current_site` | Django Sites framework | Site name and domain for footer |
| `user` | `AccountAdapter.send_notification_mail()` | User object, injected for notification emails |

The colour, font, and radius variables above are injected globally by the
`email_settings` context processor in
`freedom_ls/accounts/context_processors.py`, which reads them from the cached
`get_email_theme()` resolver (see *How Brand Colors Work*).

Further variables are injected per-message by `AccountAdapter.send_mail`
(they are **not** in the context processor, so templates reference them with a
`|default:` fallback or an `{% if %}` guard):

| Variable | Source | Description |
|---|---|---|
| `email_logo_url` | `send_mail` (absolute URL from `EMAIL_LOGO_STATIC_PATH` or `HEADER_LOGO_STATIC_PATH`) | Fully-qualified `https://domain/static/…` logo URL, or `None` to fall back to a text label |
| `email_label` | `send_mail` (`HEADER_TITLE` or `current_site.name`) | Brand label used in message bodies, the header text fallback, and the logo `alt` text |
| `email_logo_width` / `email_logo_height` | `send_mail` (`email_logo_dimensions`) | Logo's real pixel size scaled to a 48px display height (aspect-ratio safe); `None` when the file can't be measured, so the header falls back to a height-only constraint |

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

Email colours, font, and button radius are **not** settings — they are derived
from the active theme's `theme.css` lazily and cached by `get_email_theme()`
(see *How Brand Colors Work*). The genuine settings in `config/settings_base.py`
are:

| Setting | Default | Description |
|---|---|---|
| `EMAIL_LOGO_STATIC_PATH` | `None` | Path to email logo in static files; falls back to `HEADER_LOGO_STATIC_PATH` when unset |
| `ACCOUNT_EMAIL_NOTIFICATIONS` | `True` | Enable allauth notification emails (password changed, etc.) |

The theme selection that drives the derivation (`FLS_THEME`, `RESOLVED_THEME_DIR`)
also lives in settings; the path to the active theme's `theme.css` is derived
from them by `email_theme_css_path()`.

## How CSS Inlining Works

The `base_email.html` template wraps its entire content in `{% premailer %}...{% endpremailer %}` (from `django-premailer`). This converts the `<style>` block into inline `style` attributes on each HTML element at render time. Since this is in the base template, all child templates get CSS inlining automatically.

## How Brand Colors Work

`get_email_theme()` in `freedom_ls/accounts/email_utils.py` reads CSS custom
properties from the active theme's `theme.css` the first time an email is
rendered, and caches the resolved `EmailTheme` for the process lifetime (so a
future bulk send resolves it once). `parse_tailwind_tokens` captures every
`--<name>` token as a raw string; `resolve_color_token` then resolves each
colour role to an opaque `#rrggbb` value via `resolve_css_color` (backed by
`coloraide`), which understands hex, `rgb()`, `hsl()`, `oklch()`, `oklab()`,
`lch()`, `lab()`, named colours, `var()` references, and `color-mix()`:

```python
theme = get_email_theme()          # cached EmailTheme
theme.color_primary                 # e.g. "#2b6cb0"
theme.color_header                  # header band (own role; white under first_class)
```

If a token is missing or cannot be resolved to an opaque hex, the resolver emits
a `UserWarning` and uses the hardcoded fallback; a missing `theme.css` degrades
to all-fallbacks rather than raising. The colour roles and their fallbacks live
in a single source of truth, `EMAIL_COLOR_TOKENS`, shared by the resolver and the
`check_email_colour_tokens` system check (so the two cannot drift). Changing a
token in the active theme's `theme.css` updates email colours on the next server
restart. Tests that override the theme must call `get_email_theme.cache_clear()`.

## Previewing Emails in Development

Dev settings (`config/settings_dev.py`) send mail to Mailpit's SMTP listener:

```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "localhost"
EMAIL_PORT = 1025
```

Start Mailpit via the `dev_db` composition (`cd dev_db && docker compose up`), trigger an email flow (signup, password reset, etc.), then open `http://localhost:8025` to view it.

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
    <td style="background-color: {{ email_color_primary }}; border-radius: {{ email_button_radius }};">
      <a href="{{ action_url }}" style="display: inline-block; padding: 12px 32px; color: {{ email_color_on_primary }}; text-decoration: none; font-weight: bold; font-size: 16px;">Take Action</a>
    </td>
  </tr>
</table>
{% endblock %}
```

For notification-style emails (with security info), extend `emails/base_notification_email.html` and use `{% block notification_content %}` instead.
