"""Shared builders for the registration rule tests."""

from __future__ import annotations

from freedom_ls.registration_rules.models import (
    AttributeRuleConditions,
    RegistrationRule,
)


def change_payload(
    rule: RegistrationRule, *, is_enabled: bool = False, **inline: object
) -> dict[str, object]:
    """A change-page POST as a browser sends it.

    `inline` holds the conditions form's values; any picker or date left out is
    submitted empty. A rule that already has a conditions row posts it as an
    initial form, so the formset updates that row instead of adding a second.
    """
    stored = AttributeRuleConditions.objects.filter(rule=rule).first()
    data: dict[str, object] = {
        "name": rule.name,
        "attribute_conditions-TOTAL_FORMS": "1",
        "attribute_conditions-INITIAL_FORMS": "0" if stored is None else "1",
        "attribute_conditions-MIN_NUM_FORMS": "0",
        "attribute_conditions-MAX_NUM_FORMS": "1",
        "_save": "Save",
    }
    if is_enabled:
        data["is_enabled"] = "on"
    if stored is not None:
        data["attribute_conditions-0-id"] = str(stored.pk)
        data["attribute_conditions-0-rule"] = str(rule.pk)
    data.update(
        {f"attribute_conditions-0-{key}": value for key, value in inline.items()}
    )
    return data
