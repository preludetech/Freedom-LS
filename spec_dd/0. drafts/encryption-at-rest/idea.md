# Encryption at Rest for Sensitive Database Fields

Encrypt sensitive data stored in the database so that a database breach does not directly expose plaintext PII and secrets.

**Status re-checked 2026-08-24.** Part of this has already shipped, on the back of the webhooks work rather than this draft. Webhook secrets are encrypted and Postgres SSL is wired up. API keys, learner free-text answers, and key rotation are untouched. The sections below say which is which.

## Already done

- **Webhook secrets are encrypted.** `WebhookSecret.encrypted_value` is an `EncryptedTextField` (`freedom_ls/webhooks/models.py:421`, migration `webhooks/0006_webhooksecret.py`). Note this is a separate `WebhookSecret` model, not the `WebhookEndpoint.secret` field this draft originally named.
- **The library choice is settled.** `django-fernet-encrypted-fields` is the dependency, and `encrypted_fields` is in `INSTALLED_APPS` (`config/settings_base.py:126`). Not `django-encrypted-model-fields`, and not `Signer`. Anything encrypted from here on should use the same library.
- **Key material is configured.** Fernet keys are derived from `SECRET_KEY` plus `SALT_KEY` by PBKDF2 (`config/settings_base.py:437-453`). Production requires `WEBHOOK_ENCRYPTION_SALT` and fails at settings-import time if it is missing (`freedom_ls/deployment/settings_defaults.py:74`, wired at `config/settings_prod.py:56`). Development falls back to a hardcoded deterministic salt.
- **Postgres SSL is wired.** `database_ssl_options` (`freedom_ls/deployment/settings_defaults.py:90`) sets `DATABASES["default"]["OPTIONS"]` in production (`config/settings_prod.py:71-73`).

## Still to do

- **API keys are plaintext.** `Client.api_key` is a plain `CharField` (`freedom_ls/app_authentication/models.py:15`), a 64-char secret granting full API access. This draft called it the highest-impact item and it is still the highest-impact item.
- **Learner free-text answers are plaintext.** `QuestionAnswer.text_answer` (`freedom_ls/learner_progress/models.py:493`).
- **User emails and names are plaintext.** PII subject to GDPR and POPIA.
- **No key rotation path.** `django-fernet-encrypted-fields` supports MultiFernet rotation through `SECRET_KEY_FALLBACKS`, which is noted in a comment at `config/settings_base.py:442-445` but has never been exercised. There is no re-encryption management command, and no test that rotating actually works.
- **SSL is not enforced.** `DB_SSLMODE` defaults to `prefer`, which silently falls back to an unencrypted connection. Whether this is acceptable depends on the deployment: a managed Postgres that refuses plaintext connections closes the gap at the infrastructure layer, a self-hosted one does not. Decide whether FLS should default to `require` or leave it to the deployer and say so in the deployment docs.
- **The naming is now misleading.** `WEBHOOK_ENCRYPTION_SALT` and `SALT_KEY` are global to every encrypted field in the project. Once a second model uses `EncryptedTextField`, the webhook-specific name is wrong. Renaming means an env var change for every existing deployment, so decide early whether to carry the name or break it.

If an attacker gains read access to the database (SQL injection, backup theft, compromised credentials), everything in the "still to do" list is immediately usable.

ISO 27001 A.8.24 (Use of Cryptography) requires encryption of sensitive data at rest. GDPR Article 32 and POPIA Section 19 both list encryption as an appropriate technical measure.

## When to do this

**Before production with real user data.** This is not urgent during development but must be in place before FLS handles real student data. Prioritise after:
1. Security audit hardening is complete
2. Privacy compliance features are built (data export/deletion need to work with encrypted fields)

API keys go first: one field, one model, no query patterns to break. Learner PII follows.

## In scope

### Application-level field encryption
- Encrypt `Client.api_key` using `EncryptedTextField`, matching the webhook-secret pattern
- Encrypt learner free-text answers and user PII, in that order
- Transparent encryption and decryption so existing code doesn't need major changes
- Work out what breaks first: `api_key` is `unique=True` and looked up by value, and an encrypted column can do neither. Authentication probably has to move to a lookup hash alongside the encrypted value, which is a change to `app_authentication`, not only to the model field.

### Key rotation support
- Ability to re-encrypt fields when the key is rotated, through `SECRET_KEY_FALLBACKS`
- Management command for key rotation
- A test that proves data encrypted under an old key still decrypts after rotation

### Database connection encryption
- Decide on `require` versus `prefer` as the FLS default, and document it

## Out of scope
- Full-disk encryption (infrastructure concern, not application)
- Encrypting non-sensitive fields (over-engineering)
- Homomorphic encryption or searchable encryption (unnecessary complexity)
