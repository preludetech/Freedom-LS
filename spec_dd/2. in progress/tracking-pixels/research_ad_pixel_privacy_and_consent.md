# Research: privacy and consent implications of adding Meta and TikTok ad pixels to FLS

_I am not a lawyer. This builds on, and does not repeat, the two prior GA4/Ads research files:
`spec_dd/3. done/2026-09-23_11:31_google-analytics-setup/research_consent_south_africa.md` (POPIA
lawful-basis framework, no-banner conclusion for SA-only GA4) and
`research_user_id_and_pii.md` (identifier choice, PII rules). Read those first. Where this file
repeats a POPIA-101 point from that research it is only to mark exactly where the *ad-pixel* case
diverges from the *GA4* case — the divergence is the point of this file, not the repetition._

## Bottom line, stated up front

**Ad pixels are not "GA4 with a different vendor name."** The prior research's no-banner conclusion
rested on three legs specific to GA4-as-configured: (1) POPIA offers legitimate interest as a lawful
basis alongside consent, (2) Google acts, in that configuration (Signals off, ads personalisation
off), as a processor serving *FLS's own* analytics purpose, not as an independent party repurposing
the data, and (3) Google scopes its own consent-mode requirement to the EEA/UK/Switzerland, letting a
permanently-"denied" signal for that traffic satisfy Google's policy without a banner. Meta and
TikTok pixels break leg (2) outright — both platforms' own terms say plainly that pixel/CAPI/Events-API
data is used for *their* purposes (ad delivery, audience-building, measurement, product improvement
across every site that fires their pixel), which under POPIA and GDPR alike makes each of them an
independent responsible party/controller for what it does with the data, not merely FLS's
sub-processor. That is the load-bearing difference this document works through — see [§1](#1-popia-does-remarketing-count-as-direct-marketing)
through [§6](#6-practical-recommendation-options-not-a-decision).

This file lays out **options**, per the brief, rather than a recommendation — see [§6](#6-practical-recommendation-options-not-a-decision).

---

## 1. POPIA: does remarketing count as "direct marketing"?

### The narrow textual answer: probably not, under section 69 specifically

Section 69 is POPIA's only dedicated direct-marketing provision, and its own text is channel-specific:

> "The processing of personal information of a data subject for the purpose of direct marketing by
> means of any form of electronic communication, including automatic calling machines, facsimile
> machines, SMSs or e-mail is prohibited unless..." [Section 69 — POPIA](https://popia.co.za/section-69-direct-marketing-by-means-of-unsolicited-electronic-communications/)

That list — calls, faxes, SMS, email — is about the responsible party (FLS/the deployment) itself
*sending an unsolicited communication* to the data subject. A Meta or TikTok remarketing ad shown to
someone while they browse Instagram or TikTok is not FLS sending them anything; it is FLS handing a
browsing/behaviour signal to a third party who decides, on its own platform, whether and what ad to
show. Several vendor sources (see the sourcing caveat below) assert that section 69 "covers"
cookies/pixels/fingerprinting generically — that assertion does not survive reading the section's own
text, which is scoped to the automatic-calling-machine/fax/SMS/email list, not to online advertising
generally. **This is the same category of vendor overreach the prior GA4 research flagged** (GDPR-derived
specifics asserted onto POPIA's text without a textual basis) and should be weighted the same way here.

### The broader, more defensible answer: it is still "processing," and sharing with an independent third party for its own purposes is the sensitive part

Section 69 not applying does not mean POPIA has nothing to say. Two things do apply, and they are the
actual crux:

1. **Section 11's ordinary lawful-basis analysis applies to the disclosure itself**, exactly as it did
   for GA4. The question is whether *sharing browsing/event data with Meta/TikTok for their own ad
   purposes* is defensible under legitimate interest, given that — unlike the GA4 configuration —
   the third party is not a captive processor acting only for FLS's stated purpose.
2. **Michalsons' own practical line** (already the most-weighted non-vendor SA source in the sibling
   research) is that consent is specifically needed where cookies are used **"for direct marketing to
   someone who is not already a customer"** [Michalsons — cookie law in South Africa](https://www.michalsons.com/blog/cookie-law-south-africa/15264).
   That is a practitioner's practical distinction, not a quote from section 69's text, but it maps
   almost exactly onto what a Meta/TikTok remarketing pixel does on FLS's public/marketing pages: it
   is squarely aimed at converting a visitor who is *not yet a customer* into one, via a third-party ad
   platform. Michalsons' own dividing line — not the narrower statutory text of section 69 — is the
   more relevant signal for "is consent actually expected here," and it points toward consent being the
   safer basis for ad-platform remarketing specifically, even though it points the other way for
   first-party analytics.

**Net effect:** legitimate interest is a *weaker* and more contestable basis for ad-network remarketing
than it was for GA4-as-configured, precisely because the third party's own use of the data is outside
FLS's control and outside FLS's stated purpose. This is not the same as saying legitimate interest is
unavailable — POPIA does not prohibit relying on it here — but the balancing test (data subject's
reasonable expectations, proportionality, availability of a less invasive means) tips further against
it than it did for analytics, because "your browsing data will help a third party build an ad profile
of you across sites you didn't visit and haven't heard of" is a materially bigger surprise to a data
subject than "this site counts its own visits."

### The Information Regulator's direct-marketing guidance (Dec 2024) — does it help either way?

The Regulator's December 2024 guidance note, per the sibling research, is about unsolicited electronic
communications (the section 69 channels), not online ad-network targeting
[Global Policy Watch — Information Regulator direct-marketing guidance, Dec 2024](https://www.globalpolicywatch.com/2024/12/long-awaited-popia-guidance-on-direct-marketing-published-by-south-africas-information-regulator/).
No dedicated Information Regulator guidance on ad-network pixels, remarketing, or cross-site ad
profiling was found in this research pass, and no enforcement action against a South African site for
running Meta/TikTok pixels was found either. As with GA4, **the absence of Regulator guidance here is
informative but not dispositive** — POPIA's specific posture on ad-tech has not crystallised, and
this document's silence-is-not-permission caveat from the sibling research applies with at least equal
force here, arguably more, given the third-party-repurposing point above.

**Sourcing caveat (repeated deliberately, because it applies even more here than for GA4):** the
consent-management-platform vendor ecosystem (CookieChimp, EcomSolve, PopiaReady, ASi Technologies,
FitConsent, and similar, surfaced repeatedly in this research) has a direct commercial interest in
readers concluding a paid banner product is legally required, and several asserted specifics (e.g.
"section 69 covers pixels," specific consent-expiry periods, mandatory granular toggles) that do not
appear in POPIA's own text. Michalsons, the Information Regulator's own guidance, and the statutory
text itself are weighted far above this category of source throughout this document.

---

## 2. Cross-border transfer — POPIA section 72

Both prior research files flagged this as out of scope; it is squarely in scope for ad pixels because,
unlike GA4 (where Google's infrastructure and data-handling terms were already accepted for the GA4
decision), Meta and TikTok are *additional* US/China-linked recipients of FLS visitor data, each
requiring its own section 72 analysis.

Section 72 permits a cross-border transfer of personal information on one of several independent
grounds: (a) the recipient is subject to a law, binding corporate rules, or an agreement that provides
protection "substantially similar" to POPIA's Chapter 3 conditions; (b) the data subject consents to
the transfer; (c) the transfer is necessary for performance of a contract between the data subject and
the responsible party, or for a contract concluded in the data subject's interest; or a few narrower
alternatives [Section 72 — POPIA](https://popia.co.za/section-72-transfers-of-personal-information-outside-republic/), [Michalsons — transfers of personal information outside South Africa](https://www.michalsons.com/focus-areas/privacy-and-data-protection/transfers-of-personal-information-outside-south-africa).

Practically, for a Meta/TikTok pixel:

- **No adequacy finding exists** for the US (where Meta's ad infrastructure principally sits) or China
  (where TikTok/ByteDance has jurisdictional ties) under POPIA — the Information Regulator has not
  published an adequacy list naming either. This mirrors the EU's own position pre-Privacy-Shield-successor
  arrangements, though POPIA has no equivalent "Data Privacy Framework" mechanism of its own.
- **The "agreement that provides adequate protection" ground** is the realistic one used in practice —
  Meta's and TikTok's own advertiser/business terms (see §4 below) function as exactly this kind of
  agreement in the eyes of practitioners who write POPIA-specific "cross-border data transfer
  agreements" as a service line [MJ Kotze Inc — cross-border data transfer agreement](https://mjkinc.co.za/agreements/cross-border-data-transfer-agreement), but this is asserted by
  practitioners selling that exact service, not confirmed by a Regulator ruling that Meta's or TikTok's
  standard terms in fact meet the "substantially similar" bar — this is an open, untested question, not
  a settled one.
- **Consent from the data subject** (section 72(1)(b)) is the other realistic ground, and is the one
  that does not depend on an unresolved "are Meta's/TikTok's standard terms good enough" question.
  This is a second, independent reason (beyond the direct-marketing point in §1) why consent is the
  more defensible-in-practice basis for ad pixels specifically, even where it was not needed for GA4.
- No source found in this research specifically confirms or rules out whether GA4 (already accepted in
  the sibling decision) and Meta/TikTok pixels should be analysed differently under section 72 — in
  principle they should be analysed identically (same section, same test), the difference is only that
  the GA4 decision didn't examine section 72 explicitly and this document is the first to raise it for
  *any* of FLS's US-bound analytics/ad vendors. This is flagged as a gap in the GA4 decision too, not
  one this document resolves for GA4 retroactively.

---

## 3. Minors — POPIA sections 34–35, and why it matters more here than for GA4

### What sections 34–35 say

> "A responsible party may, subject to section 35, not process personal information concerning a
> child." [Section 34 — POPIA](https://popia.co.za/section-34-prohibition-on-processing-personal-information-of-children/)

Section 35 then lists the exceptions: prior consent of a "competent person" (parent/guardian),
necessity for establishing/exercising a legal right, compliance with international public law
obligations, historical/statistical/research purposes with safeguards, or information the child has
deliberately made public with a competent person's consent
[Section 35 — POPIA](https://popia.co.za/section-35-general-authorisation-concerning-personal-information-of-children/).
POPIA defines a "child" as a natural person under 18 (unlike GDPR's member-state-variable 13–16, and
unlike Meta's own 13-year US-COPPA-influenced line and TikTok's separate under-13 regime — three
different age thresholds are in play depending on which rule you're checking, and this document does
not reconcile them into one number because none of the underlying rules use the same one).

### Why this is a new question for ad pixels specifically, not a repeat of the GA4 gap

The sibling GA4 research found **no existing FLS product signal that deployments specifically target
or restrict minors** and treated minors as an open, deployment-level question, explicitly not resolved
either way. That framing was reasonable for GA4, where the practical exposure was low: Google's terms
don't single out children's data for a blanket ban, and GA4-as-configured sends no PII regardless of
the visitor's age.

**Ad pixels change the calculus even before FLS resolves the "does a deployment serve minors"
question, because Meta's and TikTok's own terms impose an outright prohibition, not a POPIA-style
lawful-basis test:**

- **Meta's Business Tools Terms** prohibit advertisers from sharing Business Tool Data that is "from
  or about children under the age of 13," full stop — not "with consent," not "if disclosed," simply
  prohibited [Meta — Business Tools Terms](https://www.facebook.com/legal/technology_terms).
- **TikTok's Business Products (Data) Terms** go further: they prohibit sharing "any Business Products
  Data that they know — or should reasonably know — belongs or relates to minors" (not just under-13),
  applying "regardless of whether the data has been collected intentionally or unintentionally,"
  covering data shared through the Pixel, Events API, or uploaded contact lists, and TikTok's Ads
  Manager/Events Manager actively flags detected violations
  [TikTok Ads Help — potentially prohibited data sharing](https://ads.tiktok.com/help/article/about-notifications-of-potentially-prohibited-data-sharing-on-tiktok), [Usercentrics — TikTok privacy policy data-sharing terms](https://usercentrics.com/guides/privacy-policies-of-major-platforms/tiktok-privacy-policy/).

This is a **contractual and platform-enforcement risk that exists independently of POPIA**, and it is
specific to FLS's actual product shape: FLS is an education platform with no age-gate (per the sibling
research), used by downstream deployments whose learner population is unknown to FLS itself and could
plausibly include under-18s (school-linked cohorts, bridging/access programmes, vocational training
aimed at school-leavers, etc. are all plausible LMS use cases, though none is confirmed in the
codebase). Firing `sign_up`, `course_registered`, `course_completed`, or a lead-form event with any
learner-linked identifier to Meta or TikKok for a cohort that includes minors is arguably exactly the
kind of data both platforms' own terms forbid sharing — independent of whether South African POPIA
minors' rules are separately satisfied. **This risk sits with whichever deployment turns pixels on**,
same ownership model as the sibling research's minors conclusion, but the trigger condition (any
event that could relate to a minor learner, not just PII) is broader for ad pixels than it was for
GA4, because GA4's exposure there was "don't send PII," while Meta's/TikTok's exposure is "don't send
data about a minor at all," PII or not.

---

## 4. Meta's and TikTok's own contractual requirements on the advertiser (FLS/the deployment)

Both platforms' terms put explicit obligations on whoever fires the pixel — this is not a "what would
be nice" list, it is what each platform's Business Tools/Business Products terms actually require:

**Meta Business Tools Terms** [source](https://www.facebook.com/legal/technology_terms):
- The advertiser must represent it has "a lawful basis (in compliance with all applicable laws,
  regulations and industry guidelines)" for sharing data with Meta.
- The advertiser must provide "a clear and prominent notice on each web page where our pixels are
  used" disclosing third-party data collection and linking to an opt-out.
- For jurisdictions "requiring informed consent for storing and accessing cookies or other information
  on an end user's device (such as the European Union)," the advertiser must "ensure, in a verifiable
  manner, that an end user provides all necessary consents before you use Meta Business Tools to
  enable storage of and access to Meta cookies or other information on the end user's device."
- Forbidden data categories include information "from or about children under the age of 13,"
  improperly hashed contact information, government/financial identifiers, and "health information,
  financial information, consumer report information or other categories of sensitive information."

**TikTok Business Products (Data) Terms** [sources](https://usercentrics.com/guides/privacy-policies-of-major-platforms/tiktok-privacy-policy/), [TikTok Ads Help](https://ads.tiktok.com/help/article/about-notifications-of-potentially-prohibited-data-sharing-on-tiktok):
- Deploying the TikTok Pixel/Events API for ad optimisation makes the advertiser and TikTok **joint
  controllers**, not controller-and-vendor, under TikTok's own framing — a materially different
  disclosure obligation than a plain processor relationship.
- Advertiser must disclose in its privacy policy that it uses third-party tracking technologies
  including TikTok, and describe what data is collected and for what (measurement, ad targeting).
- Prohibits sharing minors' data and "sensitive personal data" as covered in §3 above.

**What this means for FLS specifically, independent of the POPIA analysis above:** both platforms
contractually require (not just "recommend") a **privacy-policy disclosure naming the platform**
(FLS's current placeholder `legal_docs/_default/privacy.md`, per the sibling research, discloses
nothing about analytics/ad tooling at all today — this gap would need closing regardless of the
consent-mechanism decision), and Meta specifically requires **verifiable consent before enabling
cookie storage in EU-like jurisdictions** — this is Meta's own contractual term, not just a
GDPR/ePrivacy inference, so a deployment cannot rely on "POPIA doesn't require it" reasoning to skip
this for EEA/UK/Swiss visitors even in theory; Meta's own advertiser agreement independently requires
it. TikTok's help documentation is less explicit about a contractual consent-verification obligation
but converges on the same practical requirement via GDPR/UK-GDPR compliance (TikTok is itself subject
to those laws as a data recipient in the EU/UK).

---

## 5. Server-side (Conversions API / Events API) with hashed data — does this change the POPIA/GDPR picture?

Both platforms offer a server-side alternative to the browser pixel: Meta's Conversions API (CAPI) and
TikTok's Events API, typically sending a hashed email/phone alongside the event for better match
quality. The user's framing implicitly asks whether this is a *lower-consent* path. It is not:

- **Hashing is pseudonymisation, not anonymisation**, under both GDPR and (by the same logic, since
  POPIA's "de-identify"/"anonymise" concepts in section 1 require that the information "can not be
  re-identified again") POPIA. A hashed email remains personal information because it is
  re-identifiable by anyone (including Meta/TikTok themselves, and anyone else with the same hash
  function and a guessable/known input, e.g. a purchased email list) who can recompute the same hash
  from a plaintext email and match it — this is the identical point the sibling `research_user_id_and_pii.md`
  made about why hashing an email doesn't make it acceptable to send to GA4 either.
- **CAPI/Events-API still requires the same lawful basis as the browser pixel** — moving the call
  server-side changes *where* the request originates, not *what* is being processed or *who* receives
  it. A German court ruling in 2026 is reported to have held that CAPI events must not fire at all
  without prior consent, "not even with limited data" — treated here as one national court's ruling
  under GDPR, illustrative of the direction regulators are leaning, not binding on South Africa and
  not independently verified against a primary court record in this research pass, so weighted as a
  signal, not settled law [FlexyConsent — Meta Pixel and CAPI consent guide](https://flexyconsent.com/blog/meta-pixel-facebook-conversions-api-consent-guide/).
- **What CAPI *does* change**, relevant to FLS's own PII discipline (per the sibling research's
  "nothing hashed, nothing new" GA4 recommendation): CAPI's entire value proposition is sending a
  hashed identifier (email/phone) for match quality, which is a different posture from FLS's current
  GA4 setup, which the sibling research specifically recommended *against* doing (don't hash email as
  a workaround, use a non-PII pk instead). If FLS/deployments use CAPI/Events API with hashed
  email/phone, that is a new category of data leaving FLS's systems that the GA4 decision deliberately
  avoided — worth naming explicitly as a departure from the existing precedent, not an extension of it.
- **CAPI without hashed contact data** (e.g. sending only the same non-PII event + `external_id` as
  pk, mirroring the GA4 `user_id` approach) is possible and would keep the same PII posture as GA4 —
  but sacrifices most of CAPI's match-quality benefit over the browser pixel, which exists specifically
  to compensate for lost browser-side signal (ITP/ETP cookie blocking, ad blockers) by using
  higher-confidence identifiers.

**Net:** server-side does not relax the consent question and, if it follows each platform's own
documented best-quality setup (hashed email/phone), *raises* FLS's PII exposure relative to today's
GA4 posture rather than lowering it.

---

## 6. GDPR/EEA visitors — does GA4's "no banner" trick transfer?

The current GA4/Ads setup (per `docs/how tos/google-analytics-and-ads.md`) denies Google's Consent
Mode by default for EEA/UK/Swiss visitors and ships no banner at all — a permanently-denied signal
satisfies Google's EU User Consent Policy because Google explicitly allows "denied, forever, for this
traffic" as a valid consent state (with Google's own Advanced Consent Mode statistically modelling
aggregate conversions from that denied traffic without needing real consent collection).

**Meta and TikTok expose an equivalent-looking mechanism, but it does not have the same modelling
escape hatch, and their own terms are more prescriptive about *how* the denial has to be reached:**

- **Meta's consent API**: `fbq('consent', 'revoke')` disables advertising tracking, sets no new
  cookies, and permits only "aggregated, non-advertising" data; `fbq('consent', 'grant')` activates the
  pixel fully [Meta for Developers — Meta Pixel GDPR implementation](https://developers.facebook.com/documentation/meta-pixel/implementation/gdpr).
- **TikTok's consent API**: `ttq.holdConsent()` queues events without setting cookies until
  `ttq.grantConsent()`/`ttq.revokeConsent()` is called; `holdConsent` is the initial recommended state
  when TikTok's own Cookie Consent Mode is enabled in Events Manager
  [TikTok for Business — Pixel Cookie Consent Mode docs](https://business-api.tiktok.com/portal/docs/pixel-cookie-consent-mode/v1.3).
- **The mechanical pattern used for GA4 — geo-detect EEA/UK/Swiss, call the "denied"/"revoke"/"hold"
  variant, and never call "grant" because there is no banner to trigger it — is technically
  reproducible for both Meta and TikTok.** A permanently-held/revoked pixel for that traffic segment
  sets no cookies and sends (per Meta's own description) only aggregated non-advertising data, which
  is a defensible "we never collect for this traffic" posture, structurally identical to the GA4
  approach.
- **The difference is what that buys you.** Google's Advanced Consent Mode still derives *modelled*
  conversion estimates from denied EEA/UK traffic using aggregated signals and machine learning, so a
  permanently-denied GA4/Ads visitor still contributes *something* to reported conversions. Meta's
  documented "revoke" behaviour is described as permitting "only aggregated, non-advertising data" —
  there is no equivalent, vendor-documented statistical modelling feature for Meta or TikTok found in
  this research that reconstructs ad-attributable conversions from permanently-denied traffic the way
  Google's does. **Practical consequence: a permanently-denied Meta/TikTok pixel for EEA/UK/Swiss
  visitors is closer to "no pixel at all for that traffic" than GA4's denied state is to "no GA4 at
  all" for the same traffic** — which is a reasonable, low-risk choice, but it should be understood as
  giving up essentially all EEA/UK ad-attribution value for that segment, not a partial concession the
  way the GA4 precedent was.
- **Meta's own Business Tools Terms (§4) independently require "verifiable" consent before *enabling
  storage* in EU-like jurisdictions** — a permanently-held "revoke" state trivially satisfies this
  (storage is never enabled), so the "never call grant" pattern is contractually sufficient for Meta's
  own terms, not just practically convenient.

So: **yes, the GA4 no-banner trick transfers mechanically to Meta and TikTok**, but its value is much
smaller for ad platforms than it was for GA4, because there is no modelling fallback — permanently
denying is closer to "don't bother running Meta/TikTok ads to EEA/UK/Swiss visitors at all" in
practice. This matters concretely if FLS/a deployment ever targets ad campaigns *at* EEA/UK audiences
(unlikely for a South-Africa-focused product, but the same "if a downstream deployment serves EU/UK
learners" caveat from the sibling research applies here too, and campaign-targeting decisions sit with
the ads platform, separate from where visitors organically come from).

---

## 7. Does it matter which pages carry the pixel? What privacy-minded practitioners recommend

Yes, and there is a fairly consistent practitioner recommendation, found across multiple non-vendor and
vendor-adjacent-but-converging sources on this specific point (treated cautiously per the sourcing
caveat, but the underlying reasoning — not just the assertion — is sound and independently checkable):

- **Public marketing/landing pages** (course-catalogue pages, application-gated course marketing pages,
  the existing `content_group = landing_page` pages per `docs/how tos/google-analytics-and-ads.md`) are
  the intended, lowest-risk surface for ad pixels — this is literally what remarketing/conversion pixels
  are for, and a visitor on a public page has not yet disclosed anything account-linked.
- **Authenticated, in-course learner pages** (topic pages, activity/quiz pages, progress dashboards) are
  the highest-risk surface and the one most commonly called out for *removing* third-party ad pixels
  entirely — not because course content is health data (FLS is not healthcare), but because of the
  general principle that a signed-in area is where the platform's own identifiers (session, user_id-shaped
  page URLs, in-app referrers) are most likely to leak incidentally into a third party's request
  alongside the pixel fire, and because a learner deep in a course has the least plausible expectation
  that Meta/TikTok are watching (a materially different reasonable-expectation position than a visitor
  on a public ad landing page who arrived, plausibly, *from* a Meta/TikTok ad). The HIPAA-context
  articles surfaced in this research state this principle in a healthcare frame specifically
  ("authenticated traffic" vs "non-authenticated traffic" as the dividing line for what pixel-fires
  are defensible), but the underlying reasoning — least-surprising-use, minimise what a third party
  incidentally sees on the most sensitive pages — transfers directly to an education platform's
  in-course pages even without a HIPAA-equivalent SA statute in play
  [Lokker — managing Meta Pixel data exposure](https://lokker.com/blog/meta-pixel-privacy), [Accountable — Meta Pixel in healthcare](https://www.accountablehq.com/post/meta-pixel-in-healthcare-hipaa-compliance-privacy-risks-and-safer-alternatives).
- **The specific FLS events in scope for pixels** (per the task brief: sign-up, course registration,
  application submitted, lead form, course completion) are mostly **transition events that fire once**,
  not a "pixel loaded on every in-course page" pattern — this matters because it means the practical
  choice is narrower than "pixel everywhere vs pixel nowhere." `course_completed` is the one event in
  this list that fires from deep inside the authenticated, in-course experience (a learner finishing
  their last topic), which is exactly the surface practitioners flag as higher-risk — worth naming as
  the one event in the requested list that doesn't sit on a public marketing page by construction,
  unlike `sign_up` (post-registration-page), `course_registered`/`course_access_requested` (registration
  flow, arguably still "not yet a customer" in Michalsons' framing), and `generate_lead` (a marketing
  form by definition).

---

## 8. Common UX complaints about cookie banners, and what each option costs in conversion data

Relevant because a banner is one of the options in §6, and the trade-off is not just "legal risk" —
it is also "does the banner defeat the purpose of adding these pixels at all."

- Users see roughly 1,000+ cookie banners a year (~3/day); about a quarter click "Accept" without
  reading, and banner design materially skews the outcome: when a one-click "Reject all" sits on the
  first layer, roughly 60% of users reject; when rejecting takes more than one click, roughly 90%
  accept — i.e. banner *design*, not user preference, drives most of the observed variance
  [Ignite — 29 studies on cookie banners, consent rates and compliance](https://www.ignite.video/en/articles/basics/cookie-consent-studies).
- Multiple sources converge on **up to 70% of conversions/tracking data points being lost the moment a
  real (non-dark-patterned) reject option exists and is used** — reported ranges across sources are
  roughly 30–70% of visitors declining where a genuine choice is offered, which directly erodes the
  point of installing conversion pixels in the first place: attribution, remarketing audience size, and
  campaign optimisation data all shrink by whatever fraction declines
  [Litlyx — cookie banners and conversion loss](https://litlyx.com/blog/cookie-banner-loss), [Milkmoon Studio — the cookie consent dilemma](https://www.milkmoonstudio.com/post/the-cookie-consent-dilemma-what-happens-when-97-of-your-data-vanishes).
- Separately, **compliance quality of banners is itself poor in the wild**: one cited study found
  57.5% of sites keep advertising/analytics cookies active after a user revokes consent, and 74.2%
  fail to correctly propagate a revocation to at least one third party — i.e. a badly-implemented
  banner is not just a UX cost, it can create the exact enforcement exposure a banner was meant to
  avoid, by advertising a choice it doesn't actually honour
  [Ignite — 29 studies on cookie banners](https://www.ignite.video/en/articles/basics/cookie-consent-studies).
- **What this means for the options in §6/§9**: a banner scoped only to ad pixels (not GA4) would, if
  honest and functional, cost a large fraction of exactly the conversion data the pixels exist to
  capture — which is a real trade-off to weigh against the legal-risk reduction, not a reason to avoid
  a banner outright, but a reason not to assume "add pixels + add banner" nets out to a straightforward
  win for the ads use case.

---

## 9. Practical recommendation options — laid out, not decided

Per the brief, this section lists options and their trade-offs without choosing one.

**Option A — No banner, mirror the GA4 pattern exactly.** Fire Meta/TikTok pixels unconditionally for
non-EEA/UK/CH traffic (South Africa has no cookie-consent-specific statute per §1), and set
`fbq('consent','revoke')`/`ttq.holdConsent()` permanently (never call grant) for geo-detected
EEA/UK/CH traffic, same as the existing `denied` Consent Mode pattern.
- *For:* zero new engineering pattern to learn (same geo-gate FLS already has for GA4 Consent Mode);
  satisfies Meta's own contractual consent-verification requirement for EEA-like jurisdictions
  trivially (storage never enabled); no banner UX cost anywhere.
- *Against:* per §1–§2, legitimate interest is a weaker basis for ad-network sharing than it was for
  GA4 specifically because Meta/TikTok repurpose the data for their own ends — this option accepts more
  POPIA/section-72 legal risk than the GA4 decision did, without a consent fallback to point to if
  challenged. Zero EEA/UK/CH ad-attribution value (§6), though that traffic is presumably minor for an
  SA-focused deployment.

**Option B — Consent required for ad pixels specifically, everywhere (including South Africa), GA4
untouched.** Add a lightweight consent gate (not necessarily a full CMP) that only ad pixels are wired
to, leaving GA4 exactly as configured today, no banner for GA4.
- *For:* directly answers the §1 concern (ad-network sharing is the more consent-shaped case, per
  Michalsons' "direct marketing to non-customers" line and the third-party-repurposing point) and the
  §2 concern (consent is an independent, unambiguous section 72 transfer ground, unlike relying on
  "Meta's terms are probably adequate"); matches both platforms' own EEA-scoped contractual consent
  requirement and extends the same protection to SA visitors without needing to argue POPIA requires
  it, closing the gap proactively rather than waiting for Regulator guidance to catch up (per §1's
  "not yet crystallised" point).
- *Against:* introduces exactly the UX/data-loss cost quantified in §8 for the *entire* SA user base,
  for a legal protection that (per §1) may not be strictly required for SA-only traffic — the banner
  cost is paid immediately and continuously; the legal benefit is a hedge against an unresolved,
  currently-quiet regulatory question. Also the first consent-UI FLS would ship (PostHog and the
  referral cookie run with none today, per the sibling research), so it sets a visible precedent a
  future spec would need to reconcile with those.

**Option C — Geo-scoped banner: consent gate only for EEA/UK/CH traffic (or "not South Africa"
traffic), no gate for South African visitors.** Combine A's SA posture with a real (not
permanently-denied) consent flow for EEA/UK/CH visitors specifically.
- *For:* closest to "do the minimum required, where required" — matches the GA4 decision's SA-vs-EU
  split exactly, and gives EEA/UK/CH visitors actual ad-attribution value if they opt in (unlike Option
  A's permanent denial, which forgoes that value entirely). Directly satisfies Meta's contractual
  consent-verification term with an actual mechanism rather than a permanent no.
- *Against:* is the most engineering work of the four options (geo-detection reliability, a real
  accept/reject UI scoped conditionally, wiring both platforms' consent APIs to it); for a
  South-Africa-focused product, this effort is spent protecting a traffic segment that may be
  vanishingly small; risks being the "differently-shaped instance of the same open problem" the sibling
  research warned against if built ad-hoc for ad pixels alone rather than as part of a proper future
  consent-banner spec covering GA4/PostHog/referral-cookie/ad-pixels together.

**Option D — Pixels only on public/unauthenticated marketing pages; no pixel-bearing events fired from
inside the authenticated learner experience.** Per §7, restrict pixel fires to `sign_up` (fired from
the post-signup page, not mid-registration-flow), `course_access_requested`/`course_registered`
(registration flow pages), and `generate_lead` (a marketing form) — and *exclude* `course_completed`
specifically, since it is the one requested event that fires from deep inside the authenticated,
in-course experience.
- *For:* directly implements the practitioner recommendation in §7 with no consent-mechanism cost at
  all; meaningfully reduces exposure to the minors concern in §3 (a learner has to have gone further
  into the authenticated product, arguably signalling less about who they are, for the excluded event,
  though this is a partial mitigation, not a resolution, since `sign_up`/`course_registered` still
  happen post-authentication and still relate to a specific account).
- *Against:* gives up the `course_completed` conversion signal entirely, which the existing GA4/Ads
  setup already treats as a secondary (not primary) conversion goal for exactly the "lags the ad click
  by weeks" reason (per `docs/how tos/google-analytics-and-ads.md` §3) — so the cost of dropping it
  from ad-pixel scope specifically may be low relative to its GA4/Ads role. Does not, by itself, resolve
  §1's or §2's legal-basis questions for the events that *do* remain in scope — this option is
  orthogonal to, and combinable with, A/B/C rather than a substitute for choosing among them.

**These options are combinable, not mutually exclusive** — e.g. Option A (SA posture) + Option C's
EEA/UK/CH consent gate + Option D's page restriction is a coherent combined position, as is Option B
applied SA-wide but with Option D's page restriction layered on top to reduce the population asked to
see a banner in the first place (fewer pages carrying pixels could mean fewer sessions triggering a
consent prompt if the banner itself is also gated to only appear where a pixel could fire).

---

## References

- [Section 69 — POPIA: Direct marketing by means of unsolicited electronic communications](https://popia.co.za/section-69-direct-marketing-by-means-of-unsolicited-electronic-communications/)
- [Section 34 — POPIA: Prohibition on processing personal information of children](https://popia.co.za/section-34-prohibition-on-processing-personal-information-of-children/)
- [Section 35 — POPIA: General authorisation concerning personal information of children](https://popia.co.za/section-35-general-authorisation-concerning-personal-information-of-children/)
- [Section 72 — POPIA: Transfers of personal information outside Republic](https://popia.co.za/section-72-transfers-of-personal-information-outside-republic/)
- [Michalsons — Cookie law in South Africa: guidance and actions](https://www.michalsons.com/blog/cookie-law-south-africa/15264)
- [Michalsons — Transfers of personal information outside South Africa](https://www.michalsons.com/focus-areas/privacy-and-data-protection/transfers-of-personal-information-outside-south-africa)
- [MJ Kotze Inc — Cross-Border Data Transfer Agreement (POPIA)](https://mjkinc.co.za/agreements/cross-border-data-transfer-agreement)
- [Global Policy Watch — Long-awaited POPIA guidance on direct marketing published by the Information Regulator (Dec 2024)](https://www.globalpolicywatch.com/2024/12/long-awaited-popia-guidance-on-direct-marketing-published-by-south-africas-information-regulator/)
- [Meta — Business Tools Terms](https://www.facebook.com/legal/technology_terms)
- [Meta for Developers — Meta Pixel GDPR implementation (consent API)](https://developers.facebook.com/documentation/meta-pixel/implementation/gdpr)
- [TikTok for Business — Pixel Cookie Consent Mode documentation](https://business-api.tiktok.com/portal/docs/pixel-cookie-consent-mode/v1.3)
- [TikTok Ads Help — About notifications of potentially prohibited data sharing on TikTok](https://ads.tiktok.com/help/article/about-notifications-of-potentially-prohibited-data-sharing-on-tiktok)
- [Usercentrics — TikTok privacy policy: data-sharing terms for businesses](https://usercentrics.com/guides/privacy-policies-of-major-platforms/tiktok-privacy-policy/)
- [Lokker — Managing Meta Pixel data exposure: a technical governance perspective](https://lokker.com/blog/meta-pixel-privacy)
- [Accountable — Meta Pixel in healthcare: HIPAA compliance, privacy risks, and safer alternatives](https://www.accountablehq.com/post/meta-pixel-in-healthcare-hipaa-compliance-privacy-risks-and-safer-alternatives)
- [FlexyConsent — Meta Pixel and Facebook Conversions API: GDPR/CCPA consent implementation guide](https://flexyconsent.com/blog/meta-pixel-facebook-conversions-api-consent-guide/)
- [Ignite — 29 studies on cookie banners, consent rates, and compliance](https://www.ignite.video/en/articles/basics/cookie-consent-studies)
- [Litlyx — Cookie consent banners and conversion loss](https://litlyx.com/blog/cookie-banner-loss)
- [Milkmoon Studio — The cookie consent dilemma: what happens when data vanishes](https://www.milkmoonstudio.com/post/the-cookie-consent-dilemma-what-happens-when-97-of-your-data-vanishes)
- Sourcing caveat applied throughout to: CookieChimp, EcomSolve, PopiaReady, ASi Technologies,
  FitConsent, and similar consent-management-platform vendor blogs surfaced in this research — treated
  as marketing, not legal opinion, per the same caveat the sibling research applied to the same
  category of source for GA4.
- In-repo: `spec_dd/3. done/2026-09-23_11:31_google-analytics-setup/research_consent_south_africa.md`,
  `spec_dd/3. done/2026-09-23_11:31_google-analytics-setup/research_user_id_and_pii.md`,
  `docs/how tos/google-analytics-and-ads.md`, `legal_docs/_default/privacy.md`

status: ok
