## Re-examine User Data Retention

### Why this matters

The `better-registration` work introduces a `LegalConsent` model whose rows are erased via `on_delete=CASCADE` when a user is deleted. That choice was made deliberately — for now we want consent records to follow the rest of a user's data — but it sidesteps a real question we have not yet answered as a project: **how long do we keep user data, and which records (if any) should outlive a user deletion as evidence or business-record artefacts?**

This idea collects the questions that need answering and is the placeholder for a future spec.

### Questions to answer

- Which categories of user data exist today? (profile, progress, consent, audit/log, payment, instructor evaluations, IP-bearing records, …)
- For each category:
  - What's the legal/regulatory minimum retention period? (GDPR, POPIA, tax law, dispute-resolution windows.)
  - What's the legal/regulatory *maximum* retention period after a deletion request? (GDPR Art. 17 right-to-erasure with carve-outs for legal claims.)
  - Should the record be:
    - hard-deleted with the user (current default; CASCADE), or
    - anonymised in place (PII fields wiped, foreign keys preserved), or
    - preserved with a snapshot of the user identity at the time the record was created (e.g. legal consent rows referencing a `user_email` snapshot rather than a live FK)?
- How does deletion interact with cohorts, certificates, and educator/admin records that may have legal weight?
- Do we need a separate "deletion request" workflow vs. immediate hard delete? (E.g. cooling-off period, admin approval, batched anonymisation jobs.)
- Backups: how long are they kept and does a deletion request need to propagate into backups, or is the standard "deleted within rotation period" assertion sufficient?

### Likely scope of the resulting spec

- Per-model retention policy (table or matrix) with the chosen `on_delete` / anonymisation strategy.
- A canonical `delete_user(user)` flow that does the right thing per model rather than relying on cascade defaults scattered across migrations.
- Admin UI / management command for handling erasure requests.
- Documentation surface (privacy policy, internal runbook) describing what survives a deletion and why.

### Out of scope for this idea

- Implementation. This file exists to mark the question for a future spec, not to design it.
- Re-consent on T&C change — covered separately in `re-consent-idea.md`.

### Provenance

Surfaced during the plan-security review of `better-registration` on 2026-04-27 when choosing `on_delete` for `LegalConsent.user`. CASCADE was kept for that feature so erasure remains consistent with the rest of the user's data, but the broader retention policy should be decided in its own spec.
