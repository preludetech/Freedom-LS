---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/account/signup.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: signup honeypot rejects real people whose browser autofills it

Bug fix. Before this change, browser autofill and password managers filled the signup honeypot
with the person's surname, and the signup was rejected with "Submission could not be processed."
Real people could not create accounts, and nothing was logged.

## Breaking changes

- The honeypot field on `SiteAwareSignupForm` is renamed from `_hp` to `fax_number`, and its
  widget is now `freedom_ls.accounts.forms.HoneypotInput`. It reports itself as hidden, so it
  appears in `form.hidden_fields` and no longer in `form.visible_fields`. It still renders as
  `type="text"`. If your project subclasses `SiteAwareSignupForm` and references `_hp` or
  overrides `clean__hp`, move that code to `fax_number` and `clean()`.
- A filled honeypot now adds a form-level error (`form.non_field_errors`), not a field error.
  The message is: "We couldn't process this sign-up. If you used autofill or a password manager,
  please try typing your details in by hand."
- Every rejection logs a `WARNING` on the `freedom_ls.accounts.forms` logger with the site domain
  and client IP. The log never includes the email or the honeypot value.

## Manual steps

If your project doesn't override `account/signup.html`, there's nothing to do.

If it does, make the same two changes to your copy that were made to
`freedom_ls/base/templates/account/signup.html`:

1. Render `form.non_field_errors` near the top of the form. Without this, a rejected submission
   re-renders the page with no message.
2. Render the hidden fields bare, inside an element with the `hidden` attribute:

   ```django
   <div hidden>{% for field in form.hidden_fields %}{{ field }}{% endfor %}</div>
   ```

   If your copy loops over `form.visible_fields` and never prints `form.hidden_fields`, the
   honeypot isn't rendered at all. Signups still work, but bots aren't caught. If your copy
   renders the whole form at once (`{{ form }}`, `form.as_p`), the honeypot shows up as a
   visible, unlabelled text box.
