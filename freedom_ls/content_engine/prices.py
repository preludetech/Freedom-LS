"""Price validation rules, formatting and the current-price computation.

Shared by ``Course.clean()`` (``freedom_ls/content_engine/models/courses.py``),
the content schema (``freedom_ls/content_engine/schema.py``) and the bundled
offline validator, so the rules live in exactly one place. ``courses.py``
calls into this module, and ``schema.py`` imports it, so this module must not
import ``freedom_ls.content_engine.models`` at module level -- that would
cycle. ``from __future__ import annotations`` defers every annotation to a
string, so nothing here is evaluated at import time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from babel.numbers import format_currency, get_currency_precision, list_currencies

from freedom_ls.form_engine.typed_answers import decimal_places_used

if TYPE_CHECKING:
    from freedom_ls.content_engine.models import PriceKind

# kind -> (fields the kind requires, fields it may also carry)
KIND_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "fixed": (frozenset({"amount"}), frozenset({"currency", "tax_note"})),
    "range": (
        frozenset({"low_amount", "high_amount"}),
        frozenset({"currency", "tax_note"}),
    ),
    "discounted": (
        frozenset({"amount", "sale_amount"}),
        frozenset({"sale_ends_on", "currency", "tax_note"}),
    ),
    "on_request": (frozenset(), frozenset()),
}

_AMOUNT_FIELDS = ("amount", "sale_amount", "low_amount", "high_amount")

# Mirror the Course price amount columns, so an amount that passes these rules
# is always stored exactly as written.
AMOUNT_MAX_DIGITS = 12
AMOUNT_DECIMAL_PLACES = 3


def price_errors(
    kind: str,
    *,
    amount: Decimal | None = None,
    sale_amount: Decimal | None = None,
    sale_ends_on: date | None = None,
    low_amount: Decimal | None = None,
    high_amount: Decimal | None = None,
    currency: str = "",
    tax_note: str = "",
) -> dict[str, str]:
    """Every price rule, keyed by the author-facing field name it belongs to.

    Currency is never required here -- each caller resolves a default
    currency before calling, and reports a still-missing currency itself.
    Rules run in order and a field keeps its first error only, so a field
    that is both stray for the kind and numerically invalid reports the
    stray message rather than being overwritten by the amount checks.
    """
    values: dict[str, object] = {
        "amount": amount,
        "sale_amount": sale_amount,
        "sale_ends_on": sale_ends_on,
        "low_amount": low_amount,
        "high_amount": high_amount,
        "currency": currency,
        "tax_note": tax_note,
    }
    required, optional = KIND_FIELDS[kind]
    allowed = required | optional
    errors: dict[str, str] = {}

    for field in required:
        if values[field] is None:
            errors.setdefault(field, f"{field} is required for a {kind} price")

    for field, value in values.items():
        if field in allowed or value in (None, ""):
            continue
        errors.setdefault(field, f"{field} is not used by a {kind} price")

    currency_valid = bool(currency) and currency in list_currencies()
    if currency and not currency_valid:
        errors.setdefault(
            "currency", f"{currency!r} is not a currency code Babel recognises."
        )

    # Collect the amounts that pass finiteness and positivity, so the
    # ordering rules below never compare against a NaN (which raises) or an
    # amount already reported invalid.
    finite_amounts: dict[str, Decimal] = {}
    for field in _AMOUNT_FIELDS:
        value = values[field]
        if not isinstance(value, Decimal):
            continue
        if not value.is_finite():
            errors.setdefault(field, f"{field} must be a finite number.")
            continue
        if value <= 0:
            errors.setdefault(field, f"{field} must be greater than zero.")
            continue
        if value >= Decimal(10) ** (AMOUNT_MAX_DIGITS - AMOUNT_DECIMAL_PLACES):
            errors.setdefault(field, f"{field} is too large.")
            continue
        if decimal_places_used(value) > AMOUNT_DECIMAL_PLACES:
            errors.setdefault(
                field,
                f"{field} can have at most {AMOUNT_DECIMAL_PLACES} decimal places.",
            )
            continue
        finite_amounts[field] = value
        if currency_valid and decimal_places_used(value) > get_currency_precision(
            currency
        ):
            errors.setdefault(
                field, f"{field} has more decimal places than {currency} allows."
            )

    if (
        "sale_amount" in finite_amounts
        and "amount" in finite_amounts
        and finite_amounts["sale_amount"] >= finite_amounts["amount"]
    ):
        errors.setdefault("sale_amount", "sale_amount must be less than amount.")
    if (
        "low_amount" in finite_amounts
        and "high_amount" in finite_amounts
        and finite_amounts["low_amount"] >= finite_amounts["high_amount"]
    ):
        errors.setdefault("high_amount", "high_amount must be greater than low_amount.")

    return errors


def price_locale() -> str:
    """The Babel locale prices are formatted in.

    ``PRICE_LOCALE`` when the project has set one, else the project's own
    ``LANGUAGE_CODE`` translated into Babel's locale spelling (``"en-us"``
    becomes ``"en_US"``). ``config`` and ``settings`` are imported inside the
    function, matching the rest of this module's lazy-import discipline.
    """
    from django.conf import settings
    from django.utils.translation import to_locale

    from freedom_ls.content_engine.config import config

    return config.PRICE_LOCALE or to_locale(settings.LANGUAGE_CODE)


def _quantized_amount(amount: Decimal, currency: str) -> str:
    """``amount`` as a decimal string at exactly ``currency``'s minor units.

    JSON-LD prices are exact decimal strings, never floats: a stored
    ``1499.000`` becomes ``"1499.00"`` in ZAR and ``"1500"`` in JPY. Nothing
    is rounded elsewhere -- this is the one place an amount's trailing
    zeros are normalised to the currency's own precision.
    """
    exponent = Decimal(1).scaleb(-get_currency_precision(currency))
    return str(amount.quantize(exponent))


@dataclass(frozen=True)
class CoursePrice:
    """The price a course shows today: currency resolved, sale expiry applied.

    ``CoursePrice`` never decides whether a sale has expired -- it trusts
    the ``kind`` and amounts it is given. ``Course.current_price()`` is
    where an expired discount is turned into a fixed price.
    """

    kind: PriceKind
    currency: str = ""
    amount: Decimal | None = None
    sale_amount: Decimal | None = None
    sale_ends_on: date | None = None
    low_amount: Decimal | None = None
    high_amount: Decimal | None = None
    tax_note: str = ""

    def _formatted(self, value: Decimal | None) -> str:
        if value is None:
            raise ValueError(f"This {self.kind} price has no amount to format.")
        return format_currency(value, self.currency, locale=price_locale())

    @property
    def formatted_amount(self) -> str:
        return self._formatted(self.amount)

    @property
    def formatted_sale_amount(self) -> str:
        return self._formatted(self.sale_amount)

    @property
    def formatted_low_amount(self) -> str:
        return self._formatted(self.low_amount)

    @property
    def formatted_high_amount(self) -> str:
        return self._formatted(self.high_amount)

    def offers_json_ld(self) -> dict[str, object] | None:
        """This price as schema.org ``Offer``/``AggregateOffer`` JSON-LD.

        ``None`` for ``on_request``, which names no amount to advertise.
        """
        if self.kind == "on_request":
            return None
        if self.kind == "range":
            if self.low_amount is None or self.high_amount is None:
                raise ValueError("A range price needs low_amount and high_amount.")
            return {
                "@type": "AggregateOffer",
                "lowPrice": _quantized_amount(self.low_amount, self.currency),
                "highPrice": _quantized_amount(self.high_amount, self.currency),
                "priceCurrency": self.currency,
            }
        if self.kind == "discounted":
            if self.sale_amount is None:
                raise ValueError("A discounted price needs a sale_amount.")
            offer: dict[str, object] = {
                "@type": "Offer",
                "price": _quantized_amount(self.sale_amount, self.currency),
                "priceCurrency": self.currency,
            }
            if self.sale_ends_on is not None:
                offer["priceValidUntil"] = self.sale_ends_on.isoformat()
            return offer
        if self.kind != "fixed":
            raise ValueError(f"Unknown price kind: {self.kind!r}")
        if self.amount is None:
            raise ValueError("A fixed price needs an amount.")
        return {
            "@type": "Offer",
            "price": _quantized_amount(self.amount, self.currency),
            "priceCurrency": self.currency,
        }
