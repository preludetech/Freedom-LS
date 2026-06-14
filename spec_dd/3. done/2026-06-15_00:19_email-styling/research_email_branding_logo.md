# Research: Email Branding — Logo, Absolute URLs, and Fallback

## Recommendation Summary

- **Fix the broken image URL first**: Replace `{% static email_logo_static_path %}` with a fully-qualified URL built from `current_site.domain` + scheme. The scheme should come from `ACCOUNT_DEFAULT_HTTP_PROTOCOL` (already set to `"https"` in `settings_prod.py`) as the single source of truth, so emails work even when triggered without an HTTP request.
- **Unify the settings**: Retire `EMAIL_LOGO_STATIC_PATH` in favour of reading `HEADER_LOGO_STATIC_PATH` directly. The context processor (`email_settings`) currently hard-codes the separate setting; change it to fall back to `HEADER_LOGO_STATIC_PATH` when `EMAIL_LOGO_STATIC_PATH` is `None` (back-compat: `None` is the current default, so the behaviour change is invisible unless `HEADER_LOGO_STATIC_PATH` is set, which is the desired outcome).
- **Unify the label**: Emails currently use `current_site.name` for both the `<img alt>` and the text fallback. Apply the same precedence the web header uses: `HEADER_TITLE → Site.name`. This is already available in context via the `site_config` processor (as `header_title`), but emails do not receive that processor's output — either add it to the email context in `AccountAdapter.send_mail` or expose `header_title` from the `email_settings` processor.
- **Use PNG, not SVG**: SVG as an *embedded* element has only ~40% support; as a linked file it scores ~93% on caniemail but with known caveats in Gmail for non-Google accounts. PNG is universally safe. Do not use SVG for transactional email logos.
- **Always include explicit width/height + meaningful alt text**: Alt text must be the resolved site label (not an empty string). Images are blocked by default in Outlook desktop clients and several corporate environments; when blocked, the alt text is the only visible branding.
- **Plain-text emails cannot show a logo** — they should already use `current_site.name`; update that to use the same label precedence chain (`HEADER_TITLE → Site.name`).

---

## 1. Absolute URLs for Email Images in Django

### The problem in this codebase

`header.html` line 5:
```html
<img src="{% static email_logo_static_path %}" ...>
```
`{% static %}` yields a root-relative path like `/static/images/logo.png`. External email clients (Gmail, Apple Mail, Outlook) load the email in isolation with no host — relative URLs are silently broken; the logo never loads.

### Options

**Option A — `request.build_absolute_uri(static(path))`**

```python
from django.templatetags.static import static
logo_url = request.build_absolute_uri(static(path))
```

Works perfectly when a request is available (the common case for allauth emails triggered by a user action). The scheme follows the live request, so it is correct for both HTTP dev and HTTPS production. The drawback: `allauth_context.request` can be `None` when emails are sent programmatically outside a request cycle (e.g. management commands, background tasks). The codebase already guards against `None` request in `is_open_for_signup`; the same guard is needed here.

**Option B — `current_site.domain` + `ACCOUNT_DEFAULT_HTTP_PROTOCOL`**

```python
from django.templatetags.static import static
from django.conf import settings

protocol = getattr(settings, "ACCOUNT_DEFAULT_HTTP_PROTOCOL", "https")
logo_url = f"{protocol}://{current_site.domain}{static(path)}"
```

This is the most robust approach for this project because:
- It does not depend on a live request existing.
- The scheme is already controlled by `ACCOUNT_DEFAULT_HTTP_PROTOCOL`: `"https"` in `settings_prod.py`, implicitly `"http"` in dev (where Mailpit captures all mail, so correctness is irrelevant).
- `current_site` is always passed into the email context by `AccountAdapter.send_mail` via `get_current_site(request)` (which, when `request` is `None`, still falls back to `settings.SITE_ID` via Django's `Site.objects.get_current`).

**Recommendation**: Use Option B — build the URL in Python (not in the template) and pass it as a context variable, e.g. `email_logo_url`. This keeps the template logic trivial (`{% if email_logo_url %}<img src="{{ email_logo_url }}">{% endif %}`), is request-independent, and piggybacks the existing `ACCOUNT_DEFAULT_HTTP_PROTOCOL` scheme discipline.

### Where to compute the URL

In the `email_settings` context processor, or in `AccountAdapter.send_mail` when constructing the `ctx` dict. The context processor approach is cleanest because it is global and does not require touching `AccountAdapter`. The processor already runs for every template render (including email templates), so adding `email_logo_url` there is zero-friction.

Pseudocode:
```python
# in accounts/context_processors.py → email_settings()
from django.templatetags.static import static
from django.conf import settings

logo_path = settings.EMAIL_LOGO_STATIC_PATH or settings.HEADER_LOGO_STATIC_PATH
if logo_path:
    protocol = getattr(settings, "ACCOUNT_DEFAULT_HTTP_PROTOCOL", "https")
    # current_site is not available in a context processor; pass None path and
    # resolve domain in the adapter or use a template tag instead.
```

Note: The context processor does not have `current_site`, so a hybrid is needed: either compute the URL inside `AccountAdapter.send_mail` (where `current_site` is already at hand), or pass both the protocol and domain as context values and compose the full URL in the template with a custom `fullstatic` tag. The cleanest approach: resolve the full URL in `send_mail` and inject it as `email_logo_url`.

### HTTP vs HTTPS determination

- **When request is available**: use `request.build_absolute_uri(static(path))` — scheme is derived from the live request and HTTPS proxy headers (`SECURE_PROXY_SSL_HEADER`).
- **When request is `None`**: use `ACCOUNT_DEFAULT_HTTP_PROTOCOL` from settings. This setting already exists and is set to `"https"` in prod.
- Dev emails go to Mailpit on port 8025; the scheme does not matter there.

---

## 2. Unifying Email Branding with Web-Header Settings

### Current state

| Setting | Used by |
|---|---|
| `HEADER_LOGO_STATIC_PATH` | Web header (`header_bar.html`) |
| `HEADER_TITLE` | Web header; falls back to `site.name` |
| `EMAIL_LOGO_STATIC_PATH` | Email header only; separate setting, defaults to `None` |

Both settings exist in `settings_base.py`. Dev settings (`settings_dev.py`) set `HEADER_LOGO_STATIC_PATH = "images/first_class_logo.png"` and `HEADER_TITLE = "FirstClass"` but leave `EMAIL_LOGO_STATIC_PATH` unset — so in dev, the email header shows text even though the web header shows a logo.

### Option A — Retire `EMAIL_LOGO_STATIC_PATH`, read `HEADER_LOGO_STATIC_PATH` directly

The `email_settings` context processor changes `email_logo_static_path` to be `HEADER_LOGO_STATIC_PATH`. `EMAIL_LOGO_STATIC_PATH` is removed or left as an override that takes priority when explicitly set.

Back-compat concern: `EMAIL_LOGO_STATIC_PATH` is a documented public setting. Any downstream project that explicitly sets it to `None` to suppress the logo in emails while keeping a logo in the web header would be affected. However, since `EMAIL_LOGO_STATIC_PATH` defaults to `None` and the change only activates when `HEADER_LOGO_STATIC_PATH` is set, existing installs that never set either are unchanged.

### Option B — Keep `EMAIL_LOGO_STATIC_PATH` but default it to `HEADER_LOGO_STATIC_PATH`

```python
email_logo_path = settings.EMAIL_LOGO_STATIC_PATH or settings.HEADER_LOGO_STATIC_PATH
```

This preserves override capability (a downstream project can still set `EMAIL_LOGO_STATIC_PATH = None` to force text) while making the default behaviour "match the web header."

**Recommendation**: Option B. It is strictly additive, preserves the escape hatch, and is a one-line change. Document that `EMAIL_LOGO_STATIC_PATH` defaults to `HEADER_LOGO_STATIC_PATH` if not explicitly set.

### Label precedence chain

Web header context processor (`site_config`) already computes:
```python
"header_title": settings.HEADER_TITLE or site_title
```
where `site_title` itself falls back to `site.name`. Email templates currently use `{{ current_site.name }}` directly — they skip `HEADER_TITLE`. The fix is to expose the same resolved label to email templates. Either:
- add `email_label` (= `HEADER_TITLE or current_site.name`) to the context in `AccountAdapter.send_mail`, or
- inject it via the `email_settings` context processor (but `current_site` is not available there — use `settings.HEADER_TITLE` only, and fall back in the template: `{{ email_label|default:current_site.name }}`).

Both the `<img alt>` and the text `<h1>` fallback should use this resolved label. The plain-text template (`base_email.txt`) uses `{{ current_site.name }}` — it should also pick up `HEADER_TITLE` via the same mechanism.

---

## 3. HTML Email Logo Best Practices

### Alt text

Alt text MUST be the resolved site label (i.e., `HEADER_TITLE → Site.name`). When images are blocked — Outlook desktop blocks by default, and many corporate email gateways do so as policy — the alt text is the only visible branding in the header. An empty or generic alt text means the header appears blank. Styled alt text (inline CSS on the `<img>` tag) can partially approximate the branded look even when the image is absent.

The current template uses `alt="{{ current_site.name }}"`, which is correct in principle; it just needs to pick up `HEADER_TITLE` when set.

### Explicit dimensions

Always set `width` as an HTML attribute (not only CSS) and include `height="auto"` or omit `height` when using CSS `height: auto`. Outlook ignores CSS `max-width` but respects the HTML `width` attribute. The current template has `style="max-height: 48px; width: auto;"` — this is weak for Outlook. Better:

```html
<img src="{{ email_logo_url }}"
     alt="{{ email_label }}"
     width="200"
     style="max-height: 48px; width: auto; display: block; border: 0;" />
```

The exact `width` value depends on the logo; the pattern is: set `width` to the intended display width (in points/px), use `style="height: auto;"` for proportional scaling, and constrain with `max-height` to keep it small in the header.

### Retina / 2x

The recommended email technique (Litmus): supply the image at 2x intrinsic size, set `width` to the 1x display size, and add `style="width:100%; max-width: <1x-size>px;"`. For a logo targeting 100×40 px display, deliver a 200×80 px PNG with `width="100" style="width:100%; max-width:100px; height:auto;"`.

### PNG vs SVG

- **PNG**: universally supported. Safe choice for transactional email logos.
- **SVG as linked `<img src>`**: caniemail score ~93%, but partial support in Gmail on iOS/Android for non-Google accounts (last verified Jan 2023). Risky for transactional email where deliverability matters.
- **Embedded `<svg>`**: caniemail score ~40%. Do not use for email.

**Use PNG.** If the source logo is an SVG, rasterise it to PNG at 2x resolution for email use. This is a one-time asset preparation step and does not affect the web header (which can still use SVG).

### Dark mode

Two scenarios:

1. **Logo on a solid coloured background band** (the current design: header `<td>` has `background-color: {{ email_color_primary }}`): Use a PNG with a transparent background. The logo colours must contrast with `email_color_primary`. Dark-mode-aware email clients may invert colours; a logo with transparent background on a branded band is generally resilient because the band colour is set via inline CSS (not inverted in most clients).

2. **If a separate dark-mode variant is ever needed**: Use `prefers-color-scheme` media query with a `display:none` swap technique. This is an enhancement, not a requirement for the current scope.

For this codebase's implementation, the primary concern is: ensure the PNG has a transparent background so it renders correctly on whatever `email_color_primary` is configured for the theme.

---

## 4. "If Set" Semantics and Fallback

### Full precedence chain

**Logo URL**:
1. Resolve `email_logo_path = EMAIL_LOGO_STATIC_PATH or HEADER_LOGO_STATIC_PATH`
2. If `email_logo_path` is set: build `email_logo_url = f"{protocol}://{current_site.domain}{static(email_logo_path)}"`
3. If `email_logo_url` is not `None`: render `<img src="{{ email_logo_url }}" alt="{{ email_label }}" ...>`
4. Otherwise: render `<h1>{{ email_label }}</h1>` (text fallback)

**Label** (used as `<img alt>` AND as the text fallback heading AND in the plain-text email):
1. `HEADER_TITLE` (if set)
2. `current_site.name` (always set — Django `Site` model requires it)

**Guarantee**: There is always something visible. If neither logo nor `HEADER_TITLE` is configured, `current_site.name` appears as a text `<h1>`. This matches the current behaviour for the no-logo case; the only change is that `HEADER_TITLE` is now respected.

**Plain-text emails**: Cannot and should not show a logo. The `.txt` base template should output the resolved label text (`HEADER_TITLE or current_site.name`). No image references belong in plain-text at all.

---

## 5. Testing Approach (High Level)

### Unit / integration tests

Using `render_to_string` (as the existing `test_email_templates.py` does), add assertions covering:

- When `HEADER_LOGO_STATIC_PATH` is set and `EMAIL_LOGO_STATIC_PATH` is `None`: rendered HTML contains `<img` and the `src` attribute is a fully-qualified URL starting with `http://` or `https://` (not a bare `/static/` path).
- The `<img alt>` attribute equals the resolved label (`HEADER_TITLE` when set, `Site.name` otherwise).
- When neither logo setting is set: HTML contains `<h1` with the resolved label text; no `<img` tag is present.
- When `HEADER_TITLE` is set: both the `alt` attribute (on the logo case) and the `<h1>` text (on the no-logo case) use `HEADER_TITLE`, not `current_site.name`.
- Plain-text email output contains the resolved label but no URL starting with `/static/`.

Keep assertions on string content (URL prefix, tag presence, label text), not CSS classes or inline styles — consistent with project convention.

### Manual QA via Mailpit

Mailpit (dev email viewer at http://localhost:8025) captures all SMTP output. After implementation, manually trigger each email type (verification, password reset, login code) and verify in Mailpit that:
- The logo image is requested from the correct absolute URL (check the "Show original" / raw view for the `src` attribute).
- The HTML preview shows the logo (Mailpit renders HTML; localhost static files should load if the dev server is running on the same host and port as `current_site.domain`).
- The alt text is visible when images are toggled off (some email clients in Mailpit preview support this).

---

## References

- [caniemail: SVG image format (linked)](https://www.caniemail.com/features/image-svg/) — 92.86% support; partial on Gmail iOS/Android non-Google accounts
- [caniemail: Embedded `<svg>` image](https://www.caniemail.com/features/html-svg/) — ~40% support; do not use in email
- [Litmus: Understanding Retina Images in HTML Email](https://www.litmus.com/blog/understanding-retina-images-in-html-email) — 2x PNG, width attribute, max-width CSS technique
- [Litmus: The Ultimate Guide to Email Image Blocking](https://www.litmus.com/blog/the-ultimate-guide-to-email-image-blocking) — alt text as fallback branding
- [Litmus: The Ultimate Guide to Styled ALT Text in Email](https://www.litmus.com/blog/the-ultimate-guide-to-styled-alt-text-in-email) — styled alt text in image-blocked environments
- [django-allauth HTTPS documentation](https://docs.allauth.org/en/dev/common/https.html) — `ACCOUNT_DEFAULT_HTTP_PROTOCOL` controls scheme when request is absent
- [allauth GitHub issue: build_absolute_uri enforces http](https://github.com/pennersr/django-allauth/issues/1258) — confirms `ACCOUNT_DEFAULT_HTTP_PROTOCOL` is the fallback scheme
- [django-fullurl](https://github.com/Flimm/django-fullurl) — third-party `fullstatic` template tag (not needed given the context-based approach recommended here)
- [django-absoluteuri on PyPI](https://pypi.org/project/django-absoluteuri/) — alternative package for absolute URIs without request; uses `ABSOLUTEURI_PROTOCOL` setting
- [Audienceful: Dark Mode Logo Images in HTML Emails](https://www.audienceful.com/help/dark-mode-logo-images-HTML-emails) — transparent PNG approach for dark mode
- [CSS-Tricks: A Guide on SVG Support in Email](https://css-tricks.com/a-guide-on-svg-support-in-email/) — SVG caveats in email

status: ok
