# Sentry PII scrubbing (`before_send`)

FLS handles **learner PII**. When Sentry is enabled with `SENTRY_SEND_DEFAULT_PII=True`, every
event carries user email/username and full request bodies — including anything a learner typed
into a form. The `support-concrete-project-deployment-external-requirements-config` spec decided
to **store PII for now** to keep debugging signal high, and deferred the scrubbing work to this
spec.

This spec adds a `before_send` (and `before_send_transaction`) hook to the Sentry SDK
initialisation so PII is scrubbed/redacted before events leave the app, letting deployers keep
Sentry on without shipping raw learner data to a third party.

## Context

- The Sentry integration and the `SENTRY_SEND_DEFAULT_PII` env var are introduced by the parent
  external-requirements-config spec — see
  `spec_dd/2. in progress/support-concrete-project-deployment-external-requirements-config/idea.md`
  and its `research_sentry_django_integration.md`.
- Related, broader compliance work lives in `spec_dd/0. drafts/01. privacy-compliance/` — this
  spec is narrower: only the Sentry egress path.

## In scope

- A `before_send` hook wired into the Sentry SDK init that scrubs PII from outgoing events:
  - user email / username / IP (or reduce to a stable non-PII user id)
  - request bodies / form data (learner free-text, answers)
  - query strings and headers that can carry tokens or PII
- A `before_send_transaction` hook applying the same scrubbing to performance/trace payloads.
- A configurable denylist/allowlist of field names to scrub, with safe defaults, owned by the
  `deployment` app's settings (align with the `app-settings` skill / `config.py` pattern).
- Tests proving representative PII (email, request body, form field) is redacted before send.
- Decide the interaction with `SENTRY_SEND_DEFAULT_PII`: scrubbing should hold whether the var is
  on or off, so a misconfiguration can't leak raw PII.

## Out of scope

- The rest of the privacy-compliance feature set (data export, deletion, consent) — that is
  `01. privacy-compliance`.
- PostHog / analytics PII handling.
- Webhook PII control (`FLS_PRIVACY.WEBHOOK_INCLUDE_PII`) — owned by `01. privacy-compliance`.

## Open decisions

- Redact-in-place vs drop-the-field vs hash-with-salt for user identifiers.
- Whether scrubbing rules are hard-coded defaults, fully config-driven, or both.
- Whether to reduce `SENTRY_SEND_DEFAULT_PII` back to off-by-default once scrubbing is trusted.
