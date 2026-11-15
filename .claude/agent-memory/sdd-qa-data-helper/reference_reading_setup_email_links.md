---
name: reading account-setup email links
description: Sent OutboundEmail rows are scrubbed (payload={}); read the body from Mailpit at localhost:8025 instead; how to mint a setup link without sending
type: reference
---
- `OutboundEmail` (freedom_ls/mail) scrubs `payload` the moment it is sent (`scrubbed_at == sent_at`), so a sent email's body is NOT in the DB. Only `status=queued` rows still hold it.
- Dev upstream is SMTP localhost:1025 = Mailpit. API: `curl localhost:8025/api/v1/search?query=to:EMAIL` then `/api/v1/message/<ID>` (fields `Text`, `HTML`).
- Links use `user.site.domain` (DemoDev = 127.0.0.1:8000); rewrite to the dev server port.
- Setup link = `reverse("account_reset_password_from_key", uidb36=user_pk_to_url_str(user), key=default_token_generator.make_token(user))` (allauth), same as `accounts/account_setup.py::_send`. Minting writes nothing. Check with `default_token_generator.check_token`. Valid PASSWORD_RESET_TIMEOUT (3 days) and until password/last_login changes.
- Learner pks given by callers are `Learner` UUIDs; User pk is an int.
