# Research: best practices for the downstream_bugs_oct_29 bundle

Scope note: allauth findings were verified against the installed source in `.venv/lib/python3.13/site-packages/allauth/` (account/adapter.py, account/views.py, account/app_settings.py, templates/account/). Other items are from established Django/WCAG/HTML guidance; URLs are given for the references. I did not re-read the 14 per-bug idea.md files line by line for this unit, so "implies for FLS" lines are written from the challenge descriptions in the brief. The spec author should check them against each idea.md.

## 1. Sanitise Markdown once at the trust boundary (nh3)
- Practice: sanitise exactly once, on the untrusted string, after Markdown-to-HTML conversion and before it is marked safe. Never sanitise already-rendered trusted output again, and never inject untrusted text into trusted output afterwards. Sanitising twice is not unsafe, but it strips the trusted component attributes (the accordion bug). Use an explicit allowlist (`tags`, `attributes`, `url_schemes`, `link_rel`). Do not widen it to cover component attributes such as `x-data` or `@click` globally.
- Nested rendering: render the component's inner Markdown (the untrusted part) with sanitising first. Then wrap it in the trusted component markup, which is produced by templates and not sanitised. Or use placeholders: sanitise the user text, render components, then substitute. Do not use a single global allowlist that admits Alpine/HTMX attributes. Those attributes (`x-html`, `hx-*`, `on*`) are script-execution vectors.
- Refs: https://nh3.readthedocs.io/en/latest/ , https://docs.rs/ammonia/latest/ammonia/ , https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- FLS: find the single boundary where Markdown is cleaned. Keep component output (accordion, cotton) outside it, or pass a per-element attribute allowlist scoped to that component. Test nested components keep their attributes while a raw `<script>` or `onclick` in author text is still stripped.

## 2. Honeypot fields
- Practice: the honeypot widget must never echo a submitted value (override `format_value` to return `None`). A re-rendered value would break the form, and the bug is that the value is rendered back. Use `autocomplete="off"`, `tabindex="-1"`, and `aria-hidden="true"` on the wrapper. Hide it with CSS off-screen (not `display:none`, which some bots detect). The label should say "leave this empty". Error messaging should be generic and give no hint that a trap was tripped. Preferably fail silently, or show the same error as a normal validation failure. Don't put the honeypot's name in an error that is shown to users.
- Refs: https://docs.djangoproject.com/en/stable/ref/forms/widgets/#django.forms.Widget.format_value , https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/autocomplete
- FLS: add `format_value` returning `None` on the honeypot widget. Test that a rerender after a tripped honeypot has no `value=` for it.

## 3. Overriding django-allauth 65.x templates
- Layout: allauth's templates are at `allauth/templates/account/`. Django finds a project template at `templates/account/<name>.html` first if the project `TEMPLATES` dirs (or an app earlier in `INSTALLED_APPS`) shadow it. Override by creating a same-named file. Installed set includes: `base_entrance`, `base_manage`, `base_manage_email`, `base_manage_password`, `base_manage_phone`, `base_reauthenticate`, `base_confirm_code`, `login`, `signup`, `logout`, `email`, `email_change`, `email_confirm`, `password_change`, `password_set`, `password_reset`, `password_reset_done`, `password_reset_from_key`, `password_reset_from_key_done`, `verification_sent`, `verified_email_required`, `account_inactive`, `signup_closed`, `reauthenticate`, the `*_code` templates, and others. Messages are templates too: `account/messages/*.txt` (`email_confirmation_sent.txt`, `email_confirmed.txt`, `logged_in.txt`, etc.).
- Hierarchy: pages extend `base_entrance.html` (login, signup, confirm, reset) or `base_manage.html` (email, password, phone), which extends `allauth/layouts/base.html`. The hierarchy then goes `allauth/layouts/base.html` -> `{% extends "allauth/layouts/base.html" %}`. Safest override: provide your own `allauth/layouts/base.html` (and `entrance.html` / `manage.html` layouts) so all pages inherit the site's chrome and copy, and only override individual pages for copy changes. `base_manage_email.html` and `base_manage_password.html` exist for per-feature chrome.
- Settings:
  - `ACCOUNT_PREVENT_ENUMERATION` (default True): responses must not reveal whether an address exists. Do not write copy or add redirects that leak existence.
  - `ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL` (default None, then falls back to `get_login_redirect_url`) and `ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL` (default `LOGIN_URL`): where confirmation lands.
  - `ACCOUNT_LOGOUT_ON_GET`: avoid True (CSRF logout); keep POST logout.
  - `ACCOUNT_EMAIL_NOTIFICATIONS`: default False; when True, allauth sends notification mail on email/password changes.
  - `ACCOUNT_CHANGE_EMAIL`: True switches `EmailView` to `email_change.html` (single pending address). `ACCOUNT_MAX_EMAIL_ADDRESSES` caps the number of addresses (default None).
- `next` across confirmation: `ConfirmEmailView.get_redirect_url()` uses `self.get_next_url()` first (the `next` param from NextRedirectMixin, already host-checked), and otherwise `adapter.get_email_verification_redirect_url(email_address)`. That method (65.x) chooses `EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL` or `get_login_redirect_url` when authenticated, else the anonymous URL. The older hook `get_email_confirmation_redirect_url(request)` is deprecated and, if defined on the adapter, takes precedence. Override `get_email_verification_redirect_url` rather than the deprecated one. `get_login_redirect_url(request)` is only the default: an explicit `next` wins. The confirm link does not carry `next` by default; to preserve it, add it to the confirmation URL in a custom `send_mail` / confirmation URL path, or store it in the session.
- Already-verified re-click: `ConfirmEmailView.get_object` uses `EmailConfirmationHMAC.from_key(key)` (HMAC) and falls back to the stored `EmailConfirmation`. A re-click of an already-verified link still resolves and renders `email_confirm.html` with context `can_confirm = email_address.can_set_verified()`. Detect already verified with `confirmation.email_address.verified` (available as `confirmation.email_address`) in a `get_object` / `get` override or in the template context, and redirect with an info message.
- "Email added" message: allauth emits messages via `adapter.add_message(request, level, message_template, message_context)`, rendering `account/messages/<name>.txt`. Customise by overriding the template `account/messages/email_confirmation_sent.txt` (simplest), or by overriding `add_message` in the adapter to substitute copy by template name.
- Refs: https://docs.allauth.org/en/latest/account/configuration.html , https://docs.allauth.org/en/latest/common/templates.html , https://docs.allauth.org/en/latest/account/adapter.html
- FLS: one shared allauth layout override that extends FLS's base template fixes "stock templates and copy" for every page. Use `get_email_verification_redirect_url`, not the deprecated hook. Add an already-verified branch rather than re-rendering the confirm page.

## 4. Preserving the current page through login/signup links
- Practice: link to login/signup with `?next=<urlencoded current path + query>` (`{{ request.get_full_path|urlencode }}`). On the receiving side, validate with `url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure())` (allauth does this in `NextRedirectMixin`). Use `redirect_to_login(next, login_url)` for views, and `LOGIN_URL` for the fallback. Do NOT set `next` on auth pages themselves (loops, `next=/accounts/login/`), on logout, or on POST-only endpoints (a GET after login would 405). Keep the `next` field through the login/signup cross-links.
- Refs: https://docs.djangoproject.com/en/stable/ref/utils/#django.utils.http.url_has_allowed_host_and_scheme , https://docs.djangoproject.com/en/stable/topics/auth/default/#django.contrib.auth.views.redirect_to_login
- FLS: build the header links in one template tag or context helper that omits `next` when the current URL is under `/accounts/` or the view is POST-only.

## 5. Accessible page structure
- One `h1` per page, describing the page. The site name in the header should be a link in a `<div>`/`<a>` (not a heading). Add a skip link as the first focusable element (`<a href="#main-content" class="sr-only focus:not-sr-only">`), with `<main id="main-content" tabindex="-1">` (WCAG 2.4.1, technique G1). Error summaries use `role="alert"` (or move focus to the summary after a failed submit); link each field error with `aria-describedby` and set `aria-invalid="true"`. Name fields: `autocomplete="given-name"` and `"family-name"` (or `name`).
- Refs: https://www.w3.org/WAI/WCAG22/Techniques/general/G1 , https://www.w3.org/WAI/WCAG22/Understanding/bypass-blocks.html , https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill , https://www.w3.org/WAI/tutorials/page-structure/headings/
- FLS: change the header site name from `h1` to a non-heading and keep each page template's own `h1`. Tailwind's `sr-only` plus `focus:not-sr-only` provides the skip link.

## 6. Django form/view idioms
- PRG: after a successful POST, `redirect()`; never render the success on POST. Use `messages.info/success` for notices that must survive the redirect. For HTMX, return 422 on validation errors (project convention, `claude_plugins/fls-dev/resources/templates_and_cotton.md`). Model `blank=True` does not make a ModelForm field optional in the opposite direction: if the product requires a name, set `required=True` on the form field (override in `__init__`/Meta). `CharField` strips by default (`strip=True`), so whitespace-only counts as empty and fails `required`. The profile blank-name bug is a form-level gap.
- Refs: https://docs.djangoproject.com/en/stable/ref/forms/fields/#charfield , https://docs.djangoproject.com/en/stable/ref/contrib/messages/ , https://en.wikipedia.org/wiki/Post/Redirect/Get
- FLS: set `required=True` explicitly on the profile form's name fields, keep model `blank=True`, and test a whitespace-only value.

## 7. Access-control checks gated by a model attribute
- Practice: fail closed. Evaluate the gate explicitly (for example `course.requires_application` or equivalent), and deny if the attribute is missing/unknown. Choose redirect (to a useful page, with a message) when the user can act; 404 when the resource should not be discoverable. Keep an existing-record short-circuit (already registered/applied: send them to the course) before the gate, so legitimate existing users are not blocked. Order: existing-record check, then gate, then create.
- Ref: https://docs.djangoproject.com/en/stable/topics/auth/default/#limiting-access-to-logged-in-users-that-pass-a-test (pattern); OWASP "Deny by default": https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- FLS: the apply view should reject courses that need no application (redirect to the course, or 404), and a registered learner on a gated course should short-circuit to the course page, not the apply form.

## 8. Portable tests in a reusable app
- Practice: tests in a reusable app must pin every setting they depend on (`@override_settings` or the pytest-django `settings` fixture) and assert against the configured value (`settings.X`, `reverse()`), never a literal that only holds with FLS's defaults. A fixture that renders before the test body will see unpinned settings: pin in a fixture that the rendering fixture depends on (declare it first / use `autouse`), not inside the test body. Downstream `pyproject.toml` `--deselect` of an FLS test is a smell that the test is not portable. Fix the test.
- Refs: https://pytest-django.readthedocs.io/en/latest/helpers.html#settings , https://docs.djangoproject.com/en/stable/topics/testing/tools/#overriding-settings
- FLS: the icon-intrinsic-size and sidebar-sections tests should pin the icon set / `MESSAGING_ENABLED`-style flag and compare against it. After the fix, the concrete project should drop its deselects.

## 9. Content validation for authored course content
- Practice: validate at import/save time and fail with a message that names the file path and field (and ideally line). Add UI defence in depth: a content item that is nonetheless invalid renders a visible, safe fallback, not a 500 (for example the zero-page form that blocks course completion: reject at import and treat as complete/hidden at runtime).
- Ref: https://docs.pydantic.dev/latest/concepts/validators/ (errors with `loc`); https://docs.djangoproject.com/en/stable/ref/models/instances/#validating-objects
- FLS: reject forms with zero pages in the content schema validation, with the content path in the error. Make completion logic tolerate zero pages as well.

## 10. `<pre>` overflow and Mermaid
- `<pre>` blocks: `overflow-x: auto; max-width: 100%` (Tailwind `overflow-x-auto max-w-full`) on the pre, with `min-width: 0` on flex/grid parents so they can shrink.
- Mermaid: it is client-side (mermaid.js), initialised lazily only on pages containing `.mermaid`/`pre code.language-mermaid`, with `securityLevel: 'strict'` (default) and `startOnLoad: false`. It adds a JS dependency and an HTML-injection surface in diagrams. If the product will not ship it, reject ```mermaid blocks at content validation, with a clear path in the error, instead of rendering a raw code block.
- Refs: https://mermaid.js.org/config/usage.html , https://mermaid.js.org/config/security.html , https://developer.mozilla.org/en-US/docs/Web/CSS/overflow
- FLS: the cheaper, safer path is to reject Mermaid at validation unless it is explicitly requested. Fix the overflow with a CSS rule in the prose styles.

## 11. Save-on-exit partial persistence
- Practice: a "leave and save" control submits to a dedicated endpoint/handler (or `formnovalidate` submit button with its own `name`), which saves the current page's raw answers without validation, then redirects away. It must not mark the page complete. The dialog copy must state what actually happens ("Your answers on this page are saved").
- Refs: https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/formnovalidate , https://developer.mozilla.org/en-US/docs/Web/HTML/Element/button#formnovalidate
- FLS: include the current page's posted values in the leave-and-save path (the bug discards them). Server-side must not require validation for that action. Update the copy to match.

## 12. `<title>` and meta description
- Convention: "Page title | Site name" (page first, site name last; one separator). Build in one place: base template `{% block title %}{% endblock %} | {{ site_name }}`, with child pages only supplying the page part. Meta description per page (about 150-160 chars) via a block with a site-level fallback.
- Refs: https://developers.google.com/search/docs/appearance/title-link , https://developers.google.com/search/docs/appearance/snippet , https://www.w3.org/WAI/WCAG22/Techniques/html/H25
- FLS: append the site name only in the base template; have pages supply just their own title and an optional description.

## 13. Dates
- Practice: format with Django's `{{ value|date:"SHORT_DATE_FORMAT" }}` / `DATE_FORMAT` (locale-aware via `USE_L10N`, always on in Django 5+) instead of hard-coded format strings. Pick one short date format for the product, defined once.
- Ref: https://docs.djangoproject.com/en/stable/ref/templates/builtins/#date , https://docs.djangoproject.com/en/stable/ref/settings/#date-format
- FLS: replace literal `"d M Y"`-style strings in templates with the named formats.

## 14. Phone validation without libphonenumber
- Practice: be permissive. Strip spaces, dashes, brackets, then require an optional leading `+` and a minimum digit count (about 7) and a sensible maximum (E.164 is 15). Use `type="tel"`, `inputmode="tel"`, and `autocomplete="tel"`. A `pattern` is only a UI hint; validate server-side with a `RegexValidator`.
- Refs: https://en.wikipedia.org/wiki/E.164 , https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/inputmode
- FLS: a single reusable validator that counts digits, applied to the form field.

## 15. HTMX pagination that survives Back
- Practice: `hx-push-url="true"` adds a history entry per page click (Back steps through pages). `hx-replace-url` keeps one entry. For pagination you want Back to return to the previous page, so use `hx-push-url`, and have the view read `?page=` on a full page load too (a `clamped_page`-style helper that parses, clamps to 1..num_pages, and falls back safely on garbage). Use `hx-history` caching carefully, and return the full page for non-HTMX requests (`HX-Request` header) to survive refresh and Back after cache eviction.
- Refs: https://htmx.org/attributes/hx-push-url/ , https://htmx.org/attributes/hx-replace-url/ , https://docs.djangoproject.com/en/stable/ref/paginator/
- FLS: keep the page number in the URL so the server restores it on reload, and clamp it.

## 16. Feature flags must silence producers and consumers
- Practice: gate at the source of the effect (the producer function, for example `raise_notification` returns early when `NOTIFICATIONS_ENABLED` is False) as well as the consumers (views, URLs, header bell, sidebar). Otherwise rows accumulate invisibly and surface when the flag flips. Read the setting at call time, not import time, so `override_settings` works.
- Ref: https://docs.djangoproject.com/en/stable/topics/settings/#using-settings-in-python-code
- FLS: add the flag check to `raise_notification` and the notification views, and make the sidebar test pin the flag (see section 8).

status: ok
