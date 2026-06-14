# QA Report — Theme & site branding in emails

**Date:** 2026-06-14
**Branch:** `email-styling`
**Test plan:** `3. frontend_qa.md`
**Method:** Playwright MCP driving the dev site + Mailpit (`http://localhost:8025`); emails inspected both as rendered HTML and via the Mailpit JSON API (raw HTML / text source).
**Active theme:** `default` (`FLS_THEME` is unset → defaults to `"default"`; dev settings do not override it). The QA plan anticipates this — its radius expectation lists `default theme → 0.375rem`.

## Summary

| Test | Description | Result |
|------|-------------|--------|
| 1 | Signup verification email | **PASS** (with radius bug below) |
| 2 | Password reset email | **PASS** (with radius bug below) |
| 3 | Login-code email | **SKIPPED** — feature not enabled (`/accounts/login/code/` → 404, plan says skip) |
| 4 | Plain-text part | **PASS** |
| 5 | Text-label fallback (no logo) | **PASS** |
| 6 | Email-logo override precedence | **PASS** |
| Mobile (375×812) | Email responsive render | **PASS** |
| Tablet (768×1024) | Email responsive render | **PASS** |

The two previously-fixed bugs both verified as fixed:
- **Logo image loads** — every email `<img src>` is a fully-qualified `http://127.0.0.1:8773/static/images/first_class_logo.png` (no bare `/static/...`, no `https`/no-port form); the URL returns HTTP 200 and the logo renders.
- **Font-family present** — the email body declares `font-family:"Helvetica Neue", Arial, sans-serif` (readable sans-serif, no serif fallback).

One **bug** was found (button radius is not driven by the theme token — details below). It is masked under the default theme but fails an explicit spec acceptance criterion.

---

## Bug 1 — CTA button radius is hardcoded `6px`, not driven by the theme token

**Tests affected:** Test 1 (signup verification), Test 2 (password reset). Also present in the `account_already_exists` and `unknown_account` email templates.

**Expected** (spec `1. spec.md` §2.3, lines 159–160 and Acceptance line 236–237):
> "...expose as `email_button_radius` and use it in `.email-button` in `base_email.html` **in place of the hardcoded `border-radius: 6px`**."
> "`EMAIL_BUTTON_RADIUS` reflects `--fls-radius-md`; **rendered button HTML contains the resolved radius value rather than a stale hardcoded one.**"

So the rendered CTA `<td>` should carry `border-radius: 0.375rem` (the resolved `EMAIL_BUTTON_RADIUS` for the active default theme).

**Actual:** every CTA button still emits a **hardcoded** `border-radius: 6px`. The plumbing was only half-wired:
- `EMAIL_BUTTON_RADIUS` is correctly resolved and exposed as `email_button_radius` (context processor), and the `.email-button` CSS class in `base_email.html` *does* use `{{ email_button_radius }}`.
- **But no email template actually uses the `.email-button` class.** Each CTA rolls its own `<td>`-based button with an inline literal `border-radius: 6px`:
  - `freedom_ls/accounts/templates/account/email/email_confirmation_message.html:10`
  - `freedom_ls/accounts/templates/account/email/password_reset_key_message.html:11`
  - `freedom_ls/accounts/templates/account/email/account_already_exists_message.html:11`
  - `freedom_ls/accounts/templates/account/email/unknown_account_message.html:11`

Raw-source confirmation (password-reset email): the button `<td>` is
`<td style="background-color: #2b6cb0; border-radius: 6px;">` — a stale literal, not `0.375rem`.

**Impact:** Under the default theme `6px == 0.375rem`, so it looks correct today and the visual QA passes. But the radius is **not** theme-driven: switching to a theme with a different `--fls-radius-md` (e.g. `first_class` = `0.5rem` / 8px) would still render `6px`. This contradicts the feature's stated goal ("drive the button radius from theme tokens") and the explicit acceptance criterion. The `email_button_radius` value / `.email-button` class are effectively dead for the real CTAs.

**Suggested fix:** make the CTA buttons consume `{{ email_button_radius }}` (either by adopting the `.email-button` class, or by replacing the inline `border-radius: 6px` with `border-radius: {{ email_button_radius }}`) across the four CTA templates. TDD: add a render test asserting the CTA button HTML contains the resolved radius (and changes when the theme token changes), then fix the templates.

Confirmation email (button visible, themed):
![](screenshots/desktop_1_confirmation_email.png)

Password-reset email:
![](screenshots/desktop_2_password_reset_email.png)

---

## Test detail

### Test 1 — Signup verification email — PASS
Registered a fresh account via `/accounts/signup/`; opened "[Demo] Confirm your email address" in Mailpit.
- Logo `<img>` loads from absolute `http://.../static/images/first_class_logo.png` (HTTP 200), `alt="FirstClass"` (the resolved label, not `DemoDev`). Explicit `width="180"` present (Outlook).
- No modern colour syntax anywhere in the source — searches for `oklch`, `oklab`, `color-mix`, `var(`, `hsl(`, `rgb(` all return 0; every colour is `#rrggbb`.
- Theme colours applied: header band & button & links `#2b6cb0`, body text `#1a2332`, surfaces `#fff` / `#f3f4f6`.
- Body font is the email-safe sans-serif stack `"Helvetica Neue", Arial, sans-serif`.
- Sign-off "The FirstClass Team"; footer "© 2026 FirstClass | 127.0.0.1".
- (See Bug 1 re: button radius.)

> Note: signing up with an email that already exists (`qa_verify_1@…` from a prior run) correctly produces an "Account already exists" email instead — allauth enumeration protection. Used a fresh address to exercise the genuine confirmation template.

### Test 2 — Password reset email — PASS
Triggered via `/accounts/password/reset/` for `demodev_s1@email.com`; opened "[Demo] Reset your password".
- Same branding as Test 1: absolute-URL logo, `FirstClass` alt, themed colours, sans-serif font, no modern colour syntax.
- "Reset Password" button present, styled with the theme primary `#2b6cb0`.
- Sign-off "The FirstClass Team"; footer shows site domain `127.0.0.1`.
- (See Bug 1 re: button radius.)

### Test 3 — Login-code email — SKIPPED
`/accounts/login/code/` returns **404** — login-by-code is not enabled on this site. The plan explicitly says to skip when this page 404s. Not a data gap (no `qa-data-helper` setup could enable a disabled feature), so legitimately skipped.

### Test 4 — Plain-text part — PASS
Inspected the **Text** part of both the confirmation and reset emails:
- Sign-off uses the label: "The FirstClass Team".
- Footer line shows the label + domain: "FirstClass | 127.0.0.1".
- **No image references** and **no `/static/...` URLs** — the only links are the action URLs (`http://127.0.0.1:8773/accounts/...`).

### Test 5 — Text-label fallback (no logo) — PASS
Temporarily set `HEADER_LOGO_STATIC_PATH = None` (and left `EMAIL_LOGO_STATIC_PATH` unset) in `config/settings_dev.py`, restarted, re-triggered the reset email.
- No `<img>` in the email (0 image tags).
- The header band instead renders a **text heading** `<h1 style="…color:#ffffff…">FirstClass</h1>` (the resolved label) on the themed primary band.
- All other theming (band colour, body, button, footer) intact.
- `config/settings_dev.py` restored afterwards (verified: empty `git diff`).

![](screenshots/desktop_5_text_label_fallback.png)

### Test 6 — Email-logo override precedence — PASS
Restored `HEADER_LOGO_STATIC_PATH` and set `EMAIL_LOGO_STATIC_PATH = "images/qa_email_override_logo.png"` (a temporary copy of the logo at a distinct path, served 200), restarted, re-triggered the reset email.
- The email `<img src>` resolved to `…/static/images/qa_email_override_logo.png` — the **`EMAIL_LOGO_STATIC_PATH`** value, **not** the header logo — confirming the explicit email setting wins over `HEADER_LOGO_STATIC_PATH`.
- `config/settings_dev.py` restored and the temporary image removed afterwards (verified: empty `git diff`, only `first_class_logo.png` remains under `static/images/`).

![](screenshots/desktop_6_email_logo_override.png)

### Mobile (375×812) & Tablet (768×1024) — PASS
Rendered the reset email HTML directly at each viewport.
- **Mobile:** the `max-width:600px; width:100%` table shrinks to the viewport; logo scales within the header band, no horizontal overflow, body text readable, the "Reset Password" button is a comfortable touch target.
- **Tablet:** the email is centred at its 600px max-width with the grey background filling the margins; logo, button, and footer all render correctly.

![](screenshots/mobile_2_password_reset_email.png)
![](screenshots/tablet_2_password_reset_email.png)

---

## Tangential / out-of-place observations (not bugs in the feature under test)

- **Greeting uses the raw site name, sign-off/footer use the label.** The reset email body reads "…your account at **Demo**" (`{{ current_site.name }}` = `Demo`) while the sign-off/footer use the **FirstClass** label. This appears intentional (greeting = site name, sign-off = resolved email label) and is not a styling defect, but the mixed identity ("Demo" vs "FirstClass") in one message may be worth a product decision. The dev prereqs note assumes `current_site.name` is `DemoDev`; the actual Site row's name is `Demo`, which is why the greeting shows `Demo`. Purely a test-data/site-naming detail, unrelated to the email-styling code.

## Notes on test execution
- All emails were triggered against the dev server on the auto-selected port (8773); the branch badge confirmed the server was on `email-styling`.
- `config/settings_dev.py` edits for Tests 5 & 6 were temporary and have been fully reverted (confirmed via `git diff`).
