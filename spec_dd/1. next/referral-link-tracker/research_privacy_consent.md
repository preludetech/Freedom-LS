# Research: Privacy, Consent & Data-Protection Implications of Referral-Link Tracking

**Feature under review:** capture `?ref=CODE` / UTM params on landing, track anonymous
browsing behaviour via cookie/session, link the trail to the `User` at signup, and retain
it for analysis.

**Scope of this note:** FLS is installed by many different operators in many jurisdictions.
This is not legal advice — it is a practical brief on what the *feature* must let an operator
configure so *they* can be compliant. Any operator running FLS for EU/UK/EEA users, or
serving users from those regions, should get their own legal sign-off on the final consent
copy and retention periods.

---

## 1. Is this "tracking" that needs prior cookie consent?

### 1.1 The legal trigger is not "cookies" as a technology, it's "storage/access on the user's device"

Under the EU ePrivacy Directive Art. 5(3) (implemented nationally, e.g. UK PECR reg. 6),
consent is required before you **store information on, or gain access to information
already stored on, a user's terminal equipment** — unless it is "strictly necessary" to
provide a service the user explicitly requested. This is technology-neutral: it applies to
cookies, localStorage, fingerprinting, tracking pixels, **and tracking links** — not just
classic cookies.

- EDPB Guidelines 2/2023 on the Technical Scope of Art. 5(3) ePrivacy Directive explicitly
  lists "tracking pixels and tracking links," "certain instances of IP tracking," and
  "device fingerprinting" as in-scope, extending the traditional "cookie law" reading well
  beyond browser cookies.
  https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf
- ICO guidance on cookies and similar technologies (PECR reg. 6) confirms the same
  functional test applies in the UK, and that this is being updated through 2026 following
  the Data (Use and Access) Act 2025.
  https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/cookies-and-similar-technologies/
  https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/

**Implication for this feature:** the referral/UTM capture itself is *reading the URL*, not
storage/access on the device — that part is not covered by Art. 5(3). But the moment FLS
sets a cookie or writes to `localStorage`/session storage to **persist** that referral code
across page views so it can be matched to a signup later, that write is a "storage/access"
operation and Art. 5(3) analysis kicks in.

### 1.2 Strictly-necessary vs analytics/marketing — where does referral tracking sit?

The "strictly necessary" exemption is assessed **from the user's point of view**, not the
site owner's: "would the user's requested service fail without this?" (ICO: "if you didn't
have analytics running the user could still access your service, which is why analytics
cookies aren't strictly necessary").
https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/

A cookie that stores "this session came from ref=CODE, tracked for attribution/analysis" is
**not** strictly necessary — the visitor can browse and sign up perfectly well without it.
It is functionally an analytics/marketing cookie (attribution tracking), so:

- **It requires prior, opt-in, informed consent** in the EU/UK/EEA if it is set via a cookie
  or similar device-storage mechanism, **unless** a narrow national exemption applies (see
  1.3), or unless the data is not tied to an identifiable person at all (see §2).
- Consent must be freely given, specific, informed, and as easy to refuse as to accept — no
  pre-ticked boxes, no "consent walls" that block basic site use for refusal alone.

### 1.3 Narrow exemptions worth designing for (but not relying on by default)

- **France (CNIL):** first-party audience-measurement cookies can be exempt from consent
  if strictly first-party, used only for aggregate statistics, not shared with third
  parties, and short-lived/retention-limited.
- **UK Data (Use and Access) Act 2025 / PECR amendment (in force 5 Feb 2026, ICO guidance
  29 Apr 2026):** introduces a "statistical purposes" exemption for low-risk analytics
  cookies under conditions (first-party, opt-out available, clearly disclosed, not used for
  anything beyond service improvement).
- **EU Digital Omnibus proposal (Nov 2025, not yet law):** would fold cookie rules into
  GDPR and add an EU-wide exemption for first-party, aggregated audience measurement.

These are jurisdiction- and condition-specific, actively moving targets, and none of them
license using the data for cross-session **identification** or **marketing** once a user
signs up (which this feature's design explicitly does — linking the trail to the `User`).
Because this feature's stated purpose is to attribute a *specific, later-identified person's*
journey (not just aggregate stats), it will not cleanly qualify for most of these
exemptions once the anonymous ID is joined to a `User` at signup. Treat the exemptions as
relevant only to a possible "aggregate campaign counter" sub-feature, not to the
per-visitor trail-linking feature as specified.

Sources:
https://www.cookieyes.com/blog/cookie-consent-exemption-for-strictly-necessary-cookies/
https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/

### 1.4 UTM parameters themselves are not the trigger — persistence is

UTM (`utm_source`, `utm_campaign`, etc.) and `?ref=CODE` query parameters arrive in the URL
regardless of consent — they are not stored on the device by the act of the browser
navigating to a URL. Reading them server-side, for the single request in which they arrive,
and using them (e.g., to render a "referred by" banner, or to log a one-off,
non-identifying event) does not itself require Art. 5(3) consent. **What requires consent
is persisting that value in a cookie/localStorage/session so it survives across requests
and can later be joined to the user.** This is the crux of the design distinction below.

---

## 2. When does this data become "personal data," and what governs it once it is?

### 2.1 IP addresses

- Recital 30 GDPR explicitly names IP addresses as an example of an "online identifier"
  that can make a natural person identifiable, hence personal data.
- ICO guidance and multiple regulator decisions treat IP addresses as personal data in the
  hands of any party (e.g., the site operator, or their host/ISP) that has a realistic means
  of linking the IP to a person — which the operator running FLS, controlling both the web
  logs and eventually the signup email, plainly does.
  https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/pseudonymisation/
- **Truncating or masking an IP (e.g., zeroing the last octet) is pseudonymisation, not
  anonymisation.** It reduces risk but does not take the data out of GDPR scope, because
  re-identification is still often possible with additional information the controller
  holds (e.g., session cookie + later account email).
  https://privacyinternational.org/explainer/5755/are-ip-addresses-personal-data

### 2.2 The anonymous trail becomes personal data the moment it's linkable to a person

- Before signup, a cookie ID + referral code + browsing trail is (at best) pseudonymous:
  it identifies "some particular browser/device" but not a named individual.
- Under GDPR Art. 4(1)/(5) and Recital 26, data remains "personal data" (just pseudonymised)
  as long as the controller (or anyone else) *could reasonably* re-associate it with a
  person — and this feature's entire purpose is to perform exactly that re-association at
  signup. So:
  - The anonymous trail should be treated as personal data (or at minimum, "likely to
    become personal data") **from first capture**, not just from the moment of joining.
  - Once joined to the `User` FK, it is unambiguously personal data and inherits all GDPR
    obligations that already apply to the rest of the `User` record (access, rectification,
    erasure, portability, etc.).

### 2.3 Lawful basis

Likely candidates, to be chosen deliberately (not defaulted) by the operator:

| Basis | Fit for this feature |
|---|---|
| **Consent** (Art. 6(1)(a)) | Required if relying on the ePrivacy Art. 5(3) cookie-consent gate anyway (which is likely — see §1). Cleanest, most defensible basis; ties GDPR lawful basis and ePrivacy consent together in one banner action. |
| **Legitimate interests** (Art. 6(1)(f)) | Sometimes argued for first-party, non-marketing analytics, but **only after passing the ePrivacy Art. 5(3) consent test** — legitimate interest under GDPR cannot override the separate ePrivacy consent requirement for the underlying cookie/storage. In practice: if a cookie is used, ePrivacy already forces you to consent-gate it, so GDPR legitimate-interest analysis becomes moot for the storage step (though it can still apply to subsequent *processing* of already-lawfully-collected data). |
| **Contract** (Art. 6(1)(b)) | Not a good fit — attribution/analytics is not necessary to perform the contract of providing course access. |

**Recommendation to bake into the feature:** default to **consent** as the lawful basis and
make the cookie/storage write itself contingent on that same consent (single mechanism,
not two separately-tracked "yes"es).

### 2.4 Data minimisation (Art. 5(1)(c)) and storage limitation (Art. 5(1)(e))

- Collect only what the stated purpose (attribution / campaign analysis) needs.
- Don't collect fields "because they might be useful later" — that is the opposite of
  minimisation and a common audit finding.
- Set a **defined, justified retention period** and delete/anonymise trail data once it is
  no longer needed for that purpose — not "forever," not "until manual cleanup."

---

## 3. Practical design guidance for FLS

### 3.1 What can be captured WITHOUT a consent banner

Safe, low-risk, generally defensible without a consent gate, provided it stays true to all
listed constraints:

- **Reading `?ref=` / UTM params from the current request only**, e.g. to render "you were
  referred by X" on the landing page in that single response, with **no persistence**
  beyond the request/response cycle.
- **Aggregate, non-identifying counters** — e.g. incrementing a per-campaign hit counter
  server-side with no per-visitor identifier retained at all (no cookie, no IP, no
  session key stored against the count). This is closer to genuine "statistics" and may
  fit emerging statistical-purpose exemptions, but only if truly aggregate and
  irreversible (you cannot reconstruct who generated which hit).
- **Strictly-necessary session cookies already required for basic site function** (e.g. the
  Django `sessionid` used for cart/auth) may incidentally carry the referral code *if*
  that specific use doesn't extend the cookie's necessity-justified purpose — but stacking
  a marketing-analysis purpose onto an already-necessary cookie does not make the new
  purpose exempt; consent still governs the *use for attribution*, not the underlying
  cookie's existence.

### 3.2 What triggers a consent requirement

- Any cookie, localStorage entry, or non-essential session key **set specifically to carry
  the referral/UTM code across requests** so it can later be joined to a signing-up user.
- Recording the visitor's **IP address** against that trail (IP is personal data — see
  §2.1) for anything beyond the immediate strictly-necessary request handling Django/hosting
  already does (e.g. security/abuse logs, which are typically justified under a different,
  narrower legitimate-interest basis with its own short retention, not the marketing basis).
- Any per-visitor identifier (device fingerprint, anonymous UUID, cookie ID) intended to be
  **joined to the `User`** at signup — this is the core mechanism of the feature and is
  precisely what both ePrivacy consent and GDPR lawful-basis rules are designed to gate.

### 3.3 How a consent gate should interact with the capture middleware

Recommended architecture (conceptual, for the design/spec phase — not an implementation
here):

1. **Consent-first ordering.** The referral-capture middleware must check consent state
   (e.g., a first-party "analytics/marketing cookies accepted" flag, itself set only after
   an affirmative banner action) **before** writing any persistent referral cookie/session
   key. If consent is absent/declined/not-yet-given: at most do the single-request,
   non-persisted read described in 3.1; do not write anything that survives the request.
2. **No pre-consent shadow tracking.** Don't capture-and-hold data "provisionally" hoping
   for later consent, and don't write the cookie and just hide the UI value — the ePrivacy
   violation is the write/storage itself, not the display.
3. **Consent withdrawal.** If a user later withdraws consent (or an anonymous visitor never
   converts and their consent cookie expires), the capture middleware should stop
   collecting/refresh the trail and any queued anonymous trail data for that visitor that
   hasn't yet been joined to a `User` should be eligible for deletion on its own retention
   schedule (see 3.4) — don't let it linger indefinitely "just in case."
4. **Joining at signup is itself a processing event requiring its own record.** Precisely
   because the codebase already has `LegalConsent` (append-only, `user` FK,
   `document_type`, `ip_address`, `timestamp`) and `SiteSignupPolicy` (per-site consent
   gate), the natural conceptual fit is: add a `document_type` (or an analogous consent
   record) for "referral/analytics tracking," captured at the same signup-time gate,
   so the moment the anonymous trail is joined to the new `User` there is an auditable
   record of the legal basis for having done so — mirroring the existing terms/privacy
   consent pattern rather than inventing a parallel mechanism. (This is a design
   suggestion for the eventual spec, not an implementation instruction here.)

### 3.4 Data-minimisation recommendations specific to this feature

**Do capture (if consented):**
- Referral code / UTM values themselves (short strings, not free text).
- A short-lived, purpose-specific anonymous session identifier.
- Coarse timestamps (day/hour granularity may be enough for campaign analysis — avoid
  precise-to-the-second logs if not needed).

**Do NOT store:**
- Full, unmasked IP address tied to the anonymous trail for analysis purposes. If IP is
  needed at all (e.g., fraud/abuse detection, geolocation for campaign reporting), truncate
  it (remove the last octet for IPv4 / last 80 bits for IPv6) and treat the truncated form
  as **pseudonymised, still-personal data** with its own retention limit — not as
  anonymised data exempt from GDPR.
- Full page-by-page browsing history beyond what the stated attribution purpose needs (e.g.,
  don't log every page view with referrer chains "in case it's useful" — log the
  landing/entry event and, if genuinely required, a small bounded set of subsequent
  milestone events).
- User-agent strings / device fingerprints beyond what's needed to de-duplicate hits, and
  never combine multiple weak identifiers (IP + UA + screen size, etc.) into a de facto
  fingerprint — that reintroduces identifiability you were trying to avoid by not storing
  IP directly.
- Any free-text or third-party-sourced enrichment (e.g., IP-to-company lookups) unless a
  separate, explicit lawful basis and consent covers it — this is a common feature-creep
  trap for "campaign attribution" tooling.

**Retention window:**
- Define a **short, explicit retention period for anonymous (pre-join) trail data** — e.g.
  30–90 days is a common industry range for attribution windows; align it to the operator's
  actual sales/signup cycle, not a default "forever."
- Anonymous trail data that is never joined to a `User` within that window should be
  deleted or irreversibly anonymised (e.g., rolled into an aggregate count) on a scheduled
  job — don't rely on manual cleanup.
- Once joined to a `User`, the *fact of having been referred by campaign X* can reasonably
  be kept for the life of the account (it's now ordinary account/analytics metadata, same
  retention class as other account data) but the **granular pre-signup browsing trail**
  (every page hit, timestamps, IP) should still be minimised/aggregated down soon after
  joining — keep the attribution conclusion, not the raw click-by-click trail, once its
  purpose (attributing the signup) is served.

### 3.5 Honouring deletion/erasure (GDPR Art. 17 "right to be forgotten")

- When a `User` is deleted (account deletion, GDPR erasure request, or site data-retention
  policy), any referral/campaign trail data linked via FK to that `User` must be deleted or
  irreversibly anonymised as part of the same cascade — it cannot be retained "because it's
  useful for aggregate reporting" once linked to an identified person, unless it has first
  been rolled up into a genuinely non-reidentifiable aggregate (e.g., "campaign X produced
  N signups this month," with N ≥ some small-number threshold to avoid singling out).
- If FLS's existing `User` deletion pathway already cascades `LegalConsent` and other
  FK-linked records, the referral-tracking model should follow the same pattern (FK with
  `on_delete=CASCADE` or an anonymising delete signal) rather than being a silent orphaned
  table full of personal data after account deletion — a common and easily-missed
  compliance gap in "add-on" tracking features bolted onto an existing user model.
- Anonymous (never-joined) trail records aren't subject to Art. 17 in the same way (no
  identified data subject to action the request for), but should still be governed by the
  retention window in §3.4 regardless.

---

## 4. Grounding in existing FLS infrastructure (for context only — not an audit)

- `freedom_ls/accounts/models.py`:
  - `LegalConsent` (append-only; `user` FK CASCADE, `document_type`,
    `document_version`, `git_hash`, `timestamp` auto_now_add, `ip_address`
    (`GenericIPAddressField`, nullable), `consent_method`) — already models exactly the
    "who consented to what, when, from where, how" shape that a referral-tracking consent
    record would need. Extending `DOCUMENT_TYPE_CHOICES` (or adding an analogous
    `consent_method`) is the natural, minimal-new-surface way to plug in referral-tracking
    consent, conceptually, without inventing a parallel consent model.
  - `SiteSignupPolicy` (per-site `allow_signups`, `require_name`,
    `require_terms_acceptance`, `additional_registration_forms`) — the existing per-site
    gate at signup time; a per-site "collect referral/analytics consent" toggle would sit
    naturally alongside `require_terms_acceptance` here, letting each FLS operator turn the
    feature on/off and configure its consent copy per site (multi-tenant, since FLS is
    site-aware).
- This confirms the codebase already has the right *shape* of infrastructure (per-site
  policy gate + append-only per-user consent ledger with IP+timestamp) to extend for
  referral-tracking consent, rather than needing new patterns.

---

## 5. Summary of practical requirements to carry into the feature spec

1. Persisting a referral/UTM code across requests (cookie/localStorage/session) for later
   joining to a `User` is an Art. 5(3)-ePrivacy-governed storage operation → gate it behind
   affirmative, specific, opt-in consent, not behind a "necessary cookies" umbrella.
2. Single-request, non-persisted reads of `?ref=`/UTM params, and genuinely aggregate,
   non-reidentifiable counters, can be done without a consent banner.
3. Treat IP addresses as personal data always; truncate/pseudonymise if stored at all, and
   never treat truncation as "anonymisation" for compliance purposes.
4. Choose consent as the GDPR lawful basis and tie it to the same UI action that satisfies
   the ePrivacy cookie-consent requirement — don't run two separate consent mechanisms.
5. Define and enforce a short retention window for anonymous pre-signup trail data;
   auto-delete/anonymise unjoined trail data on schedule.
6. Once joined to a `User`, cascade-delete or anonymise the trail data when the `User` is
   deleted, and prefer keeping only the attribution *conclusion* (which campaign), not the
   full granular browsing trail, long-term.
7. Make all of the above **per-site configurable** (consent copy, retention window,
   on/off), consistent with FLS's existing `SiteSignupPolicy` multi-tenant pattern, and
   record referral-tracking consent using the same append-only, IP+timestamped pattern as
   `LegalConsent` — this is an architectural recommendation for the spec/plan phase, not an
   implementation change made here.

---

## References

- EDPB, *Guidelines 2/2023 on the Technical Scope of Art. 5(3) of ePrivacy Directive* (Oct 2024):
  https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf
  https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-22023-technical-scope-art-53-eprivacy-directive_en
- ICO, *Guidance on cookies and similar technologies* / PECR reg. 6:
  https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/cookies-and-similar-technologies/
  https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/
- ICO, *Pseudonymisation guidance* (UK GDPR):
  https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/pseudonymisation/
- Privacy International, *Are IP addresses personal data?*:
  https://privacyinternational.org/explainer/5755/are-ip-addresses-personal-data
- GDPR.eu, *Cookies, the GDPR, and the ePrivacy Directive*:
  https://gdpr.eu/cookies/
- CookieYes, *Cookie consent exemption for strictly necessary cookies*:
  https://www.cookieyes.com/blog/cookie-consent-exemption-for-strictly-necessary-cookies/
- Google for Developers, *Set up consent mode on websites (Consent Mode v2)*:
  https://developers.google.com/tag-platform/security/guides/consent
- GDPR full text, Recital 26 (pseudonymisation) and Recital 30 (online identifiers incl. IP
  addresses), Art. 4 (definitions), Art. 5 (principles incl. minimisation/storage
  limitation), Art. 6 (lawful bases), Art. 17 (right to erasure):
  https://gdpr-info.eu/
- UK Data (Use and Access) Act 2025 / PECR statistical-purposes exemption context
  (commenced 5 Feb 2026, ICO guidance 29 Apr 2026) and EU Digital Omnibus proposal
  (Nov 2025) — background commentary:
  https://www.cookieyes.com/blog/uk-cookie-guidance-ico-pecr/
  https://measuredcollective.com/ico-updates-cookie-consent-rules-under-the-data-use-and-access-act-what-organisations-need-to-do-now/

Codebase grounding (read, not audited): `freedom_ls/accounts/models.py` — `LegalConsent`
(lines ~189-219), `SiteSignupPolicy` (lines ~165-186).

---

status: ok
