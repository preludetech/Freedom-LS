# Course prices

A course can carry a price, and FLS shows it to people browsing courses. FLS only displays the
price. It takes no payment, and a price does not change who can register or access content.

## Why

Deployments sell some courses, and until now nothing in FLS could say what a course costs. It also
calls every course free: `FreeOnlyCourseAccessBackend` gives every course a "Free" `AccessBadge` and
"Free · open to everyone" copy. That copy has been accurate only because no course could cost
anything.

## What a price can be

Each course has at most one price, and the price is exactly one of these kinds:

- **Fixed.** One amount, e.g. R1 499.
- **Range.** A low and a high amount, both typed by the author, e.g. "R1 200 – R3 000". FLS does not
  model what makes the price vary, such as group size or organisation. The author states the range
  and FLS displays it. Low must be less than high.
- **Discounted.** An original amount and a sale amount, with an optional end date. The sale amount
  must be less than the original. After the end date the course shows the original amount as a
  fixed price, so a stale sale never stays on screen. FLS does not compute or show "% off".
- **On request.** No amount. The course shows a "contact us for pricing" state, for B2B and
  corporate-cohort courses.

Any course with an amount can also carry an optional **tax note**, free text such as "incl. VAT",
shown next to the price. FLS does not work out tax.

A course with no price behaves exactly as it does today.

## Settled decisions

- **Price is ordinary course metadata.** Authors write it in `course.md` frontmatter, the offline
  validator checks it, and the Django admin can edit it, as with `difficulty` and
  `estimated_duration`. It does not go in `access_config`. That blob is private to the access backend and is about how a
  learner gets access. The author docs already give `price:` under `access_config` as an invalid
  example.
- **Currency is per course, with a project default.** A course may give an ISO 4217 code. If it
  does not, a project-wide default currency setting applies, following the per-app `AppSettings`
  pattern. The ISO code is the stored value. The currency symbol is derived for display only,
  because symbols are ambiguous ("$", or "R" next to "R$").
- **Amounts are decimals, not floats.** FLS stores them as decimals. Authors write them in YAML as
  quoted strings (`"1499.00"`), because bare YAML numbers go through float. `research_money_storage.md`
  covers why decimals are chosen over integer minor units and why django-money is not used: it does
  not support Django 6.
- **A priced course drops the "Free" wording.** A course with any price (on request included) shows
  the price where the "Free" badge and free copy would otherwise appear, on cards, rows and the
  course page. Courses without a price keep today's "Free" wording. Registration and the CTA do not
  change.
- **One shared price component renders every surface:** course card, course row, the course page's
  stats strip and the sign-up panel. Formatting, currency and accessibility then live in one place.
- **The struck-through original price must be announced to screen readers.** A discounted price
  pairs the struck-through original with visually hidden "Original price" / "Now" text, because
  screen readers do not reliably announce `<del>` or `<s>`.
- **The course page emits schema.org structured data.** It uses `Offer` for fixed and discounted prices
  (with `priceValidUntil` from the sale end date), `AggregateOffer` (`lowPrice`/`highPrice`) for a
  range, and nothing for on request. This will be the first JSON-LD in FLS.

## Out of scope

- Payments, checkout, and gating access on payment. A paid-course access backend is sketched
  separately in `spec_dd/3. done/2026-06-23_13:04_applying-for-courses/possible_future_backends.md`.
- Several prices per course (tiers, cohorts, plans) and ranges derived from them.
- Price history. FLS cannot check reference-pricing rules such as the EU Omnibus 30-day lowest-price
  rule. The author is responsible for making sure a "was" price is honest.
  `research_price_display_ux.md` §6–7 covers the legal background and the Udemy fake-discount
  settlement.
- Tax calculation, exchange rates, and showing one course in several currencies.
- Filtering or sorting courses by price.

## Open questions for the spec

- **Formatting.** Add Babel for locale-aware `format_currency`, or write a small in-house formatter
  keyed on the currency code. `research_money_storage.md` §5 leans towards the small formatter until
  FLS renders in more than one locale.
- **Currencies with other minor units.** JPY has 0 decimal places and KWD has 3. Decide whether to
  validate decimal places per currency or allow up to 3 and let the formatter round.
- **Wording in each slot.** How a range and an on-request price read in the narrow card chip compared
  with the course page. For example, "From R1 200" on a card and the full range on the page.

## Research

- `research_fls_integration.md`: where course metadata is authored, loaded and validated, every
  surface where a price would appear, and the access-layer constraints.
- `research_reference_implementations.md`: how Open edX, Moodle, LifterLMS, WooCommerce and others
  model prices, and schema.org `Offer`/`AggregateOffer`.
- `research_price_display_ux.md`: display patterns, accessibility, and legal limits on discount
  display.
- `research_money_storage.md`: decimals compared with minor units, currency codes, formatting, and
  YAML authoring.
