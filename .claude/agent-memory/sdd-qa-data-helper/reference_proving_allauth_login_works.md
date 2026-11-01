---
name: Proving a QA user can really log in (allauth verification gate)
description: force_login proves nothing about the email-verification gate; use a rolled-back real login POST plus a negative control
metadata:
  type: reference
---

## Why `check_password` and `force_login` are not proof

`ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (config/settings_base.py, with
`ACCOUNT_LOGIN_METHODS = {"email"}`). Two common false positives:

- `user.check_password(pw)` -> True only tests the hash; allauth still bounces the
  session to `/accounts/confirm-email/` when there is no verified `EmailAddress`.
- `client.force_login(user)` **bypasses the login view entirely**, so it skips the very
  gate under test. It is the right tool for smoke-testing an inner page, the wrong tool
  for answering "can this user log in?".

## The check that actually proves it

Real POST through allauth's view, wrapped in a rolled-back `transaction.atomic()` so no
`django_session` / `axes.AccessLog` rows survive:

```python
c = Client(HTTP_HOST="127.0.0.1:8000")   # dev site resolution is by Host header
c.get(reverse("account_login"))
r = c.post(reverse("account_login"), {"login": EMAIL, "password": PW}, follow=True)
# PASS: redirect_chain == [('/', 302)], session["_auth_user_id"] set
# FAIL: redirect_chain == [('/accounts/confirm-email/', 302)], _auth_user_id is None
```

allauth's login field is named `login` (not `username`/`email`). Django's test Client
disables CSRF by default, so no token juggling. Note `Client.login()` raises
`AxesBackendRequestParameterRequired` - a real POST is fine because the view passes `request`.

## Always run the negative control

A green result is meaningless unless the check can go red. Inside a second rolled-back
atomic block, `EmailAddress.objects.filter(...).update(verified=False)` and repeat the
POST - it must land on `/accounts/confirm-email/` with no session. Wrap that block in
`override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")`:
**dev uses a real SMTP backend** (`config/settings_dev.py`), and an unverified login
attempt makes allauth send a confirmation email for real.

## Attributing "did I change anything?"

`Session` / `axes.AccessLog` counts are non-zero from the QA tester's own browser. Don't
report raw counts - compare timestamps and the decoded `_auth_user_id` against your
user's id to show the rows are someone else's and your test rolled back cleanly.
