"""Django system checks for the icons app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error, W = Warning. Checks run automatically on runserver, migrate,
test, and ``manage.py check``.

E001 — Unknown icon set name.
E002 — The active set's icons.json is missing: from the configured
       SEMANTIC_ICONS_ICONIFY_DIR when it is usable, otherwise from the bundled data.
E003 — Mapping value (base icon name) not found in Iconify JSON.
E004 — Variant-suffixed icon name not found in Iconify JSON.
E005 — Override key is not a valid semantic icon name.
E006 — Override icon name not found in Iconify JSON.
E007 — Mapping keys don't match SEMANTIC_ICON_NAMES.
E008 — SEMANTIC_ICONS_ICONIFY_DIR is not an absolute path to an existing directory.
W001 — Warn if commonly used variants (outline, solid) are unsupported.
W002 — FREEDOM_LS_ICON_SET is still set; use SEMANTIC_ICONS_SET.
W003 — FREEDOM_LS_ICON_OVERRIDES is still set; use SEMANTIC_ICONS_OVERRIDES.
W004 — FREEDOM_LS_ICON_BACKEND is still set; use SEMANTIC_ICONS_BACKEND.
"""

from django.core.checks import CheckMessage, Error, Warning, register

from freedom_ls.icons.config import DEPRECATED_SETTINGS, config, project_value
from freedom_ls.icons.loader import (
    BUNDLED_DATA_DIR,
    PACKAGE_MAP,
    set_file,
    usable_iconify_dir,
)
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


@register()
def check_iconify_dir(**kwargs: object) -> list[CheckMessage]:
    """E008: the configured directory is not an absolute path to an existing directory.

    Checked here rather than at render time: rendering falls back to bundled data, and
    `manage.py check --deploy` is where a deploy finds the mistake.
    """
    value = config.SEMANTIC_ICONS_ICONIFY_DIR
    if value is None or usable_iconify_dir() is not None:
        return []
    return [
        Error(
            f"SEMANTIC_ICONS_ICONIFY_DIR is {str(value)!r}, which is not an absolute "
            "path to an existing directory.",
            hint=(
                "Fix the path, or remove SEMANTIC_ICONS_ICONIFY_DIR to use the "
                "bundled icon data."
            ),
            id="icons.E008",
        )
    ]


@register()
def check_iconify_json_exists(**kwargs: object) -> list[CheckMessage]:
    """E001/E002: Check that the icon set is known and its JSON file exists."""
    icon_set_name: str = config.SEMANTIC_ICONS_SET
    pkg = PACKAGE_MAP.get(icon_set_name)
    if pkg is None:
        return [
            Error(
                f"Unknown icon set: {icon_set_name!r}",
                hint=f"Available sets: {sorted(PACKAGE_MAP)}",
                id="icons.E001",
            )
        ]

    if config.SEMANTIC_ICONS_ICONIFY_DIR is None:
        json_path = set_file(BUNDLED_DATA_DIR, icon_set_name)
    else:
        directory = usable_iconify_dir()
        if directory is None:
            return []  # E008 reports the directory
        json_path = set_file(directory, icon_set_name)

    if json_path.exists():
        return []
    return [
        Error(
            f"Iconify JSON file not found for icon set {icon_set_name!r}: {json_path}",
            hint=(
                "Set SEMANTIC_ICONS_ICONIFY_DIR to a directory laid out like "
                f"node_modules/@iconify-json, holding {pkg}/icons.json."
            ),
            id="icons.E002",
        )
    ]


@register()
def check_mapping_values_exist(**kwargs: object) -> list[CheckMessage]:
    """E003/E004: Check that every mapping value and variant-suffixed name exists."""
    errors: list[CheckMessage] = []
    icon_set_name: str = config.SEMANTIC_ICONS_SET
    if icon_set_name not in ICON_SETS:
        return errors  # E001 will catch this

    try:
        from freedom_ls.icons.loader import load_iconify_data

        data = load_iconify_data(icon_set_name)
    except (ValueError, FileNotFoundError):
        return errors  # E002 will catch this

    icons = data.get("icons", {})
    set_config = ICON_SETS[icon_set_name]
    for semantic_name, icon_name in set_config.mapping.items():
        if icon_name not in icons:
            errors.append(
                Error(
                    f"Mapping {semantic_name!r} -> {icon_name!r} not found in "
                    f"{icon_set_name!r} Iconify JSON",
                    id="icons.E003",
                )
            )
        else:
            for variant_name, suffix in set_config.variants.items():
                if suffix is not None:
                    lookup = icon_name + suffix
                    if lookup not in icons:
                        errors.append(
                            Error(
                                f"Variant {variant_name!r} of {semantic_name!r} -> "
                                f"{lookup!r} not found in {icon_set_name!r} Iconify JSON",
                                id="icons.E004",
                            )
                        )
    return errors


@register()
def check_overrides_exist(**kwargs: object) -> list[CheckMessage]:
    """E005/E006: Check that override icon names exist in the Iconify JSON data."""
    errors: list[CheckMessage] = []
    overrides: dict[str, str] = config.SEMANTIC_ICONS_OVERRIDES
    if not overrides:
        return errors

    icon_set_name: str = config.SEMANTIC_ICONS_SET
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
                    id="icons.E005",
                )
            )
        if icon_name not in icons:
            errors.append(
                Error(
                    f"Override {semantic_name!r} -> {icon_name!r} not found in "
                    f"{icon_set_name!r} Iconify JSON",
                    hint=(
                        "Pick a glyph in the active set's bundled data, or point "
                        "SEMANTIC_ICONS_ICONIFY_DIR at full data that has it."
                    ),
                    id="icons.E006",
                )
            )
    return errors


@register()
def check_mapping_keys(**kwargs: object) -> list[CheckMessage]:
    """E007: Check that every icon set mapping covers exactly SEMANTIC_ICON_NAMES."""
    errors: list[CheckMessage] = []
    for set_name, set_config in ICON_SETS.items():
        mapping_keys = set(set_config.mapping.keys())
        if mapping_keys != SEMANTIC_ICON_NAMES:
            missing = SEMANTIC_ICON_NAMES - mapping_keys
            extra = mapping_keys - SEMANTIC_ICON_NAMES
            errors.append(
                Error(
                    f"Icon set {set_name!r} mapping keys mismatch: "
                    f"missing={missing}, extra={extra}",
                    id="icons.E007",
                )
            )
    return errors


@register()
def check_variant_support(**kwargs: object) -> list[CheckMessage]:
    """W001: Warn if commonly used variants are not supported by the active icon set."""
    warnings: list[CheckMessage] = []
    icon_set_name: str = config.SEMANTIC_ICONS_SET
    if icon_set_name not in ICON_SETS:
        return warnings

    set_config = ICON_SETS[icon_set_name]
    common_variants = {"outline", "solid"}
    for variant in common_variants:
        if variant not in set_config.variants:
            warnings.append(
                Warning(
                    f"Variant {variant!r} is not supported by icon set {icon_set_name!r}",
                    hint=f"Available variants: {sorted(set_config.variants)}",
                    id="icons.W001",
                )
            )
    return warnings


# One id per old name, so a host can silence each one separately.
DEPRECATION_CHECK_IDS: dict[str, str] = {
    "FREEDOM_LS_ICON_SET": "icons.W002",
    "FREEDOM_LS_ICON_OVERRIDES": "icons.W003",
    "FREEDOM_LS_ICON_BACKEND": "icons.W004",
}


@register()
def check_deprecated_settings(**kwargs: object) -> list[CheckMessage]:
    """W002-W004: an old setting name is still set."""
    found: list[CheckMessage] = []
    for new_name, old_name in DEPRECATED_SETTINGS.items():
        if project_value(old_name) is None:
            continue
        check_id = DEPRECATION_CHECK_IDS[old_name]
        message = f"{old_name} is deprecated; use {new_name}."
        if project_value(new_name) is not None:
            message += f" {old_name} is ignored because {new_name} is set."
        found.append(
            Warning(
                message,
                hint=(
                    f"Rename the setting: {new_name} = <your value>. {old_name} is "
                    f"removed in the next tag. To silence this warning, add "
                    f"'{check_id}' to SILENCED_SYSTEM_CHECKS."
                ),
                id=check_id,
            )
        )
    return found
