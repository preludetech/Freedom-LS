# Research: Privacy and Compliance for Signup Attribution Data

> This is research to inform a product design decision, not legal advice. FLS ships to downstream
> operators across multiple jurisdictions; a downstream operator's DPO or external counsel must
> still sign off on their own processing. Where regulators disagree across jurisdictions, or the
> law is genuinely unsettled, that is stated explicitly below rather than resolved by picking a side.

## Findings that would change a design decision

1. **Reading an already-set `_ga`/`_fbp`/`_fbc` cookie server-side and copying its value into a
   permanent, user-keyed database row is very likely a *second*, separate processing purpose from
   whatever consent the downstream operator's cookie banner obtained for GA/Meta Pixel itself.**
   Consent captured for "analytics" or "advertising cookies" in a banner is scoped to that named
   purpose (Article 5(3) ePrivacy governs the *setting/reading* act; GDPR purpose limitation, Art
   5(1)(b), governs what FLS then does with the value once read). Storing the raw identifier
   permanently, joined to a real identity, for a purpose the banner never described ("attribution
   record retained indefinitely against your account in the LMS admin") is a plausible purpose-limitation
   violation even where the *initial* GA/Pixel cookie-setting was validly consented to downstream. This is
   the single biggest legal exposure in the current design, because "the downstream deployment
   obtained consent [for GA]" does not automatically license *FLS's* re-use of that cookie's value.
   See §3–4.
2. **The "no consent gate inside FLS" reasoning conflates two different regulated acts: *setting*
   a cookie and *reading* one.** Article 5(3) ePrivacy applies to "storing of information, or
   gaining access to information already stored, in the terminal equipment" — reading is expressly
   included, not just writing. If FLS's own middleware or view reads `document.cookie`-equivalent
   values (`_ga`, `_fbp`, `_fbc`) server-side via the request, FLS is performing a regulated
   "access" act, not merely a passive recipient of something the browser already sent to the
   downstream operator's own analytics vendor. Whether that access is lawful turns on whether the
   downstream site's consent banner's scope covers *this* access by *this* application, which is
   not guaranteed by the existence of a GA-consent banner. See §3.
3. **The append-only, "written once, never updated" design as literally specified is not compatible
   with the right to erasure/rectification unless FLS also builds an anonymisation or hard-delete
   path.** Comparable systems (see §6) resolve this by treating "never updated" as an application-level
   integrity guarantee about *normal write paths*, while a separate, audited erasure operation
   (delete or field-level null-out/hash) remains available for DSAR/Art 17 compliance. If FLS ships
   only an immutable model with no erasure mechanism at all, downstream operators cannot comply with
   erasure requests without direct database intervention that breaks the "official" data model —
   which itself creates an audit gap. `LegalConsent` gets away with true immutability because it
   is evidence of a *legal act* (consent given at a point in time), which has a recognised legal
   basis for indefinite retention independent of the data subject's other rights; attribution data
   has no equivalent status. See §6.
4. **`gclid`/`fbclid` and the raw `Referer` header are frequently treated as personal data in
   practice even though there is no CJEU ruling specific to click IDs**, because they are unique,
   persistent-enough identifiers capable (like the dynamic IP address in *Breyer*) of being linked
   back to an individual by the ad platform that issued them, and because in this design they are
   joined to a real user account regardless. Treat all captured fields as personal data once written
   to the per-user row — see §1.
5. **A DPIA is likely, not just "possible."** Under the WP29 nine-criteria test (still the working
   methodology referenced by EDPB and most national authorities), this design plausibly meets at
   least two criteria simultaneously — "matching or combining datasets" (session cookie + ad-network
   identifiers + IP + UA joined to identity) and, if the admin view is later used to build campaign/source
   scoring per learner, "evaluation or scoring of individuals." Two or more criteria is WP29's own
   threshold for presuming a DPIA is required. See §5.

---

## 1. What is personal data here

GDPR Art 4(1) defines personal data as anything relating to an identified or identifiable natural
person, including by reference to "an identifier such as a name, an identification number, location
data, an online identifier." POPIA's definition of "personal information" (s1) and its adjacent
"unique identifier" concept are drafted broadly enough to catch the same category of data —
identifiers relating to an identifiable, existing natural person — even though POPIA does not name
cookies specifically. ([POPIA guidance summary](https://www.michalsons.com/blog/cookie-law-south-africa/15264), [Information Regulator POPIA materials](https://inforegulator.org.za/popia/))

Per field:

| Field | Personal data on its own? | Personal data once joined to the user row? |
|---|---|---|
| Client IP address | Yes for a *controller with legal means* to obtain identity from an ISP — this is exactly the *Breyer* test: a **dynamic** IP address is personal data for a controller that has a legal avenue (even via a third party, e.g. law enforcement request to an ISP) to resolve it to a person; the CJEU declined to require the controller to hold that means *directly*. ([CJEU C-582/14 Breyer, 19 Oct 2016](https://www.dataprotectionreport.com/2016/10/cjeu-judgement-dynamic-ip-addresses-constitute-personal-data/), [IAPP summary](https://iapp.org/news/a/in-breyer-decision-today-europes-highest-court-rules-on-definition-of-personal-data)) | Unambiguously yes — the whole question in *Breyer* was about an IP address held *without* an accompanying identity; here it's captured directly against a signed-up user. |
| User agent string | Rarely identifying alone (many people share the same UA), but is one of the standard fields used in device/browser fingerprinting; treated by EDPB and ICO as an "identifier" contributing to identifiability, not personal data in true isolation. | Yes, once tied to a named account it is simply an attribute of that person's record. |
| `_ga` value | GA client ID is a persistent, semi-unique identifier tied to a browser instance; multiple EU DPAs (see §3/§5) have already treated GA identifiers as personal data in enforcement decisions, generally in combination with IP. | Yes, unambiguous. |
| `_fbp` / `_fbc` | Same reasoning — Meta's own documentation describes these as identifiers used to match a browser to ad conversion events; that is definitionally identifying. | Yes. |
| `gclid` / `fbclid` | Debated in industry commentary — some treat them as opaque "technical assignment keys" for ad billing rather than online identifiers of a *person*; others (and the more cautious/majority industry position, given they are frequently combined with IP/UA to reconstruct a click event to an individual) treat storage of a click ID in a cookie or DB as personal-data processing requiring the same care as `_ga`. There is no CJEU or EDPB ruling squarely on click IDs. ([overview of the debate](https://help.etracker.com/en/article/gclid-data-protection-assessment/), [click identifier overview](https://en.wikipedia.org/wiki/Click_identifier)) | Yes once persisted against a user row — the ambiguity about standalone status becomes moot. |
| Referrer/partner code (`ref`) | On its own, arguably not personal data — it identifies an *organisation or partner*, not the learner. | Becomes personal data the moment it's stored as an attribute of a specific signed-up individual (it then discloses something about that person — which partner referred them — even if the code itself names an organisation). |
| HTTP `Referer` header | Can contain query strings, search terms, or session tokens from the referring page, and is widely treated by EDPB/ICO guidance as data capable of being personal depending on content. | Yes once attached to a user row. |
| `utm_*` / landing path / first-seen timestamp | Low identifiability alone (campaign labels, not individuals) but contributes to a profile. | Yes as attributes of an identified person. |

**Practical conclusion for design purposes:** because every field in this feature is, by construction,
written into a row keyed to `user`, the "is it personal data on its own" analysis is largely academic
— **the entire row is personal data under both GDPR and POPIA the moment it exists**, regardless of
which individual fields might have escaped that classification in isolation. Design and retention
decisions should proceed from that premise rather than trying to carve out "non-personal" fields.

---

## 2. Lawful basis (GDPR) / justifiable processing condition (POPIA)

**Legitimate interest (GDPR Art 6(1)(f)) is the most realistic basis for the *marketing-attribution*
purpose** (knowing which campaign/partner drove a signup) — this is a standard "measuring the
effectiveness of marketing" use case that EDPB's own Guidelines 1/2024 accept can, in principle, be
legitimate, provided the three-part test is satisfied:

1. **Purpose test** — the interest must be lawful, clearly and precisely articulated, and real/present, not speculative.
2. **Necessity test** — no less-intrusive way of achieving the same result.
3. **Balancing test** — weighing the controller's interest against the data subject's interests, rights and reasonable expectations, considering "the nature of the personal data, the reasonable expectations of individuals, and the potential consequences of the processing."

([EDPB Guidelines 1/2024, adopted 8 Oct 2024](https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202401_legitimateinterest_en.pdf), [summary](https://www.edpb.europa.eu/system/files/2024-10/edpb_summary_202401_legitimateinterest_en.pdf))

A legitimate-interest assessment (LIA) for this feature has to actually show, in writing:
- The specific business interest (attributing signups to marketing spend/partner relationships) — not "improving the product" generically.
- Why first-touch `ref` and last-touch UTM capture is *necessary* to that interest (i.e., that a coarser method — e.g. asking the user directly "how did you hear about us" — would not serve it as reliably).
- That a reasonable user, given the site's context, would expect this (a learner signing up for a course reasonably expects the operator to know it came from an email link or partner; they less obviously expect a permanent record of Facebook/Google ad-network identifiers against their name).
- The safeguards in place — retention limit, access restriction (admin-only, as scoped), no onward sharing.

**Where it breaks down — the ad-network identifiers specifically.** EDPB's position (both in the
legitimate-interest guidance and in the Board's repeated line on tracking, e.g. as summarised in
coverage of Guidelines 1/2024) is that **consent, not legitimate interest, is the required basis for
non-essential tracking/advertising cookies and their associated identifiers**, because these exist
specifically to enable cross-site/cross-service measurement that most data subjects would not expect
or welcome, and the "reasonable expectations" limb of the balancing test fails for exactly that reason.
([coverage of EDPB Guidelines 1/2024 on tracking](https://usercentrics.com/knowledge-hub/gdpr-legitimate-interest/))
This matters here because the decision already made is that FLS reads and stores `_ga`/`_fbp`/`_fbc`
under **no FLS-level consent gate at all** — relying entirely on the downstream operator's *separate*
GA/Pixel consent. Even if that downstream consent is valid for GA/Pixel to operate, it does not by
itself supply GDPR's lawful basis for **FLS's own act of reading and permanently storing** those
values against an identified account (see purpose-limitation analysis in §4) — that act needs its
*own* justification, and "legitimate interest" is a weak fit for identifiers whose entire purpose is
cross-site ad measurement.

**POPIA:** s11 requires one of several justifications, the closest analogues being consent, a
legitimate interest of the responsible party under s11(1)(f) (materially similar three-part
structure to GDPR Art 6(1)(f)), and processing necessary for the conclusion/performance of a
contract. For attribution data unconnected to actually delivering the LMS service, contract necessity
is a poor fit (attribution is not needed to *perform* the learner's contract). The Information
Regulator's public guidance leans toward **consent as the safe default** for tracking data linked to
an identifiable individual, and explicitly rejects opt-out mechanisms as valid consent under s11 —
consent must be prior, specific and opt-in. ([POPIA/cookie compliance overview](https://cookiefirst.com/south-africas-protection-of-personal-information-act-popia-and-cookie-consent/), [POPIA cookie requirements](https://cookiechimp.com/guides/regulations/za_popia))
This creates a jurisdictional split worth stating plainly: **GDPR's legitimate-interest route for the
UTM/referrer part of this feature does not translate cleanly to POPIA**, where the Regulator's
guidance points much more firmly toward requiring consent for any cookie/identifier data linked to
an individual.

---

## 3. The ePrivacy/cookie question — separate from GDPR lawful basis

Article 5(3) of the ePrivacy Directive (2002/58/EC, as amended) — and its national implementations,
e.g. the UK's PECR — regulates **storing information, or gaining access to information already
stored, in a user's terminal equipment**, independently of whatever GDPR lawful basis might apply to
what happens with the data afterwards. This is a genuinely separate legal question from §2.

**a) Is the first-party `fc_attr` cookie "strictly necessary"?**
The strictly-necessary exemption is narrow: it applies only where the cookie is *objectively required*
to provide a service the user has actually requested (session/basket/security cookies are the
paradigm case), not merely commercially useful to the site operator. ICO guidance is direct on this:
cookies that are "helpful for the organization's commercial interests" but not essential to deliver
what the user asked for do **not** qualify, and analytics-style cookies in particular are called out
as **not** strictly necessary. ([ICO cookie guidance](https://ico.org.uk/media2/kz0doybw/guidance-on-the-use-of-cookies-and-similar-technologies-1-0.pdf), [summary of the ICO test](https://usercentrics.com/knowledge-hub/ico-pecr-cookie-guidance/))
An attribution cookie that exists purely so the operator can later credit a signup to a campaign is
squarely in the "commercially useful, not user-requested" category — **it does not pass the
strictly-necessary test as ordinarily applied**, and the safe design assumption is that it requires
consent under ePrivacy in the EU/UK, exactly like an analytics cookie.

National positions genuinely differ here, though, and that difference is real, not cosmetic:
- **France (CNIL)** operates a specific, narrow **audience-measurement exemption**: first-party
  analytics cookies can be set without consent if they are used *solely* for measuring site
  performance, are not cross-referenced with other processing, do not enable cross-site tracking,
  are capped (cookie lifetime ~13 months, data retention ~25 months), and users are informed via the
  privacy notice. If any of those conditions fail — and campaign/attribution data joined to an
  identified user account, retained indefinitely, is a poor fit for "solely audience measurement,
  no cross-referencing" — the exemption does not apply. ([CNIL Sheet n°16](https://www.cnil.fr/en/sheet-ndeg16-use-analytics-your-websites-and-applications), [exemption criteria summary](https://captaincompliance.com/education/cnil-clarifies-when-analytics-cookies-can-be-used-without-consent/))
- **UK (ICO/PECR)**: historically firm that analytics cookies require consent, full stop — no
  general first-party exemption. That changed narrowly with the Data (Use and Access) Act 2025,
  which inserted PECR Schedule A1 introducing a limited **"first-party, statistics-only" exemption**
  effective from 5 February 2026, requiring clear information and a free, easy opt-out, with no
  data sharing beyond service improvement. Even under this new UK exemption, the criteria (statistics-only,
  no sharing) look hard to satisfy for a cookie whose captured values are later copied into a durable,
  user-identified database row consumed for campaign/partner attribution — that is a use beyond pure
  site statistics. ([ICO PECR guidance overview / DUAA changes](https://usercentrics.com/knowledge-hub/ico-pecr-cookie-guidance/), [CookieYes summary of the 2026 change](https://www.cookieyes.com/blog/uk-cookie-guidance-ico-pecr/))
- **EDPB** (Board-level, cross-EU) has not endorsed a general first-party-analytics exemption; its
  guidance treats Article 5(3) as applying broadly to any storage/access act regardless of first-
  vs third-party framing, leaving individual DPAs to run their own narrower exemptions (as CNIL does)
  at national level. There is **no EU-wide safe harbour** to rely on; a downstream FLS operator in,
  say, Germany or Ireland should not assume the CNIL exemption travels with them.

**Bottom line for `fc_attr`:** it is very likely a **consent-requiring cookie under ePrivacy/PECR**
in the general case (not strictly necessary), with a narrow and jurisdiction-specific chance of
falling under an analytics-style exemption only if FLS's cookie is used *solely* for aggregate
measurement and never joined to an identified account — which conflicts directly with this feature's
actual design (it is joined to the account by construction). The product should not assume
`fc_attr` is exempt; it should assume the downstream operator needs a consent mechanism covering it,
or must accept the cookie is unlawful to set in EU/UK without one.

**b) Reading vs setting `_ga`/`_fbp`/`_fbc`.**
Article 5(3)'s text is "storing of information, **or gaining access to information already stored**"
— access is regulated exactly as storage is. This directly undermines the "FLS never sets these
cookies, so it's the downstream deployment's problem" framing: **FLS's own act of reading these
cookie values server-side (from the incoming request) and copying them into its database is itself
a regulated access act**, attributable to FLS/the site operator running FLS, not to Google or Meta.
Whether that access is lawful depends on whether the *specific purpose* FLS uses it for (a permanent,
user-identified attribution record) is within the scope of whatever consent the downstream operator's
banner obtained for GA/the Pixel *generally*. A banner that says "we use Google Analytics to
understand site usage" does not self-evidently cover "and a different Django application on this
site will also read the resulting cookie and store it forever against your account for the
LMS admin to browse." That is a distinct question from whether GA itself was consented to — see §4.

**c) The 2024–2025 EDPB guidance on Article 5(3) scope.**
EDPB adopted **Guidelines 2/2023 on the Technical Scope of Article 5(3)** in final form on
**7 October 2024**. Its headline effect is to *widen*, not narrow, what counts as a regulated
storage/access act — covering URL/pixel tracking, local processing, IP-only tracking, and unique
identifiers generally, explicitly reasoning that Article 5(3) is technology-neutral and not limited
to literal HTTP cookies. ([EDPB Guidelines 2/2023, final Oct 2024](https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf), [law-firm summary](https://www.lexology.com/library/detail.aspx?g=fc19acf3-7fcd-4d3a-a8ee-37e8a0d08372), [Fieldfisher: "broad reading of the cookie rule"](https://www.fieldfisher.com/en/insights/edpb-reiterates-its-broad-reading-of-the-cookie-rule-in-the-e-privacy-directive))
**This does not change any conclusion above — if anything it reinforces them.** It confirms that
reading `gclid`/`fbclid` from a URL parameter, or reading an ad-network cookie server-side, falls
within Article 5(3)'s scope regardless of the mechanism, closing off any argument that "we only read
a query string / an already-set cookie, we don't call `document.cookie`" would place this feature
outside ePrivacy's reach.

---

## 4. Consent-scope mismatch: does a GA cookie-banner consent cover FLS copying `_ga` into its own DB?

This is the crux of the current design's risk and deserves to be stated precisely rather than
hand-waved.

Two separate rules are both engaged, and both point the same way:

- **ePrivacy consent scope (Art 5(3)):** consent to *store/access* information in terminal equipment
  must be specific to the purpose disclosed at the time — Planet49 (CJEU C-673/17, 1 Oct 2019)
  establishes that cookie consent must be active, informed, and specific (no pre-ticked boxes,
  and the user must be told the *duration* of the cookie and *whether third parties* will have
  access to it). ([CJEU Planet49 summary](https://www.twobirds.com/en/insights/2019/global/planet49-cjeu-rules-on-cookie-consent), [Curia press release](https://curia.europa.eu/site/upload/docs/application/pdf/2019-10/cp190125en.pdf)) If the downstream operator's banner text says (as most GA
  banners do) "we use analytics cookies to understand how visitors use this site," it has not told
  the user that a *second* application (FLS) reads that same cookie and stores its value permanently,
  joined to their name/email, for a different purpose (partner/campaign attribution visible in an
  admin screen). That is a *different third party having access* than what Planet49 requires be
  disclosed.
- **GDPR purpose limitation (Art 5(1)(b)):** even accepting the GA cookie's setting was validly
  consented to, further processing (FLS's copy-into-DB step) must be for a purpose that is either
  the *same* as the one disclosed, or a *compatible* one assessed under Art 6(4)'s compatibility
  factors (link between purposes, context of collection, nature of the data, consequences for the
  data subject, and safeguards). ([ICO purpose limitation guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-protection-principles/a-guide-to-the-data-protection-principles/purpose-limitation/)) "Understand aggregate site usage" and "build
  a permanent, per-individual record of which ad network/campaign brought this specific named
  person to sign up, visible in the operator's admin" are not obviously the same purpose, and the
  second is materially more consequential for the data subject (it is durable, personally identified,
  and administratively browsable — closer to a marketing-attribution dossier than an aggregate stat).

**Where purpose-limitation actually bites:** the boundary is not "was GA consented to" but "was
*this specific, durable, identity-linked re-use* of the GA identifier disclosed and consented to."
As specified, the feature's privacy notice obligations (§5) exist precisely to close this gap — the
downstream operator's notice/banner has to name *this* processing explicitly, not rely on GA's own
notice covering it by implication. Until that disclosure exists, storing `_ga`/`_fbp`/`_fbc` in the
per-user row rests on a consent that, on its most natural reading, was never actually given for that
specific act.

---

## 5. What the downstream operator must be told and must do

Because FLS is installed into someone else's Django project, and that operator is the data
controller for their learners, FLS's design obligations here are really *disclosure and configuration*
obligations — give the operator what they need to be compliant, don't assume compliance on their
behalf.

**Privacy notice.** The operator's notice needs to name, in plain language: (a) that a first-party
cookie is set at first landing and persists 90 days; (b) that UTM/campaign parameters, a referrer
code, the referring page, and (if present) Google/Meta ad-click and ad-cookie identifiers are
captured; (c) that this data is copied into a permanent record tied to the learner's account at
signup; (d) who can see it (admin users only, as scoped); (e) how long it's kept; (f) that it is not
shared with third parties (true today, per the "only consumer is Django admin" decision — but this
needs to stay true or the notice needs to change). Recital 42/60 GDPR transparency requirements and
ePrivacy's own information requirement (cookie duration + third-party access, per Planet49) both
demand this be specific, not generic "we use cookies" boilerplate.

**Article 30 ROPA entry.** The operator needs a processing-activity record naming: purpose (marketing
attribution), categories of data subjects (learners), categories of data (listed above), recipients
(none beyond internal admin), retention period, and — critically — cross-reference to the lawful
basis analysis in §2 (legitimate interest for UTM/referrer, and the operator's own separately-obtained
consent basis, if any, for the ad-network identifiers). FLS should ship a template/starter entry
so operators aren't reverse-engineering this from the schema.

**DPIA.** Likely required, not merely advisable, once assessed against the WP29 nine-criteria
screening (still the reference methodology cited by EDPB and most national DPA guidance): this
design plausibly satisfies **"matching or combining datasets"** (cookie/session values + IP + UA +
ad-network IDs, joined to an identity) on its own, and would add **"evaluation or scoring of
individuals"** if the admin view is ever used to build per-learner source/quality scoring.
Two-or-more-criteria is WP29's own presumption-of-DPIA threshold.
([WP29 nine-criteria summary](https://iapp.org/news/a/what-is-and-what-isnt-subject-to-a-dpia-under-gdpr-an-update), [ICO "when do we need a DPIA" guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/data-protection-impact-assessments-dpias/when-do-we-need-to-do-a-dpia/)) FLS cannot run this DPIA *for* the operator (it's inherently
deployment-specific — depends on scale, jurisdictions served, whether the operator also runs GA/Pixel
at all), but it should supply enough documentation (data flow diagram, field list, retention default)
that the operator's DPIA is a filling-in exercise, not a from-scratch investigation of FLS internals.

**International transfer angle.** This is not intrinsic to FLS's own database (storing a copy of
`_ga` in FLS's own Postgres instance is not itself a transfer — that depends on where the operator
hosts FLS). But it *is* a live issue **at the point the downstream operator's own GA/Meta Pixel
sends data to Google/Meta in the US** — multiple EU DPAs (Austria's DSB, 13 Jan 2022; France's CNIL,
10 Feb 2022; followed by Italy's Garante, Denmark's Datatilsynet, Finland's Ombudsman) have ruled
that standard Google Analytics implementations violate GDPR's Chapter V transfer rules because
Google is subject to US surveillance law access requests, independent of SCCs being in place.
([Austria DSB ruling coverage](https://www.orrick.com/en/Insights/2022/02/The-Austrian-Data-Protection-Authority-Groundbreaking-Google-Analytics-Decision), [CNIL ruling coverage](https://iapp.org/news/a/cnil-is-latest-authority-to-rule-google-analytics-violates-gdpr), [roundup of the multi-DPA rulings](https://plausible.io/blog/google-analytics-illegal)) This is squarely the downstream operator's problem (they chose to run GA), but FLS's
documentation should flag it explicitly: *"if you run GA/Meta Pixel on a site FLS serves, note that
several EU DPAs have found standard GA/Pixel configurations non-compliant absent extra safeguards —
that is a decision and a risk that sits with you as the site operator, separate from FLS's own
processing."* Leaving this unsaid invites an operator to assume FLS's silence means it's a
non-issue.

---

## 6. Retention and erasure

**Retention.** GDPR/POPIA storage-limitation principles require a defensible, purpose-tied period,
not indefinite retention by default. For marketing-attribution data specifically, a reasonable
anchor is the operational lifetime of the interest it serves — how long does "which campaign caused
this signup" remain useful for the business purpose articulated in the LIA (§2)? For most LMS
sales/marketing cycles that is on the order of the analysis/reporting cycle (commonly argued as
12–24 months in comparable marketing-attribution designs), not "forever." CNIL's own audience-
measurement exemption criteria (§3a) use 13-month cookie / 25-month data caps as its own reference
points for what regulators consider defensible for *this class* of data — a useful anchor even though
that specific exemption doesn't apply cleanly here. There is no single legally mandated number; the
requirement is that *whatever* period is chosen be justified against the stated purpose and
documented, not left open-ended by default.

**DSAR / right of access.** The row is a normal, low-effort target for Art 15/POPIA s23 access
requests once it exists — it must be included in the operator's DSAR-fulfilment scope (or FLS's own
DSAR tooling, if it has any) precisely because it's a per-user record like any other.

**Erasure vs "written once, never updated."** This is a genuine, unresolved tension in the current
design, not a false one:
- Article 17 GDPR (and POPIA's equivalent) gives a right to erasure that does not carve out an
  exception for "attribution logs" the way it does for legal-compliance records (e.g., financial
  records under a statutory retention duty). `LegalConsent`'s immutability is defensible because it
  documents a *legal act* — evidence a person did consent, which typically needs to be *retained*,
  not erased, to defend the controller's own compliance position (the record proves lawful processing
  occurred). Attribution data has no equivalent status: there's no legal requirement to keep proof
  a particular user came from a particular campaign, so it doesn't inherit `LegalConsent`'s
  justification for permanence.
- Comparable systems generally resolve the append-only-vs-erasure tension by keeping "append-only" as
  an integrity guarantee about the **normal application write path** (no in-place mutation of
  historical values, no silent overwrites) while providing a **separate, privileged erasure/anonymisation
  operation** — invoked only for DSAR/legal purposes, itself logged — that nulls out or hashes the
  identifying fields (or deletes the row) rather than editing them. ("Anonymisation is the... release
  valve" — if identifiers are irreversibly stripped, the row is no longer personal data under GDPR
  Recital 26 and can be kept indefinitely for whatever residual statistical value it has.)
  ([overview of the erasure/audit-log tension and anonymisation-as-release-valve](https://axiom.co/blog/the-right-to-be-forgotten-vs-audit-trail-mandates), [GDPR erasure/anonymisation discussion](https://techgdpr.com/blog/reconciling-the-regulatory-clock/))
- **Does the row survive account deletion in anonymised form, and is that lawful?** Yes, provided
  the anonymisation is genuine (irreversible — not merely hashing the user FK while leaving IP/UA/
  ad-identifiers intact, which would likely still be re-identifiable and thus not true anonymisation
  under GDPR's stricter reading of Recital 26). A row stripped of the user linkage *and* of
  re-identifying fields (IP, UA, ad-network IDs) but retaining only aggregate campaign/channel labels
  is defensible to keep for business reporting after account deletion; a row that merely drops the
  FK while keeping IP+UA+`_ga` is not meaningfully anonymised and remains personal data subject to
  erasure obligations.

**Conclusion:** the "written once, never updated" principle should be read as "never *edited*
through the normal application path," not as "never erasable." FLS needs an erasure/anonymisation
mechanism for this table if it is to be shippable to GDPR/POPIA-covered operators at all — an
immutable table with genuinely no deletion path is not a defensible design for identity-linked
marketing data.

---

## 7. Data minimisation, applied field by field

| Field | Less-identifying alternative | What's lost |
|---|---|---|
| Client IP address | Truncate (zero last octet / /24 for IPv4, /64 for IPv6) or hash with a rotating salt | Loses exact-geolocation precision and any ability to correlate the *same* IP across records (e.g. detecting the same physical connection driving multiple signups) — a real capability loss if fraud/duplicate-detection is a goal, negligible loss if the only goal is coarse geographic/ISP-level attribution reporting. |
| User agent string | Parse into device/browser/OS family (e.g. "Chrome / Android / mobile") and discard the raw string | Loses exact version numbers (useful for debugging rendering issues, not for attribution) and any fingerprinting-grade specificity. For a pure attribution-reporting purpose, nothing of value is lost; it also reduces the identifiability of the row generally, since raw UA strings are one of the more fingerprint-capable fields. |
| `_ga`/`_fbp`/`_fbc` raw values | Store only a boolean ("arrived with a GA/Pixel identifier present") or a non-reversible hash, rather than the platform-usable identifier itself | Loses the ability to ever *cross-reference* this row against Google/Meta's own platforms (e.g. for later audience-matching or conversion upload) — which is precisely the cross-site-linking capability that makes these fields sensitive in the first place. If that cross-platform matching is not an actual planned use case, storing the raw value buys nothing over the hash/boolean and only adds risk. |
| `gclid`/`fbclid` | Same as above — hash, or drop after using it once to determine "came from a paid ad, platform X" and store only that derived label | Loses the ability to later push offline-conversion data back to Google Ads/Meta using the click ID (a real capability some marketing teams want) — but that's a distinct, larger feature (server-side conversion API integration) that isn't in scope here; storing the raw ID "just in case" is speculative collection against a purpose not yet defined, which cuts against the GDPR/POPIA necessity test in §2. |
| `ref` referrer code | Already coarse (an organisation-level code); little to minimise further, though it should not be enriched with anything beyond what's needed to attribute the signup to the partner (e.g. no need to also store the partner's internal contact details on this row). | Nothing significant to lose — this field is already close to the minimum needed. |
| Raw `Referer` header | Store only the parsed host/domain of the referrer, not the full URL (which can carry the *previous* site's own query parameters, including that site's search terms or session tokens) | Loses path-level detail (e.g. which specific partner blog post linked here) — a real reporting loss if per-page referral analysis matters, negligible if only "came from partner-x.com" matters. |
| `utm_*` params, landing path | Already coarse/campaign-level by design; minimal further reduction available. | — |
| First-seen timestamp | Truncate to day-level rather than exact timestamp | Loses same-session/velocity analysis (e.g. distinguishing "clicked ad, signed up in 2 minutes" from "clicked ad, signed up 89 days later") — a real loss if funnel-speed reporting matters; negligible otherwise. |

The general pattern: **every field with a cross-platform-linking capability (the ad-network cookies
and click IDs) is also the field where minimisation costs the least relative to the stated
attribution purpose** — because their re-identification/cross-linking power is not itself needed to
answer "which campaign/partner drove this signup," only to *also* enable audience-matching back on
the ad platforms, which is a separate, undeclared purpose as things stand (see §2, §4).

---

## 8. The multi-tenant angle

FLS's isolation boundary is the Django `Site`; a single install can serve multiple operators with
different privacy notices, different consent-banner configurations (or none), different retention
appetites, and potentially different governing law (a South African-only deployment vs. one also
serving EU/UK learners). This has direct implications:

- **Consent/notice state cannot be assumed global.** If any part of this feature's lawfulness
  depends on what a *particular* site's consent banner discloses (per §3–4), FLS cannot hard-code an
  assumption that "the operator has a GA consent banner covering this" — that has to be knowable
  per-`Site`, not asserted once for the whole install. At minimum, the retention period and any
  "capture ad-network identifiers at all" toggle should be **`Site`-scoped configuration** (mirroring
  the existing `SiteSignupPolicy` per-site pattern), not a single global setting — because one
  tenant's operator may have obtained valid, specific consent for this exact use while another's has
  not, and one tenant may be GDPR/POPIA-covered while another might not be.
- **Retention settings should be per-`Site`** for the same reason — different operators will have
  different defensible retention periods depending on their own LIA/notice, and a single global
  default forces the most conservative operator's requirement onto all tenants (over-retaining for
  the strict one, or under-retaining for one that had a genuine longer-term need) unless it's
  configurable per site.
- **Notice text is inherently the operator's responsibility per site**, not something FLS can bake
  in centrally — but FLS's admin/config surface should make it easy to see, per site, whether
  attribution capture is even enabled, since that's the fact each operator's own notice needs to
  reflect.
- **DSAR/erasure operations (§6) must be `Site`-scoped** as a matter of basic tenant isolation — an
  erasure mechanism that could reach across `Site` boundaries would itself be a data-isolation defect
  independent of privacy law, given `Site` is FLS's existing security boundary.

---

status: ok
