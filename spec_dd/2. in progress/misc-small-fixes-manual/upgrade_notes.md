---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/base/templates/cotton/button.html
  - freedom_ls/content_engine/templates/cotton/accordion.html
  - freedom_ls/content_engine/templates/cotton/flashcard.html
  - freedom_ls/content_engine/templates/cotton/picture.html
  - freedom_ls/content_engine/templates/cotton/table.html
  - freedom_ls/learner_interface/templates/cotton/course-card-shell.html
  - freedom_ls/learner_interface/templates/cotton/course-row-shell.html
  - freedom_ls/learner_interface/templates/cotton/player-footer.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_page.html
  - freedom_ls/learner_interface/templates/learner_interface/course_topic.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS            # hard: add "freedom_ls.mail" or its system check never runs
  - MARKDOWN_ALLOWED_TAGS     # hard: c-flashcard needs {"size"} or the attribute is dropped silently
  - EMAIL_BACKEND             # optional: unchanged default; opt in to queueing here
  - EMAIL_UPSTREAM_BACKEND    # hard once queueing is on: freedom_ls_mail.E001 enforces it at boot
  - EMAIL_TIMEOUT             # optional: recommended, defaults to unset (waits forever)
  - SILENCED_SYSTEM_CHECKS    # optional: only if you pinned mid-branch and silenced freedom_ls_deployment.E007
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: misc small fixes

Three separate things landed on this branch, and two of them need work downstream:

1. **A new `freedom_ls.mail` app** holds outgoing email. The default is unchanged — SMTP,
   sent in the request — but a deployment can now hand mail to the task queue instead.
2. **Component styling moved into each component's own template.** Two stylesheets were
   deleted, seven theme tokens removed, and a handful of class families left the compiled
   bundle. Nothing about the rendered look changed; what changed is where the CSS lives
   and how you override a component.
3. **Admin polish, form-player chrome and report print colours** — mostly self-contained,
   with two things to check if you have shadowed the templates.

`setup_initial_prod_data` also grew a required flag. See "Breaking changes".

## Breaking changes

### `setup_initial_prod_data --site-name` is now required

The command used to fall back to the resolved domain. It now insists on a display name,
because that name is what appears in email subject lines, on cohort reports and in the
navigation bar, and a bare domain reads badly in all three. A deploy runbook that calls
it without the flag will fail:

```diff
- python manage.py setup_initial_prod_data admin@example.com
+ python manage.py setup_initial_prod_data admin@example.com --site-name "Example Academy"
```

`HEADER_TITLE` still overrides it later without a database edit.

### Email subjects are now prefixed with the installation's display name

`AccountAdapter.format_email_subject` prefixes with `HEADER_TITLE`, falling back to the
`Site` row's name — the same resolution the site header and the cohort reports use.
allauth's default prefixed with the raw `Site.name` resolved from the HTTP host, which
disagreed with the email body and ignored `FORCE_SITE_NAME`. If you assert on subject
lines in your own tests, they will need updating. Setting
`ACCOUNT_EMAIL_SUBJECT_PREFIX` still wins outright, as before.

### Two stylesheets were deleted

`tailwind.base_interface.css` and `tailwind.picture_spotlight.css` are gone; their rules
moved into `_base_interface.html` and `cotton/picture.html`. A downstream project owns its
own `tailwind.input.css`, so **your build will fail until you delete both `@import` lines
from it.** See "Manual steps".

### Seven theme tokens no longer exist

A `theme.css` that sets any of them is now setting a variable nothing reads — silently,
with no build error:

| Removed token | Where the value lives now |
|---|---|
| `--fls-flashcard-back-gradient` | `cotton/flashcard.html`, as `--flashcard-*` custom properties in its own `<style>` block |
| `--fls-flashcard-back-fg` | same |
| `--fls-flashcard-back-accent` | same |
| `--fls-flashcard-back-border` | same |
| `--fls-card-radius` | `.course-card` in `tailwind.components.css` (`rounded-2xl`) |
| `--fls-card-hero-height` | `h-28` on `cotton/course-card-shell.html` |
| `--fls-card-padding` | `p-4` on both course-card shells |

To restyle the flashcard's answer face, shadow `cotton/flashcard.html` and retune the four
custom properties at the top of its `<style>` block. Every descendant rule follows them.
`--fls-course-accent-*` is unchanged and is still the way to rebrand course cards.

### Class families were removed from the compiled bundle

They are no longer generated anywhere, so any downstream markup or test that reaches for
one now matches nothing:

`.flashcard-*` (except `.flashcard-back`, which the component's own `<style>` still uses),
`.accordion`, `.accordion-summary`, `.accordion-title`, `.accordion-body`,
`.accordion-body-inner`, `.accordion-chevron`, `.picture-figure-ref`,
`.picture-figure-title`, `.course-card-hero`, `.course-card-body`,
`.htmx-hide-on-request`, `.htmx-show-on-request`.

`.spotlight-dialog` and `.side-panel-*` also left the bundle, but the side-panel classes are
still applied by `_base_interface.html` and styled from its own `<style>` block, so a
selector against `.side-panel-body` still resolves.

The htmx loading-state pair is the one with a real trap: a template of yours carrying
`class="htmx-hide-on-request"` will simply stop hiding, with no error. `c-button`'s
`loading` prop is unaffected — it now uses a `[.htmx-request_&]` descendant variant instead.

### A theme can no longer restyle these components from `theme.css`

A component's `<style>` block sits later in document order than the compiled bundle, so
within `@layer components` it wins. Restyle them by shadowing the template at
`themes/<slug>/templates/cotton/<name>.html`, which now carries the markup and the look in
one file. The Tier-2 surface is exactly the class list in `docs/how tos/theme-fls.md`:
`.btn` and its variants, `.chip` and its variants, `.alert` and its variants, `.surface`,
`.signup-panel`, `.header`, `.course-card`, `.course-accent-1`–`5`, `.course-progress-1`–`5`,
and `.modal-backdrop` / `.modal-backdrop-host`. Nothing outside that list is re-openable.

### `c-flashcard` gained a `size` attribute, and your allowlist has to admit it

A project supplies its own `MARKDOWN_ALLOWED_TAGS`, and nh3 strips any attribute outside it
*silently*. Until you add `size`, `<c-flashcard size="wide">` renders a standard-width card
with no error and no warning:

```diff
  MARKDOWN_ALLOWED_TAGS = {
-     "c-flashcard": set(),
+     "c-flashcard": {"size"},
  }
```

A wide card fills more of the content column on a large screen and left-aligns both faces,
so an answer holding a table or a code block reads properly. Existing flashcards are
untouched — the default is the width they already had, and an unrecognised value falls back
to it.

### `c-table` is documented as top-level only

No code changed for this, but the constraint is now stated in the component: a component
whose body is author markdown re-sanitises the already-rendered wrapper and strips its
classes, `tabindex` and `role`. A `c-table` nested inside `c-accordion`, a flashcard slot or
`c-admonition` has been rendering as an unstyled, unscrollable table all along. Course
content that does this should use a plain markdown table instead.

## Manual steps

1. **Add the mail app to `INSTALLED_APPS`:**

   ```diff
     "freedom_ls.deployment",
   + "freedom_ls.mail",
     "freedom_ls.health",
   ```

   Without it the app's system check is never registered, so the misconfiguration in
   step 2 goes unreported. Nothing else about your email setup changes: `EMAIL_BACKEND`
   still defaults to `django.core.mail.backends.smtp.EmailBackend` and mail is still sent
   inside the request.

2. **Decide whether to queue outgoing email.** Optional, and off by default because queued
   mail with no worker behind it is accepted and never sent. To turn it on you must already
   be running `manage.py fls_run_worker`:

   ```python
   EMAIL_BACKEND = "freedom_ls.mail.backends.QueuedEmailBackend"
   EMAIL_UPSTREAM_BACKEND = "django.core.mail.backends.smtp.EmailBackend"  # or your provider's
   ```

   `EMAIL_BACKEND` names the queue; `EMAIL_UPSTREAM_BACKEND` names what is behind it, and is
   what the worker actually sends through. Point the second back at the first and every send
   re-enqueues a copy of itself and no mail is ever delivered — `manage.py check` reports
   that as **`freedom_ls_mail.E001`**, and it runs everywhere, not just under `--deploy`.
   `EMAIL_UPSTREAM_BACKEND` defaults to SMTP, so leaving it unset is safe.

   One note on the check id, if you track this branch rather than releases: an earlier
   commit on it registered this same check as `freedom_ls_deployment.E007` before the mail
   app existed. It never reached `main`, so a project that upgrades from release to release
   has nothing to change. If you did pin to a mid-branch commit and silenced
   `freedom_ls_deployment.E007`, rewrite that entry in `SILENCED_SYSTEM_CHECKS` to
   `freedom_ls_mail.E001` — silencing the old id still succeeds and now silences nothing,
   with no error to tell you. `freedom_ls_deployment.E007` is retired and will not be
   reused.

   Queued mail is enqueued at priority 10, ahead of the 0 that webhook delivery and report
   rendering use, so a password reset is not stuck behind a cohort report. That does not
   preempt a render already in progress — run a second worker if you need queued mail
   insulated from long renders. Note also that the message body waits in the database, so a
   dump taken inside the prune window carries unexpired password-reset and
   signup-verification links.

3. **Set `EMAIL_TIMEOUT`.** Recommended whether or not you queue. Unset, `smtplib` inherits
   Python's global default of `None` and a black-holed mail host hangs forever — holding the
   request open, or stalling every other queued task behind it. FLS's own `settings_prod`
   reads it from the environment and defaults to
   `freedom_ls.mail.settings_defaults.EMAIL_TIMEOUT_SECONDS`, which is 10.

4. **Add `size` to your `c-flashcard` entry in `MARKDOWN_ALLOWED_TAGS`**, as shown above.
   Skip it and the attribute is silently dropped.

5. **Delete the two dead imports from your own `tailwind.input.css`**, then rebuild:

   ```diff
   - @import "./tailwind.base_interface.css";
   - @import "./tailwind.picture_spotlight.css";
   ```

   ```
   npm run tailwind_build
   ```

   Without the rebuild the old rules stay in your compiled bundle and duplicate the ones the
   templates now emit.

6. **Grep your project for the removed class names** listed above, and for the seven removed
   tokens in every `theme.css` you ship. Neither produces a build error.

7. **If a theme of yours re-opened `.flashcard-*`, `.accordion-*`, `.picture-figure-*`,
   `.spotlight-dialog` or `.side-panel-*` in its `theme.css`**, move that work into a Tier-3
   template shadow. The rules will not take effect where they are.

8. **If you shadow `cotton/flashcard.html`**, take the layering change with it: the flip
   trigger now carries no `z-index` and the face stack carries `pointer-events-none`, so a
   table or code block on the answer face — which the component's `<style>` block gives its
   own horizontal scroll — can actually be swiped. A shadow that keeps the old `z-10` trigger
   keeps the bug: a wide answer pushes the card off a narrow viewport.

9. **If you shadow any of the form-player templates** (`course_form.html`,
   `course_form_page.html`, `course_form_complete.html`, `course_topic.html`), re-apply your
   customisations. The footer buttons moved into a new shared
   `cotton/player-footer.html`, so the start page and the completion page now carry the same
   chrome as the rest of the player, and `course_form_complete.html` gained a working
   Previous button — `course_form_complete` now passes `previous_url` into the context.

10. **If you shadow `reports/static/reports/print.css`**, note that the report no longer
    draws its page and its table fills from the theme's `--color-surface` /
    `--color-surface-2`. A theme is free to tint those, and on paper a tinted surface reads
    as a panel laid over the page rather than as the page. Two report-owned neutrals,
    `--report-paper` (`#FFFFFF`) and `--report-fill` (`#F2F2F2`), replace them. Every other
    colour is still a theme token.

No `migrate`, no `npm install` and no package upgrade.
