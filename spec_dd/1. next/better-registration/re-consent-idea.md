## Re-consent Flow When T&Cs Change

### Why this matters (compliance)

Under GDPR (Art. 7), consent is only valid for the specific version of terms a user agreed to. When terms change materially, prior consent does not automatically carry over — users must be asked to accept the new version.

Failing to re-collect consent after a material change means:
- The platform is operating without valid consent for users who signed up under old terms
- This is a GDPR violation (fines up to 4% of annual global revenue)
- Under POPIA (South Africa), fines up to ZAR 10 million

### What a re-consent flow looks like

When a new T&C version becomes active and a user has only accepted an older version:

1. **On next login/page load**: show a blocking banner or modal requiring acceptance of the new terms
2. **Grace period**: optionally allow continued use for a configurable period (e.g., 30 days) with a non-blocking reminder
3. **After grace period**: block access until new terms are accepted
4. **Email notification**: notify affected users that terms have changed

### Implementation considerations

- Middleware that checks the user's latest accepted T&C version against the active version for the current site
- The check should be lightweight (cached) since it runs on every request
- Admin should be able to set whether a new version requires immediate re-consent or allows a grace period
- The re-consent UI should show a summary of what changed, not just the full document
