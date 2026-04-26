# Encryption at Rest for Sensitive Database Fields

Encrypt sensitive data stored in the database so that a database breach does not directly expose plaintext PII and secrets.

## Why this matters

Currently, the following sensitive data is stored in plaintext in the database:
- **API keys** (`app_authentication.Client.api_key`) - 64-char secrets that grant full API access
- **Webhook secrets** (`WebhookEndpoint.secret`) - used to sign webhook payloads
- **Student form answers** (`QuestionAnswer.text_answer`) - free-text responses that may contain personal information
- **User emails and names** - PII subject to GDPR/POPIA

If an attacker gains read access to the database (SQL injection, backup theft, compromised credentials), all of this data is immediately usable.

ISO 27001 A.8.24 (Use of Cryptography) requires encryption of sensitive data at rest. GDPR Article 32 and POPIA Section 19 both list encryption as an appropriate technical measure.

## When to do this

**Before production with real user data.** This is not urgent during development but must be in place before FLS handles real student data. Prioritise after:
1. Security audit hardening is complete
2. Privacy compliance features are built (data export/deletion need to work with encrypted fields)

API keys and webhook secrets should be encrypted first (highest impact if leaked). Student PII encryption can follow.

## In scope

### Application-level field encryption
- Encrypt API keys and webhook secrets at the application layer
- Use `django-encrypted-model-fields` or Django's built-in `Signer` with a dedicated encryption key
- Transparent encryption/decryption so existing code doesn't need major changes
- Key management: encryption key from environment variable, separate from `SECRET_KEY`

### Key rotation support
- Ability to re-encrypt fields when the encryption key is rotated
- Management command for key rotation

### Database connection encryption
- Enforce SSL for PostgreSQL connections (`OPTIONS: {'sslmode': 'require'}`)

## Out of scope
- Full-disk encryption (infrastructure concern, not application)
- Encrypting non-sensitive fields (over-engineering)
- Homomorphic encryption or searchable encryption (unnecessary complexity)
