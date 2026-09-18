# Research: UX patterns and pitfalls for displaying course prices

Scope: how course cards, catalogue listings and course landing pages should present
single prices, price ranges, discounts, free courses, and "price on request" —
plus the accessibility and legal traps that come with them. FLS itself only needs to
**display** prices (payment processing is out of scope for this idea), so the focus
below is presentation, not pricing/checkout logic.

---

## 1. TL;DR / concrete recommendations (see full detail in §8)

- Store price data as **structured facts** (currency, amount(s), price-type, discount
  metadata, effective dates), and keep **all rendering/formatting decisions in the
  template layer** — never bake a formatted string into the database.
- Support four price "shapes" as first-class display states: **single price**, **price
  range**, **discounted price** (original + current), and **free**. Add a **"price on
  request"** state for completeness even if not urgently needed.
- Never rely on `<del>`/`<s>`/CSS `line-through` alone to communicate "this is the old
  price" — screen readers do not reliably announce that semantic. Pair the crossed-out
  price with visually-hidden text (e.g. "Original price:" / "Now:").
- Don't invent a currency-symbol-only display when the audience may span currencies
  that share a symbol (`$`, `£`-like ambiguity is rarer, but `$` covers USD/CAD/AUD/etc).
  Prefer **symbol + ISO 4217 code** in any multi-currency or ambiguous context, and use
  proper locale-aware number formatting (thousands/decimal separators, symbol position).
- Be explicit about **tax treatment** ("incl. VAT" / "excl. VAT" / "+ tax") wherever the
  organisation is not obviously single-jurisdiction — silence here is itself a dark
  pattern in many jurisdictions.
- If FLS or any site using it ever shows a "was" / struck-through price, treat that as a
  **compliance-sensitive feature**, not just a visual style — the EU, UK and US all have
  rules (of varying strictness) about what a "was" price is allowed to mean. Don't build
  a generic "original price" field without at least a comment/TODO flagging this, and do
  not implement a synthetic/inflated reference price.
- Avoid Udemy-style patterns: perpetual "sale ends soon" countdowns, discounts that are
  never actually a genuine reduction from a real prior price, and vague "up to 90% off"
  banners. These have already resulted in real regulatory and class-action exposure for
  other platforms — don't reproduce the pattern even informally.
- A **price range** ("From $49") on a card should always resolve to something concrete
  and truthful on the detail page (e.g. per-cohort price, per-tier price, or bundle
  price) — never a vague range that can't be tied to an actual purchasable price.

---

## 2. Price display patterns by shape

### 2.1 Single price
The simplest and least error-prone case: one currency, one amount, one course. Common
convention across catalogue cards (Udemy, Coursera individual courses, Domestika) is:
large/bold current price, muted/smaller original price struck through if discounted,
positioned consistently (bottom of card, near the CTA button) so users can compare
across a grid without hunting for the number.

### 2.2 Price ranges ("From $X", "$X–$Y")
Ranges appear on course cards/catalogues in two genuinely different underlying
situations, and mixing them up is a common source of learner confusion:

- **"From $X" (open-ended floor)** — used when a single course/programme has multiple
  purchase options (e.g. multiple cohorts, tiers, add-ons, or bundle inclusion) and the
  card is showing the *cheapest* entry point. This is the SaaS-pricing-table convention
  ("Starting at...") applied to courses — see LearnDash/WooCommerce variable-product
  integrations, which show variant-level pricing (e.g. self-study vs. self-study +
  coaching) and often surface the *minimum* price on the card while the detail page
  resolves the full option set.
- **"$X–$Y" (closed range)** — used when the *same* purchase can genuinely cost different
  amounts depending on a variable outside the buyer's immediate choice, e.g. per-seat
  cohort pricing that changes by intake, or a "name your price" scheme with an enforced
  minimum and maximum (LearnDash's "Name Your Price" add-ons let the site owner choose
  whether to surface the minimum, maximum, or suggested price prominently on the card
  vs. detail page).

Pitfall: a catalogue card showing "$49–$199" for a *single* SKU with a *single* price is
misleading; ranges should only appear when there truly are multiple distinct purchasable
prices behind that course. If FLS ever needs to support ranges, the range should be
derived (min/max across the concrete price options), not entered as a free-floating
range that can drift from the real prices.

### 2.3 Discounted prices
The near-universal convention (Udemy, Domestika, most e-commerce) is: original price with
strike-through styling next to/above the discounted price, often with a percentage-off
badge ("83% off", "-40%") and sometimes a countdown or "sale ends" date to create
urgency. Domestika, for example, runs discount-driven catalogue pages ("Discounted
Courses") advertising up to 83% off, and often frames annual-subscription pricing as a
percentage saving vs. monthly ("19% discount for paying yearly").

Key design questions this raises for FLS-style content:
- What is the "original" price actually anchored to? (see §5 — legal constraints)
- Is the discount time-bound (needs an end date/urgency messaging) or permanent
  (e.g. early-bird vs. standard, cohort-based)?
- Should the % off be computed and displayed, or just show both absolute prices and let
  the learner do the maths? (Percentage badges increase urgency but also increase
  regulatory/complaint risk if the base is not genuine — see §5, §6.)

### 2.4 Free courses
"Free" needs a clearly distinct, positive visual treatment — not just "$0.00" or a blank
price field, which reads as a bug/missing-data state. Common conventions: a green/positive
"Free" pill or badge in the same slot other cards show a price, so grid-scanning still
works. Coursera's "audit for free" pattern is a related but distinct concept worth noting:
the *course* can be free while a *credential/certificate* tied to it is paid — i.e. "free"
sometimes needs to be qualified ("Free to audit", "Free — certificate extra") rather than
a bare label, to avoid learners feeling misled at the point of certification. (Coursera
narrowed this significantly in late 2024, restricting free audit availability — a useful
cautionary example that "free" labelling policy can be a business decision that changes
over time, so it should be data-driven, not hardcoded per course.)

### 2.5 "Price on request" / "Contact us"
Common in B2B/enterprise and cohort-based corporate training contexts, less common in
consumer course catalogues (Udemy/Coursera/Domestika, being self-serve consumer
platforms, essentially never use it). It's a legitimate pattern for FLS to support as a
price-type (e.g. bespoke corporate cohorts, custom enterprise pricing) even though none
of the researched consumer platforms needed it — it should render as a clear CTA
("Contact us for pricing") in the same visual slot as a price, not as an absence of data.

---

## 3. Currency symbol vs. ISO code, and locale formatting

- A bare currency **symbol** is ambiguous whenever the audience could be international:
  `$` alone is used by USD, CAD, AUD, NZD, and many others. The safest pattern for any
  multi-currency or export-facing product is **symbol + ISO 4217 code** in ambiguous
  contexts (e.g. "$49 USD"), or ISO code alone when multiple currencies could appear
  side-by-side on the same page/table.
- For single-currency, single-market deployments (plausible for many FLS installs), a
  bare localized symbol is fine and is what most audiences expect — over-labelling every
  price with "ZAR"/"USD" when the whole site is one currency adds visual noise for no
  benefit. This should be a **site-level configuration decision**, not hardcoded.
- Number formatting (decimal separator, thousands separator, symbol position
  before/after the number, spacing) is genuinely locale-dependent (e.g. `$1,234.56` vs
  `1.234,56 €`) and should go through locale-aware formatting (e.g. Python's `babel` /
  Django's `django.contrib.humanize` + locale machinery, or JS `Intl.NumberFormat` for
  any client-rendered price), not manual string formatting — this avoids a whole class
  of "looks like a typo" bugs when the same course is shown to users in different
  locales.
- Domestika's approach — detect the buyer's likely currency from IP/registration and
  localize prices, falling back to USD when the local currency isn't supported — is a
  reasonable model for a global consumer platform, but is more infrastructure than FLS's
  stated scope ("just need to show the prices for now"); worth noting as a
  **future/out-of-scope extension point**, not something to build now.

---

## 4. Tax-inclusive vs. tax-exclusive display

- Regional norms differ sharply: VAT/GST jurisdictions (EU, UK, South Africa, Australia)
  overwhelmingly expect **consumer-facing prices to be tax-inclusive by default** — in
  several of these jurisdictions inclusive pricing to consumers is a legal requirement,
  not just a convention. US sales-tax norms are the opposite: prices are typically shown
  **tax-exclusive**, with tax added at checkout because sales tax varies by
  buyer-jurisdiction and can't be known until checkout.
- Where a course price could be shown to a mixed audience (e.g. a South African LMS
  instance also enrolling international learners) or where the org serves both B2C and
  B2B audiences, an explicit qualifier next to the price ("incl. VAT" / "excl. VAT" / "+
  applicable tax") removes ambiguity. Silently omitting this — showing a bare number with
  no tax context — is the single most common tax-related pricing complaint in the
  ecommerce UX literature, and in inclusive-by-law jurisdictions can itself be a
  compliance problem, not just a UX nicety.
- Since FLS is explicitly **not** doing payment processing yet, tax treatment cannot be
  computed/known reliably at display time in the general case. Recommendation: support
  an optional free-text or enum "tax note" alongside the price (e.g. "excl. VAT", "incl.
  VAT", or blank) that the course owner sets explicitly, rather than FLS trying to infer
  or compute tax status.

---

## 5. Accessibility: strike-through prices and screen readers

This is a well-documented, easy-to-get-wrong problem:

- Visually, "was/now" pricing is almost always rendered with CSS `text-decoration:
  line-through`, or the HTML `<del>`/`<s>` elements. The critical gap: **most screen
  readers do not announce strike-through/deletion semantics by default**, even though
  `<s>` and `<del>` both map to an ARIA "deletion" role in principle — browser/AT support
  for actually surfacing that role to the user is inconsistent, so a screen-reader user
  frequently hears only "forty nine dollars, twenty nine dollars" with no indication
  which is current and which is the crossed-out original. This can mislead blind/low-
  vision users into thinking the *higher* price is what they'll pay, or into missing the
  discount entirely.
- `<s>` and `<del>` are also semantically distinct even though they render identically:
  `<s>` is for content that is "no longer accurate" (fits a superseded price), `<del>` is
  for content that was literally removed/revised. Either can be justified for a former
  price; `<s>` is the more common recommendation for this specific use case.
- **Recommended pattern** (converging recommendation across accessibility sources):
  combine the semantic element with visually-hidden ("sr-only") text that spells out the
  relationship in words, e.g.:
  ```html
  <span class="sr-only">Original price:</span>
  <s>$99.00</s>
  <span class="sr-only">Now:</span>
  <span class="price-current">$59.00</span>
  ```
  This guarantees the meaning survives even where the strike-through role isn't
  announced, and costs nothing visually.
- Whatever component/pattern FLS ends up using for discounted-price display should bake
  this in once, centrally (e.g. a shared price-display template/cotton component), so
  every call site gets it "for free" rather than depending on every author remembering to
  add hidden text by hand.

---

## 6. Legal constraints on "was" / reference pricing

This section is included so the eventual spec/design can flag reference-pricing as a
**compliance-sensitive area** even though FLS's current scope is display-only. These
rules generally target advertised price *reductions*, not price display in general, but
if FLS ever supports "original price" + "discounted price" together, this is directly
relevant to how that feature should be described/guarded in the spec (e.g. requiring the
course owner to attest the original price is genuine, rather than FLS silently trusting
any two numbers it's given).

- **EU — Omnibus Directive (Directive (EU) 2019/2161), "Price Reduction" rule.** When a
  trader announces a price reduction, they must state the prior price, and that prior
  price must be the **lowest price applied in the 30 days before the reduction** — not
  a temporarily-inflated price shown just before a "sale". Any advertised discount
  percentage must be calculated against that 30-day-lowest price, not a higher recent
  price. Compliance in practice requires a timestamped price history per SKU. Note:
  the Directive's core "movable goods" scope is aimed at physical retail goods; digital
  content/services and B2B are generally described as outside its direct scope in
  commentary, though guidance and enforcement in this area continues to evolve — this
  should not be read as a settled exemption for online course sales without local legal
  advice. (Sources: Talon.One, Voucherify, 7Learnings, Bird & Bird, RPC.)
- **UK — CMA guidance on reference pricing** (developed via cases like CMA v Emma Sleep /
  Emma Matratzen): a "was" price must (a) have been offered for a sufficient period
  immediately before the discount, no shorter than the discount period itself, and (b) a
  meaningful volume of actual sales should have occurred at that price — CMA guidance
  suggested roughly one sale at the "was" price for every two sold at the discounted
  price, though a 2026 High Court ruling in the CMA v Emma case rejected a rigid
  fixed-volume requirement, indicating this area is still legally unsettled and evolving.
  A trader's genuine, good-faith belief that the reference price was a real, achievable
  price is treated as relevant even where actual sales at that price were low.
  (Sources: TLT, HSF Kramer, Mills & Reeve, UK gov "Discount and reference pricing
  principles" guidance.)
- **US — FTC Guides Against Deceptive Pricing (16 CFR § 233.1), "Former price
  comparisons".** A former ("was") price used in a comparison must be the actual,
  bona-fide price at which the item was openly offered to the public on a regular basis,
  for a reasonably substantial period, in good faith — not an artificial price
  established only to make a subsequent "discount" look bigger. There have also been
  concrete enforcement/litigation consequences for platforms that got this wrong (see
  §7, Udemy).
- **South Africa — Consumer Protection Act (CPA).** General marketing/advertising
  provisions require that pricing claims be factual, accurate and not misleading; the
  CPA doesn't appear (from available guidance) to have as detailed a "30-day lowest
  price" or "sales-volume" test as the EU/UK rules, but the general misleading-marketing
  prohibition would still cover a fabricated "was" price. Worth flagging for legal review
  if FLS is deployed by South African organisations advertising discounts, rather than
  treating the absence of a specific numeric rule as "no risk."

**Practical takeaway for the spec:** reference/"was" pricing is not a purely cosmetic
feature — if FLS supports it, the spec should require the *course owner* to supply and
own the "original price" (FLS just displays what it's given, doesn't synthesize a
discount), and any UI copy suggesting a discount is "genuine"/time-limited should not be
FLS's own invention layered on top of arbitrary data.

---

## 7. Common complaints and dark patterns

- **Fake/perpetual discounts (Udemy).** Udemy agreed to a $4M class-action settlement
  over allegations that its near-permanent "sale" pricing used fabricated "original"
  prices that courses were never actually sold at, inflating the perceived value of the
  discount. The suit also alleged a **fake urgency countdown** on the homepage that,
  once it hit zero, simply reset/continued showing "ends in 0s" rather than the sale
  actually ending — a textbook "false urgency" dark pattern. Lesson for any system
  displaying discounts: don't invent expiry countdowns unless the discount genuinely and
  verifiably expires, and don't display a struck-through "original" price unless it
  reflects a real, previously-charged price.
- **Percentage-off theatre.** Very large, round discount percentages ("83% off", "90%
  off") shown as a matter of course (as opposed to occasionally, for genuine clearance)
  train users to distrust the baseline price entirely and to wait for "the next sale" —
  this is a general ecommerce/dark-pattern complaint, not specific to one platform, and
  is one of the underlying behaviours the EU Omnibus and UK CMA rules were written to
  curb.
- **Ambiguous "starting at" pricing that never resolves to something purchasable at that
  price** — e.g. a catalogue card advertises "From $29" but by the time a learner reaches
  checkout, the only available options are all above that figure (out-of-stock cheapest
  tier, expired cohort, etc.). This erodes trust in the same way as fake reference
  pricing, even though it's a range/tiering issue rather than a strike-through issue.
- **Missing free/no-cost signalling clarity** — offering "free" access to some
  functionality (audit) while gating the credential behind payment, without making that
  distinction obvious at the point the word "Free" is shown, generates complaints when
  learners feel the "free" label was bait for an eventual paywall (see Coursera's audit
  model, and its 2024 narrowing of free-audit availability).

---

## 8. Examples surveyed

| Platform | Price shapes observed | Notable pattern |
|---|---|---|
| **Udemy** | Single price, heavy discount ("was/now" + %), perpetual near-100%-off sales | Subject of a $4M settlement over fake reference prices and a fake countdown timer — a clear anti-pattern to avoid. |
| **Coursera** | Free (audit), single price (course), subscription (monthly), tiered (Specializations/Professional Certificates), high-ticket (degrees) | "Free to audit, pay for certificate" — free label needs qualification. Free-audit availability itself has narrowed over time (business-policy-driven, not fixed). |
| **edX** | Single price, subscription, percentage-off promo codes | Time-boxed % promos ("20% off") rather than permanent strike-through pricing. |
| **Thinkific / Teachable / Kajabi** | These are course-*platform* pricing tiers (for the creator, not per-course consumer pricing) rather than course price display per se | Useful as a tiered-plan UX reference (ascending price order, feature comparison tables) but not a direct analogue for course-catalogue price display. |
| **LearnDash (+ WooCommerce)** | Single price via linked WooCommerce product, sale price/regular price pair, variable pricing (course + coaching bundles), "Name Your Price" with min/max/suggested | Explicitly supports choosing *which* of several prices (min/max/suggested) to foreground on the card vs. detail page — directly relevant prior art for FLS "price range" design. |
| **FutureLearn** | Free-to-audit + paid upgrade, subscription, time-boxed % promos | Broadly mirrors Coursera's free/paid split. |
| **Domestika** | Single price with heavy sale/discount framing, subscription (Domestika Plus) with annual-vs-monthly % saving framing, geolocation-based currency | Explicit multi-currency localization by IP/registration is a relevant future extension point, and its discount-catalogue page ("up to 83% off") is a live example of the perpetual-discount pattern to be wary of. |

---

## 9. Concrete recommendations for FLS

1. **Model prices as structured data, not strings.** At minimum: currency (ISO 4217),
   amount(s) as a decimal, a `price_type` (single / range / discounted / free / on
   request), and — only if/when discounts are supported — a separate "original amount"
   field that is explicitly owned/entered by the course owner rather than derived or
   defaulted.
2. **Build one shared price-display component** (cotton component, per FLS's HTMX/Cotton
   conventions) used by course cards, catalogue listings and the course landing page, so
   formatting, accessibility markup, and currency handling live in one place. Don't let
   each template hand-roll its own price string.
3. **Bake accessibility in at the component level**: any discounted-price rendering must
   pair the struck-through original with visually-hidden text (`sr-only` "Original
   price:" / "Now:") rather than relying on `<del>`/`<s>` alone.
4. **Make "Free" a distinct, positive, first-class state** in the same visual slot as a
   price — not `$0.00`, not an empty field.
5. **Treat currency formatting as a locale concern, not a template string concern.** Use
   Python's locale/Babel-style formatting (or Django's built-in humanize/l10n machinery)
   for amount formatting; don't hand-format `f"${amount}"` anywhere the site may ever
   need another currency or locale. Include the ISO code alongside the symbol wherever
   more than one currency could plausibly appear on the same page.
6. **Give course owners an explicit, optional tax note field** ("incl. VAT" / "excl.
   VAT" / custom text) rather than trying to infer or compute tax treatment — FLS has no
   payment/checkout context to compute this reliably, and *silence* on tax treatment is
   itself a UX/compliance risk in VAT-inclusive-by-default jurisdictions.
7. **If/when a range price-type is supported**, derive "From $X" / "$X–$Y" display from
   the actual set of concrete purchasable prices behind the course (cohorts, tiers,
   bundle variants) — never allow a free-floating range value that isn't backed by real
   priced options, to avoid the "advertised range I can't actually get" complaint pattern.
8. **If/when a discounted/"was" price-type is supported**, flag it in the spec as
   compliance-sensitive: require the course owner to supply the original price (FLS
   displays, does not synthesize, discounts), avoid generating urgency messaging
   ("ends in..." countdowns) unless there's a real, enforced expiry, and consider adding
   a short note in the spec pointing implementers at EU Omnibus / UK CMA / US FTC
   reference-pricing rules for any deployment that advertises discounts to consumers.
9. **Support a "price on request" / "contact us" state** even though none of the
   consumer platforms surveyed use it — it's a real need for B2B/corporate cohort
   pricing that FLS, as an installable/extensible LMS, is likely to be used for.

---

## References

- EU Omnibus Directive / 30-day lowest price rule:
  - [Talon.One — EU requirements for advertising with price reductions](https://www.talon.one/blog/eu-requirements-for-advertising-with-price-reductions)
  - [Voucherify — Omnibus Directive and discounts](https://www.voucherify.io/blog/omnibus-directive-how-it-impacts-your-discount-strategy)
  - [7Learnings — What retailers need to know about the EU Omnibus Directive](https://7learnings.com/blog/what-retailers-need-to-know-about-the-new-eu-consumer-protection-directive/)
  - [Bird & Bird — Transparency of price reductions in the EU](https://www.twobirds.com/en/insights/2025/global/transparency-of-price-reductions-a-closer-look-at-the-legal-framework-in-the-eu)
  - [RPC — European Commission guidance on price promotions under Omnibus](https://www.rpclegal.com/snapshots/consumer/spring-2022/european-commission-publishes-guidance-on-price-promotions-under-the-omnibus-directive/)
- UK reference pricing / CMA:
  - [TLT — CMA v Emma Sleep: reference pricing battles](https://www.tlt.com/insights-and-events/insight/cma-v-emma-sleep-let-the-reference-pricing-battles-begin)
  - [Herbert Smith Freehills Kramer — High Court rejects CMA's fixed-volume requirement](https://www.hsfkramer.com/notes/crt/2026-07/high-court-rejects-cmas-fixed-volume-requirement-for-reference-pricing-in-emma-matratzencase)
  - [Mills & Reeve — CMA v Emma: court rejects fixed volume pricing](https://www.mills-reeve.com/publications/cma-v-emma-the-high-court-pulls-the-sheets-on-12-fixed-volume-pricing/)
  - [UK Government — Discount and reference pricing principles (mattresses case study)](https://assets.publishing.service.gov.uk/media/66ab4347a3c2a28abb50db3c/Discount_and_reference_pricing_principles.pdf)
  - [Business Companion — Guidance for traders on pricing practices](https://www.businesscompanion.info/en/guidance-for-traders-on-pricing-practices)
- US FTC:
  - [eCFR — 16 CFR Part 233, Guides Against Deceptive Pricing](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-233)
  - [LegalClarity — FTC Deceptive Pricing Rules, Tactics, and Penalties](https://legalclarity.org/ftc-deceptive-pricing-regulations-and-enforcement/)
  - [HinchNewman — How to comply with FTC deceptive pricing guides](https://ftcdefenselawyer.com/ftc-deceptive-pricing-guides/)
- South Africa CPA:
  - [LegalWise — Consumer Protection Act | CPA South Africa](https://www.legalwise.co.za/help-yourself/quicklaw-guides/consumer-protection-act)
  - [SAICA — Guide on the Consumer Protection Act (PDF)](https://saicawebprstorage.blob.core.windows.net/uploads/resources/ConsumerProtectionGuideFeb2014.pdf)
- Udemy fake-discount settlement / dark patterns:
  - [Class Central — Udemy agrees to pay $4M settlement over deceptive pricing](https://www.classcentral.com/report/udemy-settles-class-action/)
  - [Top Class Actions — Udemy's false sale pricing scheme](https://topclassactions.com/lawsuit-settlements/lawsuit-news/udemys-false-sale-pricing-scheme-misleads-and-damages-consumers-distorts-market-class-action-alleges/)
  - [ClassAction.org — Lawsuit alleges Udemy advertises videos at false discounts](https://www.classaction.org/news/inherently-misleading-lawsuit-alleges-udemy-advertises-videos-at-false-discounts-to-generate-sales)
  - [Hacker News discussion of the Udemy settlement](https://news.ycombinator.com/item?id=35738645)
- Accessibility of strike-through pricing:
  - [Web Axe — Strikethrough Accessibility](https://www.webaxe.org/strikethrough-html-accessibility/)
  - [PaulJAdam.com — Accessibility of CSS line-through / `<del>`/`<ins>`](https://pauljadam.com/demos/css-line-through-del-ins-accessibility.html)
  - [Orange Digital Accessibility Guidelines — Price vocalization](https://a11y-guidelines.orange.com/en/articles/price-vocalization/)
  - [eBay Open Source — Offscreen Text technique](https://opensource.ebay.com/evo-web/accessibility/techniques/offscreen-text)
- Currency symbol vs. ISO code / locale formatting:
  - [XTransfer — Currency Symbols Localization Guide](https://www.xtransfer.com/wiki/trade-terms/currency-symbols-localization-guide-for-beginners)
  - [Michael Samuel Naeem — Multi-Currency Display UX](https://blog.michaelsam94.com/payments-ux-multi-currency-display/)
  - [Medium (Shreya Rao) — The UX of currency conventions for a global audience](https://medium.com/design-bootcamp/the-ux-of-currency-conventions-for-a-global-audience-4098ff66b6ed)
  - [Carta Ink Design System — International Currencies](https://ink.carta.com/internationalization/currency-i18n/)
- Tax-inclusive vs. exclusive display:
  - [WebToffee — Tax Inclusive vs Exclusive](https://www.webtoffee.com/blog/inclusive-exclusive-tax/)
  - [u11d — Tax-Inclusive Pricing: Meeting International Customer Expectations](https://u11d.com/blog/tax-inclusive-pricing/)
  - [Dealavo — How to display prices in e-commerce: 5 UX best practices](https://dealavo.com/en/how-to-display-prices/)
- Course-platform pricing examples:
  - [LearnDash Dev Docs — Display Regular Price & Sale Price using custom fields](https://developers.learndash.com/snippet/display-regular-price-sale-price-on-course-using-custom-fields/)
  - [SaffireTech — Name Your Price for LearnDash](https://www.saffiretech.com/name-your-price-for-learndash/)
  - [FunnelKit — LearnDash WooCommerce Integration](https://funnelkit.com/learndash-woocommerce/)
  - [Honors WP — LearnDash Course Price Shortcodes](https://honorswp.com/docs/additional-shortcodes-for-learndash/course-price-shortcodes/)
  - [MyElearningWorld — Domestika Pricing](https://myelearningworld.com/domestika-pricing/)
  - [Domestika Support — In which currency are the prices shown?](https://support.domestika.org/hc/en-us/articles/360003316798-In-which-currency-are-the-prices-shown)
  - [Domestika — Discounted Courses catalogue](https://www.domestika.org/en/courses/on_sale)
  - [Domestika Plus — subscription pricing](https://www.domestika.org/en/plus)
  - [ThePivotWave — Coursera Cost in 2026](https://thepivotwave.com/blog/coursera-pricing/)
  - [Edubracket — Coursera pricing 2026: Plus, individual courses, and free audit mode](https://edubracket.com/articles/coursera-pricing-2026)
  - [Class Central — Back to School Discounts & Online Learning Deals 2026 (edX/FutureLearn promos)](https://www.classcentral.com/report/online-learning-deals/)
- Pricing-table UX patterns (SaaS, adapted for tiered course pricing):
  - [UX Planet — Best Practices for Pricing Table Design](https://uxplanet.org/best-practices-for-pricing-table-design-2d99e46201da)
  - [Smashing Magazine — Designing Effective Pricing Plans UX](https://www.smashingmagazine.com/2022/07/designing-better-pricing-page/)
  - [Smart Interface Design Patterns — Pricing Plans UX](https://smart-interface-design-patterns.com/articles/pricing-plans/)

status: ok
