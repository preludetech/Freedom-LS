"""Django system checks for the icons app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error, W = Warning. Checks run automatically on runserver, migrate,
test, and ``manage.py check``.

E001 — Unknown icon set name.
E002 — Iconify JSON file not found on disk.
E003 — Mapping value (base icon name) not found in Iconify JSON.
E004 — Variant-suffixed icon name not found in Iconify JSON.
E005 — Override key is not a valid semantic icon name.
E006 — Override icon name not found in Iconify JSON.
E007 — Mapping keys don't match SEMANTIC_ICON_NAMES.
W001 — Warn if commonly used variants (outline, solid) are unsupported.
"""

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning, register

from freedom_ls.icons.loader import PACKAGE_MAP, iconify_json_path
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


@register()
def check_iconify_json_exists(**kwargs: object) -> list[CheckMessage]:
    """E001/E002: Check that the icon set is known and its JSON file exists."""
    errors: list[CheckMessage] = []
    icon_set_name: str = getattr(settings, "FREEDOM_LS_ICON_SET", "heroicons")
    pkg = PACKAGE_MAP.get(icon_set_name)
    if pkg is None:
        errors.append(
            Error(
                f"Unknown icon set: {icon_set_name!r}",
                hint=f"Available sets: {sorted(PACKAGE_MAP)}",
                id="freedom_ls.E001",
            )
        )
        return errors

    json_path = iconify_json_path(pkg)
    if not json_path.exists():
        errors.append(
            Error(
                f"Iconify JSON file not found for icon set {icon_set_name!r}",
                hint=f"Run: npm install @iconify-json/{pkg}",
                id="freedom_ls.E002",
            )
        )
    return errors


@register()
def check_mapping_values_exist(**kwargs: object) -> list[CheckMessage]:
    """E003/E004: Check that every mapping value and variant-suffixed name exists."""
    errors: list[CheckMessage] = []
    icon_set_name: str = getattr(settings, "FREEDOM_LS_ICON_SET", "heroicons")
    if icon_set_name not in ICON_SETS:
        return errors  # E001 will catch this

    try:
        from freedom_ls.icons.loader import load_iconify_data

        data = load_iconify_data(icon_set_name)
    except (ValueError, FileNotFoundError):
        return errors  # E002 will catch this

    icons = data.get("icons", {})
    config = ICON_SETS[icon_set_name]
    for semantic_name, icon_name in config.mapping.items():
        if icon_name not in icons:
            errors.append(
                Error(
                    f"Mapping {semantic_name!r} -> {icon_name!r} not found in "
                    f"{icon_set_name!r} Iconify JSON",
                    id="freedom_ls.E003",
                )
            )
        else:
            for variant_name, suffix in config.variants.items():
                if suffix is not None:
                    lookup = icon_name + suffix
                    if lookup not in icons:
                        errors.append(
                            Error(
                                f"Variant {variant_name!r} of {semantic_name!r} -> "
                                f"{lookup!r} not found in {icon_set_name!r} Iconify JSON",
                                id="freedom_ls.E004",
                            )
                        )
    return errors


@register()
def check_overrides_exist(**kwargs: object) -> list[CheckMessage]:
    """E005/E006: Check that override icon names exist in the Iconify JSON data."""
    errors: list[CheckMessage] = []
    overrides: dict[str, str] = getattr(settings, "FREEDOM_LS_ICON_OVERRIDES", {})
    if not overrides:
        return errors

    icon_set_name: str = getattr(settings, "FREEDOM_LS_ICON_SET", "heroicons")
    try:
        from freedom_ls.icons.loader import load_iconify_data

        data = load_iconify_data(icon_set_name)
    except (ValueError, FileNotFoundError):
        return errors

    icons = data.get("icons", {})
    for semantic_name, icon_name in overrides.items():
        if semantic_name not in SEMANTIC_ICON_NAMES:
            errors.append(
                Error(
                    f"Override key {semantic_name!r} is not a valid semantic icon name",
                    id="freedom_ls.E005",
                )
            )
        if icon_name not in icons:
            errors.append(
                Error(
                    f"Override {semantic_name!r} -> {icon_name!r} not found in "
                    f"{icon_set_name!r} Iconify JSON",
                    id="freedom_ls.E006",
                )
            )
    return errors


@register()
def check_mapping_keys(**kwargs: object) -> list[CheckMessage]:
    """E007: Check that every icon set mapping covers exactly SEMANTIC_ICON_NAMES."""
    errors: list[CheckMessage] = []
    for set_name, config in ICON_SETS.items():
        mapping_keys = set(config.mapping.keys())
        if mapping_keys != SEMANTIC_ICON_NAMES:
            missing = SEMANTIC_ICON_NAMES - mapping_keys
            extra = mapping_keys - SEMANTIC_ICON_NAMES
            errors.append(
                Error(
                    f"Icon set {set_name!r} mapping keys mismatch: "
                    f"missing={missing}, extra={extra}",
                    id="freedom_ls.E007",
                )
            )
    return errors


@register()
def check_variant_support(**kwargs: object) -> list[CheckMessage]:
    """W001: Warn if commonly used variants are not supported by the active icon set."""
    warnings: list[CheckMessage] = []
    icon_set_name: str = getattr(settings, "FREEDOM_LS_ICON_SET", "heroicons")
    if icon_set_name not in ICON_SETS:
        return warnings

    config = ICON_SETS[icon_set_name]
    common_variants = {"outline", "solid"}
    for variant in common_variants:
        if variant not in config.variants:
            warnings.append(
                Warning(
                    f"Variant {variant!r} is not supported by icon set {icon_set_name!r}",
                    hint=f"Available variants: {sorted(config.variants)}",
                    id="freedom_ls.W001",
                )
            )
    return warnings
