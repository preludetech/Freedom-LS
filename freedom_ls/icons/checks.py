from pathlib import Path

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning, register

from freedom_ls.icons.loader import PACKAGE_MAP
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


@register()
def check_iconify_json_exists(**kwargs: object) -> list[CheckMessage]:
    """E001: Check that the Iconify JSON file exists for the active icon set."""
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

    json_path = (
        Path(settings.BASE_DIR) / "node_modules" / f"@iconify-json/{pkg}" / "icons.json"
    )
    if not json_path.exists():
        errors.append(
            Error(
                f"Iconify JSON file not found for icon set {icon_set_name!r}",
                hint=f"Run: npm install @iconify-json/{pkg}",
                id="freedom_ls.E001",
            )
        )
    return errors


@register()
def check_mapping_values_exist(**kwargs: object) -> list[CheckMessage]:
    """E002: Check that every mapping value exists in the Iconify JSON data."""
    errors: list[CheckMessage] = []
    icon_set_name: str = getattr(settings, "FREEDOM_LS_ICON_SET", "heroicons")
    if icon_set_name not in ICON_SETS:
        return errors  # E001 will catch this

    try:
        from freedom_ls.icons.loader import load_iconify_data

        data = load_iconify_data(icon_set_name)
    except (ValueError, FileNotFoundError):
        return errors  # E001 will catch this

    icons = data.get("icons", {})
    config = ICON_SETS[icon_set_name]
    for semantic_name, icon_name in config.mapping.items():
        if icon_name not in icons:
            errors.append(
                Error(
                    f"Mapping {semantic_name!r} -> {icon_name!r} not found in "
                    f"{icon_set_name!r} Iconify JSON",
                    id="freedom_ls.E002",
                )
            )
    return errors


@register()
def check_overrides_exist(**kwargs: object) -> list[CheckMessage]:
    """E003: Check that override icon names exist in the Iconify JSON data."""
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
                    id="freedom_ls.E003",
                )
            )
        if icon_name not in icons:
            errors.append(
                Error(
                    f"Override {semantic_name!r} -> {icon_name!r} not found in "
                    f"{icon_set_name!r} Iconify JSON",
                    id="freedom_ls.E003",
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
