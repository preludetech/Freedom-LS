Research: Does FLS need a cookie consent banner before loading GA4, for a South-Africa-only deployment?

_I am not a lawyer. Where sources disagree or a point turns on facts specific to a deployment (which
audience, which regulator posture at the time), that is flagged explicitly rather than smoothed over._

## Bottom line

**No banner is required to add GA4 for a South-Africa-only deployment, if it is configured
conservatively.** POPIA does not have a GDPR/ePrivacy-style rule that makes *consent* the only lawful
basis for a non-essential cookie — it instead offers six lawful grounds in section 11, and legitimate
interest is a normal, litigatable-but-viable basis for first-party, non-marketing analytics. Google
does not require Consent Mode or the EU User Consent Policy outside the EEA/UK/Switzerland. So this
matches the user's framing: do not spec a banner now.

What *should* accompany turning GA4 on, none of which is a banner:
1. Update the (currently placeholder, currently silent-on-analytics) privacy policy to disclose GA4
   and what it collects — see [Gap found](#gap-found-in-fls-today) below.
2. Configure GA4 conservatively: leave Google Signals off (it is opt-in, not on by default), turn off
   ads personalisation, and set data retention to the shorter 2-month option rather than 14 months.
   IP address handling needs no separate action — GA4 discards the identifiable portion of the IP
   before storage unconditionally; there is no "anonymize IP" toggle to set because there is nothing
   else to configure.
3. If FLS is ever installed for a deployment that also serves EU/UK/Swiss visitors, that deployment
   needs a consent gate — see [§3](#3-if-a-downstream-deployment-serves-euukswiss-learners). A cheap,
   worthwhile hook is discussed there so a future banner spec doesn't need an unrelated refactor first.

This mirrors FLS's existing, unresolved position on the PostHog snippet and the referral-tracking
cookie, both of which already run with no consent gate — see [Existing FLS analytics posture](#existing-fls-analytics-posture-posthog-and-referral-tracking).

---

## 1. POPIA and ECTA

### Is a cookie / online identifier "personal information" under POPIA?

Yes, in principle. Section 1 of POPIA defines personal information to expressly include "any
identifying number, symbol, e-mail address, physical address, telephone number, location
information, **online identifier** or other particular assignment to the person." A GA4 client ID
(the value in the `_ga` cookie) or an IP address, to the extent either can be linked to an
identifiable natural person, falls inside that definition. POPIA does not, however, mention
"cookies" anywhere in its text — this is an inference from the online-identifier wording, not an
express statutory rule about cookies. [Mondaq/Lexology — unique identifiers under POPIA](https://www.mondaq.com/southafrica/data-protection/1813672/id-like-to-know-unique-identifiers-under-popia), [popia.co.za section 1 commentary](https://popia.co.za/).

### Is consent required, or is there a lawful-basis alternative?

This is the load-bearing difference from the GDPR/ePrivacy world, and it is worth being precise
about. POPIA section 11 sets out **six** independent lawful grounds for processing personal
information — consent is only one of them, alongside (among others) necessity for a contract,
compliance with a legal obligation, and **the legitimate interests of the responsible party or a
third party**. POPIA does not rank these grounds; consent is not the default or the "safe" one, and
several commentators specifically caution against treating it as such, because consent is
withdrawable at will while legitimate interest is not. [Section 11 — POPIA](https://popia.co.za/section-11-consent-justification-and-objection/), [Werksmans Attorneys — moving beyond the consent myth](https://werksmans.com/privacy-day-2026-moving-beyond-the-consent-myth-under-popia/), [MJ Kotze Inc — the six lawful grounds](https://mjkinc.co.za/popia/lawful-grounds).

Crucially, unlike the EU, **South Africa has no ePrivacy-style instrument that specifically overrides
this general framework for cookies and mandates consent regardless of lawful basis.** The GDPR's
strict "consent needed for any non-essential cookie" rule does not come from the GDPR itself — it
comes from the ePrivacy Directive / member-state implementations (e.g. the UK's PECR), which apply
*in addition to* GDPR specifically to the act of storing/reading information on a device. POPIA has
no equivalent companion law. So the analysis for a South African site is a straight section-11
lawful-basis analysis on the personal information itself, not a separate "is this cookie strictly
necessary" gate.

Michalsons — a South African law firm that specialises in this area and is one of the few
non-vendor sources with a considered legal opinion on the point — states directly that a
responsible party generally **does not need prior authorisation to use cookies for the purpose they
were set for** (e.g. first-party analytics to understand how a site is used), and that consent is
specifically required mainly where cookies are used for **direct marketing to someone who is not
already a customer**. Their view is that ordinary analytics fits within the "legitimate interest"
ground, not that it requires opt-in consent. [Michalsons — cookie law in South Africa](https://www.michalsons.com/blog/cookie-law-south-africa/15264).

**Caveat on sourcing.** Most other results returned by search on this topic (CookieYes, CookieHub,
Complianz, Termly, CookieFirst, Usercentrics, TermsFeed, and similar) are consent-management-platform
vendors with a direct commercial interest in readers concluding that a paid banner product is
legally required. Several of these assert, with GDPR-derived specifics (a "reject all" button, 12-
month consent expiry, granular purpose toggles) that have no textual basis anywhere in POPIA — POPIA
sets none of these mechanics. Treat that whole category of source as marketing, not legal opinion,
and weight Michalsons and the direct statutory/regulator sources far more heavily.

### What has the Information Regulator said, specifically about cookies?

Nothing specific has been found. The Information Regulator's most relevant recent published guidance
is on **direct marketing** (December 2024), not cookies or online analytics generally. No dedicated
cookie guidance note, code of conduct, or enforcement action naming Google Analytics or web analytics
cookies was found in this research. [Global Policy Watch — Information Regulator direct-marketing guidance, Dec 2024](https://www.globalpolicywatch.com/2024/12/long-awaited-popia-guidance-on-direct-marketing-published-by-south-africas-information-regulator/). The absence of guidance is itself informative for a
decision-oriented answer: there is no known enforcement pattern targeting SA-only sites that run
first-party analytics without a banner. This is not the same as certainty that the Regulator would
never take that view in future — POPIA is a comparatively young statute (fully in force since July
2021) and its cookie-specific posture, if any, has not yet crystallised.

### ECTA (Electronic Communications and Transactions Act 25 of 2002)

ECTA is South Africa's general e-commerce/electronic-transactions statute — consumer protection in
electronic transactions, e-signatures, ISP liability, cybercrime provisions predating the Cybercrimes
Act. It has no cookie-specific or analytics-specific provisions. Where personal information is
collected via a website, ECTA's own data-protection principles (largely superseded in practice by
POPIA once POPIA commenced) and POPIA operate together, but ECTA adds nothing beyond POPIA for this
question. [Michalsons — guide to the ECT Act](https://www.michalsons.com/blog/guide-to-the-ect-act/81), [CMS — data protection and cybersecurity laws in South Africa](https://cms.law/en/int/expert-guides/cms-expert-guide-to-data-protection-and-cyber-security-laws/south-africa).

### Legal requirement vs. best practice — the actual line

- **Legal requirement (POPIA):** disclose the processing (what is collected, why, by whom, third
  parties involved) — this is a section 18/notification obligation independent of the lawful-basis
  question, and applies regardless of which of the six grounds is relied on. A privacy policy that
  says nothing about GA4 while GA4 runs is the actual POPIA gap here, not the absence of a banner.
- **Best practice, not a POPIA requirement:** an "accept/reject" banner mechanism, granular
  category toggles, a "manage preferences" panel. These are GDPR/ePrivacy conventions that vendors
  have generalised into "cookie compliance" products; POPIA's text does not require this mechanism
  for a first-party analytics cookie relied on under legitimate interest.
- **Right to object stays live either way.** Even on a legitimate-interest basis, POPIA gives a data
  subject the right to object to processing on reasonable grounds relating to their situation
  (echoing GDPR Art. 21). A functioning opt-out mechanism (see §5) satisfies this without needing a
  pre-load consent gate.

---

## 2. Google's own requirements

### EU User Consent Policy

Google's EU User Consent Policy applies only to end users physically located in the **EEA, the UK,
or Switzerland**, regardless of where the business operating the site is based. It does not apply to
a South African visitor, and it does not apply to a site that has no EEA/UK/Swiss visitors at all.
[Google — EU user consent policy](https://www.google.com/about/company/user-consent-policy/), [CookieYes — how to comply with Google's EU user consent policy](https://www.cookieyes.com/blog/eu-user-consent-policy/).

### Consent Mode v2

Consent Mode (v1 and v2) exists to let Google Analytics/Ads adjust what they measure based on a
visitor's consent status, and Google has stated a requirement for it specifically for traffic from
the EEA, UK, and (for certified-CMP/TCF purposes) Switzerland, since March 2024. There is **no
requirement, from Google, to implement Consent Mode for a site whose traffic is South African.**
Skipping Consent Mode entirely for an SA-only deployment carries no Google-side compliance risk
(only the ordinary risk of reduced measurement accuracy if EEA/UK traffic does show up unexpectedly
and Consent Mode isn't there to model it). [UniConsent — Google Consent Mode for EEA, UK, Switzerland](https://www.uniconsent.com/consent-mode-eea-uk-switzerland), [Google Ads Help — verify consent signals for EEA users](https://support.google.com/google-ads/answer/16142339?hl=en-GB).

### Google Analytics Terms of Service

Separately from the EU policy, GA's general Terms of Service require operators to have a privacy
policy that discloses use of cookies/identifiers and provides a way to opt out — this applies
globally, not only in the EEA/UK. This is a **disclosure** obligation, satisfied by the privacy
policy update recommended in §5, not a consent-banner obligation.

---

## 3. If a downstream deployment serves EU/UK/Swiss learners

FLS is installed into other Django projects (per `docs/product/deployment.md` and
`docs/product/configuration-and-extension.md`), so a specific downstream operator's deployment — not
FLS itself — decides who its learners are. If a downstream project markets to or accepts learners
from the EEA, UK, or Switzerland, **that project needs a consent gate before GA4 (and before
PostHog, and before the existing referral-tracking cookie) fires for those visitors**, independent of
this South-Africa-only decision. FLS's own `docs/product/signup-attribution.md` already flags this
same gap for the referral-tracking cookie and ships no consent gate for it today — this GA4 decision
should not create a second, differently-shaped instance of the same open problem.

**Recommendation: build the smallest sensible extension point now, not a banner.** Concretely, that
means whatever config surface is added for GA4 (a settings-driven "is analytics enabled" flag akin to
`POSTHOG_API_KEY`, per the prior PostHog config research) should render the tracking snippet from a
single, named template block or a single context-processor boolean (e.g.
`analytics_consent_granted`) that a downstream project can override — rather than hard-coding the
snippet to always render whenever the API key is set. That costs very little now (a conditional
already has to exist to gate on "is a key configured" at all) and means a later "add a real consent
banner" spec, when and if a deployment needs one, is a template/context-processor change instead of a
refactor of how the snippet is loaded. This mirrors the existing PostHog snippet's shape, so it isn't
a new pattern to learn.

Do **not** build an actual banner UI, cookie-category taxonomy, or preference-storage mechanism
now — that is explicitly out of scope per the user's instruction and would be speculative work with
no deployment currently needing it.

---

## 4. What comparable South African sites/LMSs do in practice (brief)

Search results (dominated by consent-vendor content, so treated cautiously — see the caveat in §1)
converge on one candid observation from a non-vendor angle: **most South African websites that
implement any cookie notice at all use a minimal "this site uses cookies, click OK" banner with no
real accept/reject choice**, which — if POPIA *did* require GDPR-style consent — would itself be
non-compliant (not "informed", not "specific"). In other words, current SA market practice for
sites that do show a banner is not a reliable signal of what is legally required; it looks more like
imported GDPR convention applied inconsistently. No specific comparable Django-based LMS's actual
GA4/consent implementation was found and verifiable in this research pass; this point is therefore
weaker than the statutory analysis above and should be weighted accordingly. [CookieYes commentary on typical SA banner practice](https://www.cookieyes.com/popia-compliance/).

---

## 5. Recommendation and minimum accompanying configuration

**Banner needed now, for SA-only operation: No.** Do not spec a consent banner as part of this GA4
setup. This matches the user's stated framing and is supported by: POPIA's non-consent-exclusive
lawful-basis structure (§1), Michalsons' direct legal view that ordinary analytics fits legitimate
interest without prior authorisation (§1), the absence of Information-Regulator guidance targeting
cookies specifically (§1), and Google's own geographic scoping of its consent requirements to
EEA/UK/Switzerland (§2).

**What should accompany turning GA4 on, as part of *this* piece of work (not deferred):**

1. **Update the privacy policy to name GA4.** `legal_docs/_default/privacy.md` is currently a
   placeholder that discloses account/consent data but says nothing about analytics tooling of any
   kind — it is silent on the PostHog snippet that already runs today, too. Per POPIA's disclosure
   obligation (§1) and GA's own Terms of Service (§2), section 1 ("Information we collect") should
   name Google Analytics 4 (and PostHog, while there), what it collects (page views, device/browser
   info, an anonymised/pseudonymous client identifier), and that it is used for site-usage
   measurement — plus a route to object/opt out (§1's "right to object" point). This is a
   documentation change to a legal template, not a banner.
2. **Configure GA4 conservatively, as part of setup, regardless of the no-banner decision:**
   - Leave **Google Signals off** — it is opt-in in the GA4 admin, not on by default, so this is
     "don't turn it on" rather than an active step. Leaving it off also avoids Google using
     signed-in Google-account data for personalised-advertising-style reporting, which is the part
     of GA4 with the most privacy sensitivity. [Google — activate Google Signals](https://support.google.com/analytics/answer/9445345?hl=en).
   - **Disable ads personalisation** for the property (a separate toggle from Signals) — there is no
     product reason for FLS, an LMS, to feed remarketing/ads-personalisation audiences. [Google — advanced settings for ads personalization](https://support.google.com/analytics/answer/9626162?hl=en).
   - **Set data retention to 2 months** (the shorter of GA4's two options) rather than the 14-month
     default GA4 offers, since nothing in FLS's product needs long-lived per-user GA4 event
     retention beyond aggregate reporting. [Analytics Mania / Google — GA4 data retention settings](https://support.google.com/analytics/answer/7667196).
   - **IP anonymisation needs no configuration.** Unlike Universal Analytics, GA4 has no
     `anonymizeIp` flag because it never stores an identifiable IP address in the first place — the
     identifiable portion is discarded before storage, unconditionally, in every region. There is
     nothing to turn on. [Graphed — does GA4 anonymize IP addresses by default](https://www.graphed.com/blog/does-google-analytics-4-anonymize-ip-addresses-by-default).
3. **Give visitors a way to object/opt out**, satisfying POPIA's right-to-object even on a
   legitimate-interest basis — a documented "Google's opt-out browser add-on" link or an
   equivalent lightweight opt-out mechanism in the privacy policy is enough; this does not require a
   pre-load banner.
4. **Add the extension seam described in §3** so a future EU/UK-serving downstream deployment's
   consent-banner spec is additive, not a rework.

**Not recommended to build now:** an accept/reject banner UI, a cookie-category taxonomy, consent
storage/versioning for cookie choices (as distinct from the existing `LegalConsent` T&C/privacy
model), or Consent Mode v2 wiring. None of these are required for SA-only operation, and building
them now would be speculative work against no live requirement — flag them explicitly as deferred,
not silently dropped, in case a later spec needs a starting point.

---

## Existing FLS analytics posture (PostHog and referral tracking)

For context, this decision is not being made in a vacuum: FLS already ships two other pieces of
client-side tracking with no consent gate, both flagged as known gaps in FLS's own documentation
rather than resolved:

- **PostHog** (`freedom_ls/base/context_processors.py::posthog_config`) loads the PostHog JS snippet
  client-side whenever `POSTHOG_API_KEY` is configured, with no consent check anywhere in the render
  path. See `spec_dd/3. done/2026-07-11_16:01_support-concrete-project-deployment-external-requirements-config/research_posthog_django_integration.md` for the config-surface research (silent on
  consent entirely — it was out of scope there).
- **Referral-tracking cookie** (`docs/product/signup-attribution.md`) sets a signed, host-only
  cookie on any tracked-link landing regardless of consent, and additionally records **Google
  Analytics and Meta cookie values already present in the visitor's browser** into a permanent
  database row at signup. FLS's own docs candidly flag this as needing a real privacy assessment
  before running in the EU/UK and state plainly: "FLS ships no consent gate for the tracking
  cookie."

Neither of these is in scope to fix here — but it means the GA4 decision made in this document
should be read as "matching FLS's existing, already-shipped posture for SA-only operation," not as
introducing a new pattern. If a future banner spec is written (for an EU/UK-serving deployment, per
§3), it will need to cover all three (GA4, PostHog, referral-tracking cookie) together, since they
are functionally the same category of problem.

## Gap found in FLS today

`legal_docs/_default/privacy.md` (the shipped, still-placeholder privacy policy) discloses account
and consent data collection but contains **no mention of analytics, cookies, PostHog, Google
Analytics, or the referral-tracking cookie at all** — see §1 "Information we collect" and §5
"Sharing" in that file. This is the actual, existing gap against POPIA's disclosure obligation,
present before GA4 is even added. Recommendation 1 above addresses it, but note it is a pre-existing
gap this research surfaced rather than one this piece of work introduces.

## Learner age / minors

No mention of a minimum learner age, minor status, parental consent, or COPPA-equivalent handling was
found anywhere under `docs/product/` (searched for "minor", "child", "under 18", "parental consent",
"13 years", "age of", "COPPA" — the only matches were unrelated uses of "parent/child" describing
organisation hierarchy, and "child" in an example course-type name). FLS's registration flow
(`claude_plugins/fls-dev/skills/registration/SKILL.md`) has no age-gate concept. This means: (a) there
is no existing product signal that FLS deployments specifically target or restrict minors, so no
additional minors-specific consent analysis (e.g. POPIA's competent-person/parental-consent rules for
processing a child's personal information) was triggered by anything found in the codebase; (b) if a
specific downstream deployment *does* serve minors, that deployment's operator would need to consider
POPIA's stricter rules for processing children's personal information as a separate, deployment-level
question — this is flagged as an open question for whoever configures a specific deployment, not
something this research resolves either way.

---

## References

- [Michalsons — Cookie law in South Africa: guidance and actions](https://www.michalsons.com/blog/cookie-law-south-africa/15264)
- [Michalsons — Guide to the ECT Act in South Africa](https://www.michalsons.com/blog/guide-to-the-ect-act/81)
- [POPIA (popia.co.za) — Section 11: Consent, justification and objection](https://popia.co.za/section-11-consent-justification-and-objection/)
- [Werksmans Attorneys — Privacy Day 2026: Moving beyond the consent myth under POPIA](https://werksmans.com/privacy-day-2026-moving-beyond-the-consent-myth-under-popia/)
- [MJ Kotze Inc — The six lawful grounds: the heart of POPIA](https://mjkinc.co.za/popia/lawful-grounds)
- [Mondaq / Lexology — ID like to know: Unique identifiers under POPIA](https://www.mondaq.com/southafrica/data-protection/1813672/id-like-to-know-unique-identifiers-under-popia)
- [Global Policy Watch — Long-awaited POPIA guidance on direct marketing published by the Information Regulator (Dec 2024)](https://www.globalpolicywatch.com/2024/12/long-awaited-popia-guidance-on-direct-marketing-published-by-south-africas-information-regulator/)
- [CMS — Data protection and cybersecurity laws in South Africa](https://cms.law/en/int/expert-guides/cms-expert-guide-to-data-protection-and-cyber-security-laws/south-africa)
- [Google — EU user consent policy](https://www.google.com/about/company/user-consent-policy/)
- [CookieYes — How to comply with Google's EU User Consent Policy](https://www.cookieyes.com/blog/eu-user-consent-policy/)
- [UniConsent — Google Consent Mode for EEA, UK, and Switzerland](https://www.uniconsent.com/consent-mode-eea-uk-switzerland)
- [Google Ads Help — Verify your consent signals for EEA users](https://support.google.com/google-ads/answer/16142339?hl=en-GB)
- [Google Analytics Help — Activate Google Signals](https://support.google.com/analytics/answer/9445345?hl=en)
- [Google Analytics Help — Advanced settings to allow for ads personalization](https://support.google.com/analytics/answer/9626162?hl=en)
- [Google Analytics Help — Data retention settings](https://support.google.com/analytics/answer/7667196)
- [Graphed — Does Google Analytics 4 anonymize IP addresses by default?](https://www.graphed.com/blog/does-google-analytics-4-anonymize-ip-addresses-by-default)
- [CookieYes — POPIA compliance guide (used only for the "typical SA banner practice" observation in §4, weighted as low-confidence vendor commentary)](https://www.cookieyes.com/popia-compliance/)
- In-repo: `legal_docs/_default/privacy.md`, `legal_docs/README.md`, `docs/product/security-and-data-handling.md`, `docs/product/signup-attribution.md`, `claude_plugins/fls-dev/skills/registration/SKILL.md`, `spec_dd/3. done/2026-07-11_16:01_support-concrete-project-deployment-external-requirements-config/research_posthog_django_integration.md`

status: ok
