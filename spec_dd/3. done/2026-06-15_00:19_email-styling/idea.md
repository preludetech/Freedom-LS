# Idea: Theme & site branding in emails

## Goal

Make our transactional emails (allauth: verification, password reset, login
code, change/notification mails) faithfully reflect the active theme, and show
the site's configured logo and label.

## Starting point (already built, on `main`)

A branded-email system already exists and is merged:

- Theme colours are extracted from the active theme's `theme.css` into
  `EMAIL_COLOR_*` settings (`config/settings_base.py`), exposed via the
  `email_settings` context processor, and inlined into the email templates
  (`freedom_ls/accounts/templates/emails/`) by a premailer template tag.
- The email header (`emails/includes/header.html`) already shows a logo **if**
  `EMAIL_LOGO_STATIC_PATH` is set, otherwise falls back to `current_site.name`.
- The footer already uses `current_site.name` / `current_site.domain`.

So this is **not a greenfield build** — it is a hardening + unification pass on
top of the existing system. Theme stays **global** (one `FLS_THEME` env var);
this work does **not** introduce per-site theming.

## Scope

### 1. Harden theme-colour extraction

The current `parse_tailwind_colors` regex only matches literal `#hex` values.
Today every base token emails use happens to be hex, so it works — but it is
brittle and fails **silently** to a hardcoded default the moment a theme defines
a base token with any modern CSS colour syntax. The same theme files already use
`oklch()`, `color-mix()`, and `var()` for derived tokens, so this is a real
forward risk, not a hypothetical.

- Parse the **raw** value of each `--color-*` token (everything up to `;`), then
  classify and **convert it to email-safe hex** in Python. Email clients do not
  reliably support `oklch()`/`oklab()`/`color-mix()`/`var()` — Gmail strips the
  *entire* style attribute when it hits one. So extraction must always resolve to
  `#rrggbb`, never pass modern syntax through.
- Handle `var(--x)` references (two-pass resolve) and `color-mix(...)`.
- On a missing/unparseable token, fall back to the existing hardcoded default
  **but make it visible** (a `warnings.warn` at settings-load time — not silent,
  and not a hard `ImproperlyConfigured` that blocks startup).

### 2. Cover fonts & buttons more fully

- Derive the email font stack from the theme's `--fls-font-sans` rather than the
  hardcoded `EMAIL_FONT_FAMILY` string — but **strip non-web-safe entries**
  (custom/Google fonts, `system-ui`, `ui-sans-serif`) so the result is an
  email-safe fallback stack. Custom fonts don't load in most email clients.
- Drive the email button's `border-radius` from `--fls-radius-md` (Outlook
  ignores `border-radius` — acceptable degradation; no VML workaround).
  Button background/text already come from theme tokens.

### 3. Unify site logo & label with the existing web-header branding

"If a site label and logo are set, include them in emails" — sourced from the
**existing global settings** (no new model, no migration, no uploads):

- **Logo**: default the email logo to the web header's logo — i.e. use
  `EMAIL_LOGO_STATIC_PATH or HEADER_LOGO_STATIC_PATH`, so a site that configures
  a header logo automatically gets it in emails, while the explicit email setting
  remains an override/escape-hatch.
- **Fix the broken image URL** (real bug): the header currently builds the logo
  `src` with `{% static %}`, which yields a root-relative `/static/...` path that
  does **not load** in external email clients. Build a fully-qualified absolute
  URL from `current_site.domain` + scheme (scheme from
  `ACCOUNT_DEFAULT_HTTP_PROTOCOL`, so it works even when an email is sent without
  a request).
- **Label**: apply the same precedence the web header uses — `HEADER_TITLE →
  Site.name` — for the logo `alt` text, the text fallback, and the plain-text
  email. Today emails use `current_site.name` directly and skip `HEADER_TITLE`.
- **Always-something guarantee**: logo `<img>` if a resolvable logo is
  configured; otherwise the text label; the label always falls back to
  `Site.name`. Alt text = the label (it's the only visible branding when images
  are blocked). Use PNG, not SVG.

## Non-goals

- No per-site theme/branding model, DB fields, migration, or uploaded logos.
- No per-site theming — theme remains global via `FLS_THEME`.
- No VML/Outlook-specific hacks for rounded buttons.
- No dark-mode logo variants (transparent PNG is sufficient for now).

## Research

Detailed findings, options, and citations:

- `research_theme_color_extraction.md` — CSS parsing approach (hardened regex vs
  `tinycss2`), modern colour formats & email-client support, `coloraide` for
  conversion, failure behaviour, font/button token coverage.
- `research_email_branding_logo.md` — absolute-URL construction, settings
  unification options, PNG vs SVG, alt-text/fallback semantics, testing approach.

## Open implementation choices (for the spec, not decided here)

- Whether to add `coloraide` as a dependency (recommended) vs hand-rolled
  conversion; whether `tinycss2` is already transitively available.
- Exactly where the absolute logo URL is composed (adapter `send_mail` vs
  context processor + template tag) — `current_site` is needed, which the
  `email_settings` context processor doesn't currently have.
