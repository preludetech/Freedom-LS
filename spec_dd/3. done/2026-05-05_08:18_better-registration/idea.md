## Better Registration

We need to improve the signup flow. Currently we only collect email and password (with an email confirmation field).

### What needs to change

1. **Ask for name at signup**: First name required, last name optional. This is needed for certificates, educator-facing student lists, and personalised communication. Currently names are only collected optionally via profile edit after signup.

2. **T&C acceptance**: Users must accept Terms and Conditions via an unchecked checkbox (clickwrap) before signing up. This is the most legally defensible approach under GDPR and POPIA. Acceptance must be recorded with timestamp, T&C version, and IP address.

3. **Separate Privacy Policy consent**: GDPR requires T&C acceptance and privacy policy consent to be separate checkboxes — they cannot be bundled. Both need independent audit trails.

4. **Drop the email confirmation field (`email2`)**: This adds friction without real benefit — users copy-paste, and FLS already has mandatory email verification which catches typos anyway.

### Configurability

Different concrete websites will have different requirements. This should be configurable per site.

- Extend the existing `SiteSignupPolicy` model with registration config fields (e.g., `require_name`, `require_terms_acceptance`) rather than creating a separate model
- The signup form should dynamically include/exclude fields based on the site's configuration
- Use allauth's `ACCOUNT_FORMS` hook with a custom form that reads site config at init time

### T&C versioning

- T&C content lives in the git repo (not in the database)
- Each T&C document has a human-readable version (e.g. in frontmatter) for ordering and business logic (e.g. "has user accepted v2 or later?")
- Record both the explicit version and the git hash of the file at time of acceptance — the hash serves as cryptographic proof of exactly what the user saw
- T&C content should be site-aware (different sites can have different terms)
- Store: user, T&C version, git hash, timestamp, IP address, consent method

### Additional user information fields

Some sites will need to collect more detailed user information beyond name — e.g., ID number, phone number, etc. These should be configurable per site.

- Not everything should be shown on the initial signup page. The first page collects the essentials (email, password, name, T&Cs).
- Once a user has verified their email, they are presented with a form to fill in the remaining required fields before they can proceed.
- Consider using a list of form instances on the `SiteSignupPolicy` to define which additional fields are required per site.

### Out of scope (future work)

- Re-consent flow when T&Cs are updated (see `spec_dd/1. next/better-registration/re-consent-idea.md`)
- Social login / passwordless auth
