# Research: Storing and formatting money in Django (for course-prices)

Scope: how to store/validate/display course prices (fixed, ranged, discounted) in FLS.
Payment processing is explicitly out of scope for this feature, but the storage choice
should not block wiring Stripe/Paddle in later.

## TL;DR recommendation

- **Store amounts as `models.DecimalField(max_digits=10, decimal_places=2)`**, not integer
  minor units ("cents"). FLS is not doing arithmetic/settlement yet — it is *displaying* a
  price a human typed into content or an admin form. Decimal keeps the authored value
  (`"499.00"`, `"1499.99"`) exact and human-readable in the DB and admin, and Django's
  `DecimalField` already avoids the float-precision problem that minor-units storage exists
  to solve. Convert to Stripe/Paddle's integer-minor-unit representation **at the payment
  integration boundary**, not in the domain model (see "Stripe/Paddle" section below).
- **Do not add django-money.** It does not yet advertise Django 6 support (latest release
  3.6.1, classifiers list Django 4.2/5.0/5.1/5.2 only — see below), and this feature does not
  need multi-currency arithmetic (`Money + Money`), currency-aware `ExchangeBackend`, or
  `MoneyField` query lookups — it needs "store an amount, a currency, and a display type,
  then render it." A plain `DecimalField` + `CharField` (ISO 4217 code) pair, validated by a
  small helper (mirroring the pattern already used in `form_engine/typed_answers.py`), gets
  the same correctness with zero new runtime dependency and no risk of blocking on upstream
  Django-6 support.
- **Currency should be per-course (defaulting from a per-app setting), not per-Site as a DB
  field** — `django.contrib.sites.Site` is used unmodified in this repo (no `SiteProfile`
  extension model exists), so there is nowhere on `Site` to hang a currency today. Add
  `DEFAULT_CURRENCY` as a new declared setting (following the existing
  `freedom_ls/*/config.py` + `AppSettings` pattern), and let each `Course` optionally
  override it. This is consistent with `Course.difficulty`, `Course.visibility`, etc., which
  are all per-course with a project-wide fallback pattern.
- **Author prices in YAML as quoted strings** (`price: "499.00"`), not bare YAML numbers,
  and parse them to `Decimal` in the pydantic schema with the same
  regex-then-`Decimal(text)` approach `form_engine/typed_answers.py` already uses for
  question `min`/`max` bounds. Bare YAML floats (`price: 499.00`) round-trip through
  IEEE-754 binary floats and are exactly the failure mode Decimal exists to avoid.
- **Babel is not a dependency of this repo today** (only unrelated hit in a `spec_dd`
  design-sketch JS file). Django's own `l10n`/`USE_THOUSAND_SEPARATOR` machinery formats
  *numbers*, not *currency* (no currency symbol, no per-currency decimal-place rule). If
  locale-correct currency rendering (`$1,499.00` vs `1.499,00 €` vs `¥1,499`) is wanted,
  Babel's `babel.numbers.format_currency` is the standard tool and is a small, mature,
  actively-maintained dependency — but it is an *additional* decision, separate from the
  storage decision, and should be scoped explicitly if the idea's "display it appropriately"
  is read to include locale formatting rather than just "show the number and currency".

---

## 1. DecimalField vs integer minor units ("cents")

**`DecimalField` (fixed-point, base-10)**
- Django's `DecimalField` maps to PostgreSQL `numeric(max_digits, decimal_places)`, which is
  exact base-10 arithmetic — no binary-float rounding error. This is Django's own documented
  reason `DecimalField` exists for money: see the `FloatField` docs warning that `FloatField`
  "results may not always be predictable" for anything money-adjacent, and the general
  Python/Django community guidance to always use `Decimal`, never `float`, for money.
- Values in the DB and admin read naturally (`499.00`), which matters here because prices
  are also hand-authored in course YAML front matter and reviewed by educators, not only
  read by payment code.
- Requires picking `max_digits`/`decimal_places` up front. `decimal_places=2` is wrong for
  3-decimal currencies (KWD, BHD, JOD — see ISO 4217 section) and wrong-but-harmless for
  0-decimal currencies (JPY) if you don't also enforce "no cents" at the currency level.

**Integer minor units ("store 4990 for $49.90")**
- The classic recommendation for *systems that do money arithmetic/settlement* (ledger
  systems, payment processors) because integers have no rounding ambiguity under
  addition/subtraction and match how card networks and processors bill (see Stripe/Paddle
  section). Martin Fowler's "Money" pattern and countless "How to store currency in a
  database" posts recommend integer cents specifically for these arithmetic-heavy contexts.
- Costs: every currency's minor-unit exponent must be tracked (2 for most, 0 for JPY, 3 for
  KWD) and applied consistently at every point amounts are read/displayed/summed. Values are
  opaque in the DB/admin (`4990` needs a human to remember "divide by 100... unless it's
  JPY").
- FLS is not doing settlement in this feature — it just needs to *store and show* a number a
  human decided on. There's no summation, no rounding-then-re-summing, no ledger
  reconciliation risk that integer minor units are designed to prevent. `DecimalField` gives
  the same "no float rounding error" guarantee with a representation that is directly what
  a course author typed and what a learner reads.

**Recommendation:** `DecimalField(max_digits=10, decimal_places=2)` per price field, with the
`decimal_places` value itself possibly needing to become currency-aware later (see below) if
JOD/KWD-style courses are ever priced in their local currency — flagged as a known limitation
rather than solved now, since "payment processing is out of scope" and the idea only mentions
prices being shown, not charged.

Sources:
- https://docs.djangoproject.com/en/6.0/ref/models/fields/#decimalfield
- https://docs.djangoproject.com/en/6.0/ref/models/fields/#floatfield
- https://martinfowler.com/eaaCatalog/money.html

## 2. ISO 4217 currency codes and minor-unit exceptions

ISO 4217 assigns every currency a 3-letter code (`USD`, `ZAR`, `EUR`...) and a "minor unit"
exponent — how many decimal digits the currency's smallest denomination represents:

- **Exponent 2 (the default almost every UI/library assumes):** USD, EUR, GBP, ZAR, AUD, CAD,
  NZD, and most others.
- **Exponent 0 (no minor unit / no decimals in normal use):** JPY (Japanese Yen), KRW (South
  Korean Won), VND, ISK, and others — a price of "1500" JPY means ¥1500, not ¥15.00.
- **Exponent 3 (three decimal places):** KWD (Kuwaiti Dinar), BHD (Bahraini Dinar), JOD
  (Jordanian Dinar), OMR, TND, IQD, LYD.

If FLS ever needs to correctly price a course in JPY or KWD, a fixed `decimal_places=2`
column will either lose precision (KWD: "19.995" truncated) or display two spurious zero
digits (JPY: "1500.00" instead of "¥1500"). Two ways to handle this later without touching
storage now:
1. Keep `decimal_places=2` at the DB layer (it's just how many digits `numeric` reserves)
   and do currency-aware **rounding/display** in the presentation layer (round KWD to 3dp
   before display would need decimal_places=3 in the column; simplest is to pick a
   `decimal_places` large enough for the exceptions, e.g. 3, and let 2-decimal currencies
   simply always have a trailing zero — Postgres `numeric(10,3)` stores `19.99` fine).
2. Or maintain a small `CURRENCY_MINOR_UNITS: dict[str, int]` constant (mirrors what
   Stripe/`zero-decimal-currencies` packages ship) and use it only for *display* rounding,
   independent of the DB's `decimal_places`.

Given the idea only needs display for now, **note this as a known edge case in the spec**
rather than build full multi-currency-precision support pre-emptively (`Don't build
functionality that is not explicitly requested` — CLAUDE.md) — but do not hardcode "always 2
decimal places" so deeply that it can't be revisited.

Sources:
- https://en.wikipedia.org/wiki/ISO_4217
- https://www.iso.org/iso-4217-currency-codes.html
- https://docs.stripe.com/currencies (zero-decimal currency list, reused ISO 4217 minor units)

## 3. django-money vs plain DecimalField + CharField

**What django-money adds:** a `MoneyField` (a `DecimalField` + a paired currency `CharField`
bundled as one model field), a `Money` value object (`django_money.money.Money`) supporting
`Money(10, 'USD') + Money(5, 'USD')` arithmetic with currency-mismatch errors, Django admin
integration, form fields, template tags, and optional exchange-rate backends
(`django-money[exchange]`) for cross-currency conversion.

**Maintenance/compatibility status (checked 2026-09-18):**
- Latest release: **3.6.1**, released 2026-06-07 — actively maintained, healthy release
  cadence.
- PyPI classifiers list supported Django versions as **4.2, 5.0, 5.1, 5.2**. There is
  **no Django 6 classifier**, and no changelog/issue found confirming Django 6 support.
  This repo pins `django>=6.0.4,<6.1` (pyproject.toml) — adding django-money today means
  either running an unsupported combination or waiting on upstream to certify Django 6.
- Requires Python >=3.10 (fine — repo requires >=3.13).

**Cost of the dependency for this feature specifically:**
- The idea needs: a fixed price, OR a range (X–Y), OR a discounted price (regular + sale),
  displayed per course. None of that needs `Money` arithmetic, cross-currency conversion, or
  MoneyField's custom manager/lookup machinery (`Model.objects.filter(price__gt=Money(...))`).
  It needs two or three `DecimalField`s (regular/sale, or low/high) plus one currency code
  per course, and a `field_validator`/`clean()` that says "sale < regular" or "low < high" —
  well within plain Django.
- A new dependency also mypy/django-stubs support risk (`mypy_django_plugin` is already
  configured in pyproject.toml and django-money has historically lagged on stub coverage),
  and this repo explicitly tracks third-party stub gaps in `[[tool.mypy.overrides]]` (e.g.
  `allauth.*`, `weasyprint.*` are already `ignore_missing_imports`) — one more line of upkeep
  for a dependency whose main value (currency arithmetic) is unused here.
- If/when actual multi-currency *charging* is built (Stripe/Paddle), the integration itself
  will most likely deal in minor-unit integers per processor's own SDK, not `Money` objects,
  so django-money doesn't even remove work at that later step — it would need to be converted
  at the boundary either way.

**Recommendation:** do not add django-money for this feature. Use `DecimalField` +
`CharField(max_length=3)` (ISO 4217 code) directly on `Course` (or a small related model, see
below), validated by plain Django/pydantic validators. Revisit only if a future feature
genuinely needs `Money` arithmetic or multi-currency conversion across many call sites.

Sources:
- https://pypi.org/project/django-money/
- https://github.com/django-money/django-money
- https://django-money.readthedocs.io/en/latest/changes.html

## 4. Per-site vs per-course currency

Checked `freedom_ls/site_aware_models/models.py`: `Site` is Django's stock
`django.contrib.sites.models.Site` — **not subclassed or extended** with a profile model in
this repo (`grep` for `SiteProfile`/`OneToOneField(Site` found nothing outside test/QA
fixtures). Every content model (`Course`, `CourseCategory`, ...) carries its own
`site = models.ForeignKey(Site, on_delete=models.PROTECT)` via `SiteAwareModelBase`
(`freedom_ls/site_aware_models/models.py:131-134`), and `SiteAwareManager` filters querysets
by the current request's resolved site (`get_cached_site`, same file).

Because there's no DB-level place to store "this site's currency" today, and because this
deployment pattern is "one Django process/settings.py serving multiple `Site` rows", a
**project-wide `DEFAULT_CURRENCY` Django setting** (via the existing `AppSettings` pattern —
see `freedom_ls/base/app_settings.py`, `freedom_ls/content_engine/config.py`,
`freedom_ls/site_aware_models/config.py` for the established shape) is the right default —
it matches how `FORCE_SITE_NAME`, `HEADER_TITLE`, etc. already work as global,
settings.py-level knobs alongside true per-`Site` DB data.

Layered with a **per-course override** (a `currency` field on `Course`, defaulting to
`config.DEFAULT_CURRENCY` at creation), this mirrors the existing `Course.difficulty` /
`Course.visibility` pattern exactly: a project-wide sensible default, overridable per course.
If a genuinely separate currency per `Site` (not just per course) is needed later, that is a
bigger change (introducing a `SiteProfile`-style extension model) and should be its own
ticket — flag it as a known gap rather than build it speculatively now.

Suggested new setting (in a `course_prices`/`content_engine` `config.py`, following the exact
shape of `ContentEngineConfig`):

```python
class ContentEngineConfig(AppSettings):
    ...
    DEFAULT_CURRENCY: str

    declared_settings = {
        ...
        # ISO 4217 code, e.g. "USD", "ZAR". No safe built-in default — a
        # deployment must say what it prices in.
        "DEFAULT_CURRENCY": Setting(required=True),
    }
```

## 5. Locale-aware formatting: Babel vs Django's own l10n

**Checked repo:** `grep -ri babel` across the repo found **one** hit, an unrelated
third-party `support.js` file under `spec_dd/1. next/.../support.js` (a design sketch, not
project code). **Babel is not currently a dependency** (absent from `pyproject.toml`).

**Django's built-in `l10n`:** `LANGUAGE_CODE = "en-us"`, `USE_I18N = True`, `USE_TZ = True`
are set in `config/settings_base.py:236-242`; `USE_L10N` isn't set (it was removed/always-on
from Django 5 onward) and `USE_THOUSAND_SEPARATOR` is **not currently set** anywhere in
`config/`. `USE_THOUSAND_SEPARATOR = True` turns on locale-aware grouping separators for
plain numbers (e.g. `1,499` vs `1499`) via `django.utils.numberformat` / the `intcomma`-style
formatting Django applies automatically to model/form field output when localization is
active — but this is **number** formatting, not **currency** formatting: Django has no
built-in concept of a currency symbol, no per-currency decimal-place rule, and no
locale-vs-currency disambiguation (see next section). Confirmed against the Django 6.0 i18n
formatting docs.

**Babel's `babel.numbers.format_currency`** is the standard library for the currency-specific
part: given an amount, an ISO 4217 code, and a locale, it renders the locale-correct symbol
position, decimal separator, grouping, and (importantly) the currency's correct number of
decimal digits (0 for JPY, 3 for KWD, 2 otherwise) using CLDR data — solving the ISO 4217
minor-unit problem in section 2 as a side effect of correct locale formatting.

**Recommendation:** for *this* feature, "display it appropriately" most plausibly means
"show the number with its currency clearly (e.g. `$499.00` / `R499.00 – R899.00` / `~~$99~~
$49`)" rather than full locale-negotiated formatting per learner's browser locale — the repo
has one `LANGUAGE_CODE` ("en-us") and no existing i18n-of-numbers infrastructure switched on
(`USE_THOUSAND_SEPARATOR` isn't set). Build a small, explicit formatter
(`format_price(amount, currency) -> str`, e.g. `f"{symbol}{amount:,.2f}"` keyed by a small
symbol map) rather than pulling in Babel for one call site. If/when the project takes on
genuine multi-locale rendering, add Babel then — it's a lightweight (`pip install babel`),
mature, widely-used dependency (used internally by Flask-Babel, Django itself vendors CLDR
data for its own i18n) and would be a reasonable, low-risk addition at that point.

Sources:
- https://docs.djangoproject.com/en/6.0/topics/i18n/formatting/
- https://babel.pocoo.org/en/latest/api/numbers.html
- https://babel.pocoo.org/en/latest/locale.html

## 6. Currency symbols are ambiguous

`$` is used by USD, AUD, NZD, CAD, HKD, SGD, MXN and others; `R` is used by ZAR (South
African Rand) but is also mistakable for BRL's "R$" prefix. Babel's own docs/issue tracker
confirm this is a known, intentionally-unsolved problem: `format_currency` disambiguates by
*locale*, not by symbol alone — e.g. `format_currency(10.50, 'USD', locale='en_AU')` renders
`"US$10.50"` (prefixing `US` because the `en_AU` locale's own currency, AUD, also uses `$`).
There is no reliable symbol-to-code reverse mapping (a GitHub feature request for "$" → "USD"
parsing remains open/unresolved).

**Implication for FLS:** never store or key anything by a bare symbol. Always store the ISO
4217 **code** (`"USD"`, `"ZAR"`) as the source of truth, and only derive a symbol for
*display*, with an explicit fallback to showing the code when a symbol would be ambiguous in
context (e.g. a multi-currency admin list should probably show `R 499.00 ZAR` rather than
bare `R499.00`, or use Babel's locale-aware disambiguating prefix as above).

Sources:
- https://github.com/python-babel/babel/issues/141
- https://babel.pocoo.org/en/latest/api/numbers.html

## 7. Validation rules

For the three price shapes in the idea (fixed, range, discounted), validate:
- **Non-negative:** `price >= 0` (a `MinValueValidator(0)` on the `DecimalField`, or a
  pydantic `Field(ge=0)` / `field_validator` in the YAML schema).
- **Discounted price < regular price:** `sale_price < regular_price` (strictly less — equal
  isn't a discount) — a `model_validator(mode="after")` in pydantic and a `clean()` on the
  Django model, mirroring exactly how `Course._validate_icon_fields` and
  `FormQuestion.clean()` (`question_bounds_error`) already re-validate the same rule on both
  the content-authoring side and the admin side in this codebase.
- **Range low < high:** `price_low < price_high` (or `<=` if a single-value "range" of equal
  bounds should be allowed — decide explicitly; recommend strict `<` and let a single price
  use the "fixed" shape instead, avoiding two ways to express the same thing).
- **Currency code validity:** the stored `currency` string should validate against a known
  ISO 4217 code list (or an explicit application-level allow-list scoped to currencies FLS
  actually supports) rather than accepting arbitrary text — mirrors how `slug` fields in this
  codebase validate against `SLUG_PATTERN` rather than accepting free text
  (`content_engine/schema.py:36`).
- **decimal_places consistency:** if `decimal_places=2` is fixed at the DB layer (section 1),
  validate that an authored amount doesn't imply more precision than the column allows —
  exactly the `decimal_places_used(value) > decimal_places` check already implemented in
  `freedom_ls/form_engine/typed_answers.py:225` for question bounds. That helper (and its
  sibling `parsed_number`) is a directly reusable pattern (not necessarily reusable code,
  since it's form-engine-specific) for a price parser.
- **Exactly one shape populated:** if fixed/range/discounted are modeled as one row with
  optional fields rather than a discriminated union, validate that the fields for exactly one
  "shape" are set (e.g. reject a row with both `price_low`/`price_high` *and*
  `sale_price` populated) — a `model_validator(mode="after")` analogous to
  `CourseCategories._validate_entries`'s multi-field cross-checks.

## 8. How Stripe and Paddle represent amounts (future-proofing)

- **Stripe:** amounts are a **positive integer in the currency's smallest unit** — e.g. `1099`
  for $10.99 USD, but `10` for ¥10 JPY (a "zero-decimal currency", since JPY has no minor
  unit). Stripe publishes and maintains the zero-decimal-currency list; three-decimal
  currencies like KWD are handled by Stripe's own currency-specific rounding rules at the API
  boundary.
- **Paddle (Billing API):** the `amount` on a `Price` object is a **string** holding the
  integer count of the currency's smallest unit (e.g. `"500"` for $5.00), not a JSON number —
  Paddle documents this explicitly to avoid floating-point serialization surprises in
  JSON-based API clients.

**Implication:** both processors want integer minor units, not decimals, and Stripe wants
that integer computed with a currency-aware exponent (0/2/3), not a flat "×100". Whatever
FLS's later payments feature looks like, it will need a `to_minor_units(amount: Decimal,
currency: str) -> int` conversion at the API boundary regardless of how the price is stored
internally today — so storing `DecimalField` now doesn't cost anything at that point; it's the
same conversion step django-money's `Money` object would also have needed to go through
before calling Stripe/Paddle. This confirms `DecimalField` now does not block payments later.

Sources:
- https://docs.stripe.com/api/charges/object
- https://docs.stripe.com/currencies
- https://developer.paddle.com/api-reference/prices/create-price/
- https://developer.paddle.com/api-reference/prices/overview

## 9. Repo-specific findings (grep results)

- **`pyproject.toml` dependencies:** no `babel`, no `django-money`, no money/currency package
  of any kind currently listed (`/home/sheena/workspace/lms/freedom-ls-worktrees/course-prices/pyproject.toml`).
- **`grep -ri "price|currency|Decimal|money"` across `freedom_ls/`:** no existing
  price/currency/Money code anywhere in the app. `DecimalField` itself is not used anywhere
  yet in the codebase (`grep DecimalField freedom_ls` → no matches) — this feature would be
  the first use of `DecimalField` in FLS, so there's no existing convention to conflict with,
  but also no precedent to copy directly beyond the `Decimal`-via-string pattern in
  `form_engine/typed_answers.py` (uses `Decimal` for parsed numeric answers, stored as
  `CharField` text with app-level parsing — a workable secondary reference for
  “store the authored text, parse to Decimal, validate” even though model-level `DecimalField`
  wasn't used there).
- **Settings (`config/settings_base.py`):** `LANGUAGE_CODE = "en-us"` (line 236),
  `USE_I18N = True` (line 240), `USE_TZ = True` (line 242). No `USE_L10N` (removed/implied
  True since Django 5) and **no `USE_THOUSAND_SEPARATOR`** set anywhere under `config/`.
- **Per-app settings pattern confirmed:** `freedom_ls/base/app_settings.py` defines a generic
  `AppSettings`/`Setting(default=..., required=...)` base; every app (`content_engine`,
  `site_aware_models`, `accounts`, `learner_management`, etc.) has its own `config.py`
  subclassing it, e.g. `freedom_ls/content_engine/config.py`'s `ContentEngineConfig`. A new
  `DEFAULT_CURRENCY` setting should follow this exact shape (see section 4).
- **`Course` model** (`freedom_ls/content_engine/models/courses.py`): is a `SiteAwareModel` +
  `MarkdownContent`/`TitledContent`, already carries per-course enum-like fields
  (`difficulty`, `visibility` as `models.TextChoices` + `CharField(choices=...)`) with
  project-wide defaults — the price/currency fields should follow this same shape (plain
  fields directly on `Course`, or a small related model if "range vs fixed vs discounted" is
  modeled as a discriminated union rather than nullable columns on `Course` itself — a
  modeling decision for the design doc, not this research).
- **Pydantic content schema** (`freedom_ls/content_engine/schema.py`): the `Course` pydantic
  model (mirrors the Django model, validated at content-load time from YAML front matter) is
  the place a `price`/`price_low`/`price_high`/`sale_price`/`currency` set of fields would be
  added, with `model_validator(mode="after")` cross-field checks exactly like
  `_validate_icon_fields` and `CourseCategories._validate_entries` already do. Note `Course`
  uses `model_config = ConfigDict(extra="forbid", use_enum_values=True)` — any new
  currency/price-shape enum should also use `use_enum_values=True` for consistency.
- **YAML float-precision risk:** nothing in the repo currently guards against this because no
  numeric-money field exists yet, but the closest analog
  (`form_engine`'s question `min`/`max`) is stored and authored as **quoted strings**, not
  bare YAML numbers, precisely to keep parsing under application control
  (`typed_answers.parsed_number` does `Decimal(text)` from a regex-validated string — never
  `float(text)` or a bare YAML-parsed number). The same approach is recommended for
  `price:` fields in course YAML: author `price: "499.00"` (or `price: 499` for a whole-number
  price, since bare YAML integers parse exactly, only YAML floats are the hazard), and validate
  with a `field_validator(mode="before")` that accepts `str | int` and rejects/converts a
  `float` explicitly (raise a clear error telling the author to quote the value) before
  constructing the `Decimal`.

---

## Suggested concrete shape (for the design doc to refine, not a final decision)

```python
# freedom_ls/content_engine/models/courses.py (sketch)
class PriceType(models.TextChoices):
    FIXED = "fixed", _("Fixed price")
    RANGE = "range", _("Price range")
    DISCOUNTED = "discounted", _("Discounted price")

class Course(MarkdownContent, TitledContent):
    ...
    price_type = models.CharField(max_length=20, choices=PriceType.choices, blank=True, default="")
    currency = models.CharField(max_length=3, blank=True, default="")  # ISO 4217; "" = use DEFAULT_CURRENCY
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)        # FIXED
    price_low = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)     # RANGE
    price_high = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)    # RANGE
    price_regular = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # DISCOUNTED
    price_sale = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)    # DISCOUNTED
```

with a `clean()`/pydantic `model_validator` enforcing: exactly the fields for `price_type`
are populated; all amounts `>= 0`; `price_low < price_high`; `price_sale < price_regular`;
`currency` (or the resolved `DEFAULT_CURRENCY`) is a recognised ISO 4217 code. This is a
sketch for the design phase to accept/reject/refine — not a final schema.

---

status: ok
