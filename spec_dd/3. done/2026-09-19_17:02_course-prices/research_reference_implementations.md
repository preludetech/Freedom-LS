# Research: how other LMS / course platforms model course prices

Scope: survey of pricing data models and authoring UI in comparable systems, to inform
FLS's course-price feature (display-only for now; payment processing out of scope but
should not require a schema migration to add later).

All field/vocabulary names below belong to the system named in each section. FLS's own
terms should be chosen separately per `domain_vocabulary.md`, not copied wholesale.

---

## 1. Open edX — `course_modes` app (`CourseMode` model)

Source: `common/djangoapps/course_modes/models.py` in
[openedx/openedx-platform](https://github.com/openedx/openedx-platform/blob/master/common/djangoapps/course_modes/models.py),
and the instructor docs on
[Manage Course Fees](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-cypress/running_course/manage_course_fees.html).

Shape: a course can have **multiple `CourseMode` rows** (one per "mode", e.g. `audit`,
`verified`, `professional`, `credit`), each a separate enrollment track with its own
price, not just a display variant.

Key fields per mode:
- `mode_slug` / `mode_display_name` — identifies the track (audit/verified/etc.)
- `min_price` (IntegerField, whole currency units, default 0) — the price for that mode.
  Note the field's own history: it used to support a *set* of prices the learner chose
  from (see `suggested_prices` below) but that was deprecated in favour of one price per
  mode.
- `suggested_prices` (CharField, **deprecated**) — originally a comma-separated list of
  suggested "pay what you can/at least" amounts for a mode (used for a donation-style
  slider on verified certificates). Code comments explicitly say this was abandoned for
  a single price.
- `currency` (CharField, default `"usd"`, lowercase ISO 4217-ish code) — currency lives
  on the same row as the price, i.e. **per-mode currency, not per-course**.
- `expiration_datetime` — an upgrade deadline (after this date you can no longer buy
  into this mode), not a *sale* window; it gates availability of the mode rather than
  changing its price.
- `sku`, `android_sku`, `ios_sku`, `bulk_sku` — opaque identifiers used to hand off to
  the external ecommerce/basket service; **no payment logic lives in this app** — it's
  purely a catalog of purchasable tracks with prices, and a separate ecommerce service
  does checkout. This is the closest analogue to "display prices now, wire up payments
  later without a migration": the price-bearing rows already exist and just gain a
  foreign key/SKU into a payment system later.

Range/discount handling: **no explicit price-range or discount-with-dates concept** in
this model. A "range" is approximated only by having several modes (e.g. audit=$0,
verified=$50) rather than one course having a low/high price for the same thing.
Discounts are handled entirely by the external ecommerce service (coupons/enterprise
offers), not by this app.

---

## 2. Moodle — `enrol` instances (`enrol_fee`-family plugins, e.g. `enrol_paypal`)

Source: [Moodle enrol table schema](https://moodleschema.zoola.io/tables/enrol.html),
[Enrolment plugins dev docs](https://moodledev.io/docs/4.5/apis/plugintypes/enrol),
[Enrolment on payment](https://docs.moodle.org/501/en/Enrolment_on_payment).

Shape: price is not a property of the course itself but of an **enrolment method
instance** attached to a course. The generic `enrol` table holds one row per enrolment
method (manual, self, fee/paypal, etc.); fee-taking plugins add `cost` and `currency` to
that instance (custom columns interpreted per-plugin, since `enrol.customchar`/
`customint`/`customdecimal` fields are reused by each plugin type).

- **A single course can have multiple enrolment instances simultaneously**, each with
  its own cost/currency and its own role assignment — e.g. "self-enrol free" plus
  "PayPal fee $49" side by side. This is structurally similar to Open edX's multiple
  modes, but framed around *how you get in* rather than a named tier.
- Currency is per-instance, matching the instance's cost field, so a single course can
  in principle show different currencies via different instances.
- No native price range or scheduled discount at the model level in core Moodle; sales/
  coupons are left to third-party or payment-gateway-specific plugins.
- Trade-off: this is a very payments-first shape (the price literally lives on the
  enrolment mechanism), so it doesn't map cleanly onto "just display a price, no
  payment yet" — you'd have to keep the fee plugin's cost field but never activate the
  plugin's checkout part.

---

## 3. LifterLMS — Access Plans

Source: [`LLMS_Access_Plan` model](https://github.com/gocodebox/lifterlms/blob/trunk/includes/models/model.llms.access.plan.php),
[Access Plan Options docs](https://lifterlms.com/docs/access-plan-options/),
[`is_on_sale()`](https://developer.lifterlms.com/reference/classes/llms_access_plan/is_on_sale/).

Shape: an **Access Plan is its own WordPress post type** (`llms_access_plan`), and a
course/membership ("product") can have **many access plans**, each a distinct
purchasing option (e.g. "One-time $199", "3 monthly payments of $75", "Free preview").
This is the richest multi-plan model surveyed.

Per-plan pricing fields:
- `price` (float) — the plan's regular price ("price per charge").
- `is_free` (yes/no) — plans can be explicitly free rather than $0.
- `on_sale` (yes/no) flag, `sale_price` (float), `sale_start`, `sale_end` (date
  strings) — **a discount is its own price plus an explicit start/end date window**,
  and `is_on_sale()` computes whether "now" falls in that window before the sale price
  is used. This directly matches the idea's "discounted price" requirement and shows a
  clean way to model a time-bounded discount alongside a regular price.
- `trial_offer` (yes/no), `trial_price`, `trial_length`/`trial_period` — a separate
  trial-price concept, distinct from a sale.
- `frequency` (0 = one-time, 1-6 = recurring interval count), `period`
  (year/month/week/day), `length` (number of billing cycles, 0 = until cancelled) —
  this is the recurring/subscription shape, orthogonal to the sale-price shape.

Range/discount handling: LifterLMS has **no single "range" field**; a price range is
achieved only by exposing multiple access plans (e.g. min and max tier) side by side,
not by one plan storing a low/high pair. Discounts are first-class (sale_price +
window), which is the strongest reference for "specific discounted price with a
schedule."

---

## 4. LearnDash — course access mode + custom price fields

Source: [Course Enrollment Mode Settings](https://learndash.com/support/kb/core/settings/course-access/),
[Display Regular Price & Sale Price via custom fields (dev snippet)](https://developers.learndash.com/snippet/display-regular-price-sale-price-on-course-using-custom-fields/).

Shape: a course has one **price/access "mode"** chosen from a fixed enum: `open`,
`free`, `buy now`, `recurring`, `closed`. This is a coarser model than LifterLMS/edX —
one price-bearing mode per course, not a collection of plans, plus a custom "button URL"
for `closed` courses that redirect to an external sales page (i.e. "price varies, go
elsewhere to find out"). LearnDash's own core price field is a single number for `buy
now`/`recurring`; **regular price + sale price is not built in** — the docs show it only
as a custom-fields snippet layered on top by site builders, which is a useful negative
data point: even a popular LMS treats "sale price" as a bolt-on, not core schema.

---

## 5. Tutor LMS — Pricing Model + Purchase Options

Source: [Subscriptions docs](https://docs.themeum.com/tutor-lms/subscriptions/), [Native ecommerce subscriptions](https://tutorlms.com/docs/native-ecommerce-subscriptions/).

Shape: course-level `Pricing Model` toggle (`Free` / `Paid`). When Paid, a course has a
single **Regular Price**, and then optionally one or more **Purchase Options**, which
can mix a one-time purchase with one or more named **Subscription** plans (name, price,
billing interval, cycle count). Similar in spirit to LifterLMS's multi-plan approach,
but the "one-time regular price" and "subscription plans" are modelled as different
kinds of objects rather than a uniform list of plans that can each be one-time or
recurring.

---

## 6. Thinkific — primary price + "Additional Prices"

Source: [Set Additional Prices For Your Products](https://support.thinkific.com/hc/en-us/articles/360030721813-Set-Additional-Prices-For-Your-Products),
[Create a Subscription Price](https://support.thinkific.com/hc/en-us/articles/360034692814-Create-a-Subscription-Price-for-Your-Product).

Shape: a product (course/bundle) has **one primary price** (free, one-time, or
subscription) plus an arbitrary number of **additional prices**, each independently
one-time, payment-plan (instalments), or subscription. Structurally this is "primary +
list of alternates," a variant of the plan-list shape (LifterLMS/Tutor) rather than a
low/high range.

---

## 7. Teachable and Kajabi — mostly commercial-tier gating, not schema novelty

Source: [Teachable — Price your products](https://support.teachable.com/en/articles/11682476-price-your-products),
[Kajabi — free trials & flexible payment options](https://www.kajabi.com/blog/introducing-free-trials-flexible-payment-options).

Both support one-time price, payment plans (instalments), and subscriptions per
product/offer, gated behind their own platform pricing tiers (e.g. Teachable's
cheapest tier can't do payment plans/subscriptions at all). Neither exposes public
schema docs, but the *shape* is consistent with the others surveyed: a product has one
or more "offers"/pricing options, each with its own type (free/one-time/instalment/
subscription) rather than a single row with a low/high pair. No public evidence of a
first-class "range" or dated-discount concept distinct from swapping which offer is
shown.

---

## 8. WooCommerce — simple vs. variable product pricing

Source: [Variable Products documentation](https://woocommerce.com/document/variable-product/),
WooCommerce core product fields (`regular_price`, `sale_price`, `date_on_sale_from`,
`date_on_sale_to`).

This is the clearest **general e-commerce** (not LMS-specific) reference, and maps well
onto "range" and "discount" as the idea.md describes them:

- **Simple product**: `regular_price`, `sale_price` (optional), `date_on_sale_from`,
  `date_on_sale_to` (optional schedule). If `sale_price` is set and "now" is within the
  from/to window (or no window is set, meaning the sale is indefinite), the sale price
  is shown instead of the regular price, with the regular price struck through. This is
  the same shape as LifterLMS's plan-level sale fields, and is a strong candidate
  shape for FLS's "discounted price."
- **Variable product** (one product, many variations e.g. size/colour, or here:
  cohort/format): each **variation** has its own `regular_price`/`sale_price` pair, and
  WooCommerce **computes and displays a price range** (e.g. "$49.00 – $79.00") by taking
  the min and max of the variations' *currently active* price (so a variation on sale
  contributes its sale price, not its crossed-out regular price, to the range). This is
  important: **"range" here is a derived display, not a stored field** — there is no
  `low_price`/`high_price` column; it's computed from the set of child prices at read
  time. This matches one plausible reading of the idea.md range requirement ("price
  range from X to Y") if X and Y correspond to real, purchasable variants (e.g.
  cohorts/tiers) rather than a single course having an arbitrary abstract range.

---

## 9. schema.org `Offer` / `AggregateOffer` (SEO structured data)

Source: [schema.org/Offer](https://schema.org/Offer), [schema.org/AggregateOffer](https://schema.org/AggregateOffer),
[Yoast — AggregateOffer](https://developer.yoast.com/features/schema/pieces/aggregateoffer/).

This matters for FLS because whatever is stored needs to be *renderable* as valid
structured data if/when SEO markup is added, without another migration.

- **`Offer`** (single price): `price` (decimal string, no currency symbol),
  `priceCurrency` (ISO 4217, e.g. `USD`), `priceValidUntil` (date) — Google's own
  guidance for showing a *sale* is: put the **current/sale price** in `price`, and put
  the sale's end date in `priceValidUntil`; the "was" price is not part of the vocabulary
  at all (it's a copy/display concern, not structured data). `Offer` also has
  `validFrom`/`validThrough` (more general availability window) and `availability`
  (in stock / pre-order / etc., not really applicable to courses but shows the pattern
  of "state + date range" recurring across all these systems).
- **`AggregateOffer`** (range across multiple offers/variants): required properties are
  `priceCurrency` plus **either** a single `price` **or** `lowPrice`/`highPrge` (a true
  low/high pair) and typically `offerCount`. This is the one place in the entire survey
  where a genuine **stored low/high range pair** is a first-class, named concept —
  everybody else either has multiple discrete priced entities (modes/plans/variations)
  or computes a range from those. If FLS ever emits structured data, a "range" price
  should be representable as `lowPrice`/`highPrice`, which argues for storing (or being
  able to derive) an explicit min and max rather than only a fuzzy "price varies" flag.

---

## Common shapes across all systems

1. **Multiple discrete priced entities per course**, each independently priced
   (Open edX modes, Moodle enrolment instances, LifterLMS/Tutor/Thinkific plans,
   WooCommerce variations). This is the dominant shape. A "range" is then either (a) not
   modelled at all — you just see several distinct prices, e.g. $0 / $50 / $200 — or
   (b) computed at display time as min/max across the entities (WooCommerce), never
   stored as its own field.
2. **A dedicated "on sale" shape**: base/regular price + sale price + optional
   start/end dates for the sale (LifterLMS, WooCommerce). This is the most common and
   most directly reusable shape for the idea.md "discounted price" requirement. The
   discount is a *property of a price*, not a separate price entity.
3. **Currency travels with the price**, not with the course: every system that models
   currency at all (Open edX, Moodle, schema.org) puts the currency code on the same
   row/object as the amount, because different modes/instances/offers can validly be in
   different currencies (e.g. multi-region pricing). None of them hoist currency up to
   a single course-level field only.
4. **A true stored low/high range field pair only appears in schema.org's
   `AggregateOffer`** (`lowPrice`/`highPrice`), and there it's explicitly a *summary*
   over other offers, not a manually authored range with no underlying detail. Nobody
   in the survey lets an author type "from $X to $Y" as a freestanding fact with no
   corresponding priced entities behind it — though it's plausible FLS's authors want
   exactly that (a simple range annotation with no underlying tiers), which none of
   these systems directly models; it would be a genuinely new shape for FLS if that's
   the intended UX, worth flagging as a design decision rather than assuming a
   reference implementation covers it.
5. **Payment/checkout metadata (SKUs, gateway IDs) is always additive**, layered onto
   the price-bearing row (Open edX's `sku`/ecommerce fields, Moodle's plugin-specific
   enrolment columns) rather than baked into how price/currency/discount are stored.
   This is good news for FLS: a schema built around "priced entity(ies) with
   amount + currency + optional discount(+window)" can later gain optional
   `sku`/`external_product_id`-style columns for payment integration without touching
   the existing price/discount columns or requiring backfill.

## Trade-offs relevant to FLS, and migration-safety

- **Single price field on the course** (simplest, closest to LearnDash's core model)
  is the cheapest to build and display, but cannot express "range" or "discount"
  without new columns later, and cannot express multiple simultaneous prices (e.g.
  early-bird vs regular) without a schema change.
- **Course has one Price object (amount, currency, optional sale_price + sale window)**
  (LifterLMS/WooCommerce shape, but singular instead of a list) directly satisfies
  "specific price" and "discounted price" from idea.md with a single row, and adding
  payment fields (`external_price_id`, `provider`) later is additive, not a migration
  of existing data. It does **not** natively express a "range from X to Y" — that would
  need either (a) treating the range as two more nullable fields (`min_price`,
  `max_price`) coexisting with the single-price fields, mirroring schema.org's
  `AggregateOffer` shape, or (b) modelling a range as multiple priced tiers instead
  (Open edX/LifterLMS shape) and computing the range for display like WooCommerce
  does.
- **Course has many Price/Plan rows** (Open edX modes, Moodle instances, LifterLMS
  plans, Tutor/Thinkific plans) is the most future-proof for payments (each plan can
  independently gain a payment-provider SKU later, exactly as Open edX's `sku` field
  does) and most naturally extends to real multi-tier pricing (cohort pricing,
  early-bird, group rates) without another migration — but it is more to build and
  display for what idea.md currently describes as a fairly simple requirement
  (single price OR a range OR a discount, not an open-ended list of tiers).
- Given idea.md's three stated cases — range, specific price, discounted price — the
  survey suggests the risk of under-building is a single scalar price field (can't
  grow into a range without a migration), while the risk of over-building is a full
  multi-plan/subscription system (Tutor/LifterLMS-grade) that FLS doesn't need yet
  since payments are explicitly out of scope. The shapes most directly reusable
  without either problem are: (a) LifterLMS/WooCommerce's amount+currency+optional
  dated sale-price on a single priced concept, extended with nullable min/max fields
  for the range case (schema.org `AggregateOffer`-style), which needs no migration to
  later add payment/SKU fields, versus (b) a small list of priced "tiers" per course
  (Open edX/Moodle-lite) if the range case really means "these are the tiers a learner
  can choose" rather than "the price varies for reasons TBD."

## References

- Open edX `course_modes` app: https://github.com/openedx/openedx-platform/blob/master/common/djangoapps/course_modes/models.py
- Open edX — Manage Course Fees: https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-cypress/running_course/manage_course_fees.html
- Moodle `enrol` table schema: https://moodleschema.zoola.io/tables/enrol.html
- Moodle enrolment plugin API: https://moodledev.io/docs/4.5/apis/plugintypes/enrol
- Moodle — Enrolment on payment: https://docs.moodle.org/501/en/Enrolment_on_payment
- LifterLMS `LLMS_Access_Plan` model source: https://github.com/gocodebox/lifterlms/blob/trunk/includes/models/model.llms.access.plan.php
- LifterLMS — Access Plan Options docs: https://lifterlms.com/docs/access-plan-options/
- LifterLMS — `is_on_sale()`: https://developer.lifterlms.com/reference/classes/llms_access_plan/is_on_sale/
- LearnDash — Course Enrollment Mode Settings: https://learndash.com/support/kb/core/settings/course-access/
- LearnDash — Display Regular/Sale Price snippet: https://developers.learndash.com/snippet/display-regular-price-sale-price-on-course-using-custom-fields/
- Tutor LMS — Subscriptions docs: https://docs.themeum.com/tutor-lms/subscriptions/
- Tutor LMS — Native ecommerce subscriptions: https://tutorlms.com/docs/native-ecommerce-subscriptions/
- Thinkific — Set Additional Prices: https://support.thinkific.com/hc/en-us/articles/360030721813-Set-Additional-Prices-For-Your-Products
- Thinkific — Create a Subscription Price: https://support.thinkific.com/hc/en-us/articles/360034692814-Create-a-Subscription-Price-for-Your-Product
- Teachable — Price your products: https://support.teachable.com/en/articles/11682476-price-your-products
- Kajabi — Free Trials & Flexible Payment Options: https://www.kajabi.com/blog/introducing-free-trials-flexible-payment-options
- WooCommerce — Variable Products documentation: https://woocommerce.com/document/variable-product/
- Canvas Catalog — course listing "Enrollment Fee": https://community.canvaslms.com/t5/Canvas-Catalog/How-do-I-add-a-course-listing-in-Canvas-Catalog/ta-p/1770
- schema.org `Offer`: https://schema.org/Offer
- schema.org `AggregateOffer`: https://schema.org/AggregateOffer
- Yoast — AggregateOffer schema piece: https://developer.yoast.com/features/schema/pieces/aggregateoffer/

status: ok
