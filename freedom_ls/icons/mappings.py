from dataclasses import dataclass

from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


@dataclass(frozen=True)
class IconSetConfig:
    mapping: dict[str, str]
    variants: dict[str, str | None]


HEROICONS_MAPPING: dict[str, str] = {
    "next": "arrow-right",
    "previous": "arrow-left",
    "home": "home",
    "expand": "chevron-down",
    "collapse": "chevron-right",
    "menu_open": "chevron-right",
    "menu_close": "chevron-left",
    "dropdown": "chevron-down",
    "success": "check-circle",
    "error": "x-circle",
    "warning": "exclamation-triangle",
    "info": "information-circle",
    "in_progress": "play",
    "complete": "check",
    "locked": "lock-closed",
    "not_started": "minus",
    "repeatable": "arrow-path",
    "check": "check",
    "close": "x-mark",
    "retry": "arrow-path",
    "download": "arrow-down-tray",
    "more_options": "ellipsis-vertical",
    "settings": "cog-6-tooth",
    "reading": "book-open",
    "quiz": "pencil-square",
    "assessment": "academic-cap",
    "section": "folder",
    "user": "user",
    "notifications": "bell",
    "achievement": "trophy",
    "loading": "arrow-path",
    "sort_asc": "chevron-up",
    "sort_desc": "chevron-down",
    "sort_neutral": "bars-arrow-down",
    "boolean_true": "check",
    "boolean_false": "x-mark",
    "deadline": "clock",
    "deadline_override": "clock",
    "sentiment_good": "hand-thumb-up",
    "sentiment_bad": "hand-thumb-down",
    "unknown": "question-mark-circle",
    "star": "star",
    "notes": "document-text",
}

LUCIDE_MAPPING: dict[str, str] = {
    "next": "arrow-right",
    "previous": "arrow-left",
    "home": "house",
    "expand": "chevron-down",
    "collapse": "chevron-right",
    "menu_open": "chevron-right",
    "menu_close": "chevron-left",
    "dropdown": "chevron-down",
    "success": "circle-check",
    "error": "circle-x",
    "warning": "triangle-alert",
    "info": "info",
    "in_progress": "play",
    "complete": "check",
    "locked": "lock",
    "not_started": "minus",
    "repeatable": "repeat",
    "check": "check",
    "close": "x",
    "retry": "repeat",
    "download": "download",
    "more_options": "ellipsis-vertical",
    "settings": "settings",
    "reading": "book-open",
    "quiz": "pencil",
    "assessment": "graduation-cap",
    "section": "folder",
    "user": "user",
    "notifications": "bell",
    "achievement": "trophy",
    "loading": "loader",
    "sort_asc": "chevron-up",
    "sort_desc": "chevron-down",
    "sort_neutral": "arrow-down-up",
    "boolean_true": "check",
    "boolean_false": "x",
    "deadline": "clock",
    "deadline_override": "clock",
    "sentiment_good": "thumbs-up",
    "sentiment_bad": "thumbs-down",
    "unknown": "circle-question-mark",
    "star": "star",
    "notes": "file-text",
}

TABLER_MAPPING: dict[str, str] = {
    "next": "arrow-right",
    "previous": "arrow-left",
    "home": "home",
    "expand": "chevron-down",
    "collapse": "chevron-right",
    "menu_open": "chevron-right",
    "menu_close": "chevron-left",
    "dropdown": "chevron-down",
    "success": "circle-check",
    "error": "circle-x",
    "warning": "alert-triangle",
    "info": "info-circle",
    "in_progress": "play",
    "complete": "check",
    "locked": "lock",
    "not_started": "minus",
    "repeatable": "repeat",
    "check": "check",
    "close": "x-mark",
    "retry": "repeat",
    "download": "download",
    "more_options": "dots-vertical",
    "settings": "settings",
    "reading": "book",
    "quiz": "pencil",
    "assessment": "school",
    "section": "folder",
    "user": "user",
    "notifications": "bell",
    "achievement": "trophy",
    "loading": "loader",
    "sort_asc": "chevron-up",
    "sort_desc": "chevron-down",
    "sort_neutral": "arrows-sort",
    "boolean_true": "check",
    "boolean_false": "x-mark",
    "deadline": "clock",
    "deadline_override": "clock",
    "sentiment_good": "thumb-up",
    "sentiment_bad": "thumb-down",
    "unknown": "help-circle",
    "star": "star",
    "notes": "file-text",
}

PHOSPHOR_MAPPING: dict[str, str] = {
    "next": "arrow-right",
    "previous": "arrow-left",
    "home": "house",
    "expand": "caret-down",
    "collapse": "caret-right",
    "menu_open": "list",
    "menu_close": "caret-left",
    "dropdown": "caret-down",
    "success": "check-circle",
    "error": "x-circle",
    "warning": "warning",
    "info": "info",
    "in_progress": "play",
    "complete": "check",
    "locked": "lock",
    "not_started": "minus",
    "repeatable": "repeat",
    "check": "check",
    "close": "x",
    "retry": "repeat",
    "download": "download",
    "more_options": "dots-three-vertical",
    "settings": "gear",
    "reading": "book-open",
    "quiz": "pencil",
    "assessment": "graduation-cap",
    "section": "folder",
    "user": "user",
    "notifications": "bell",
    "achievement": "trophy",
    "loading": "spinner",
    "sort_asc": "arrow-up",
    "sort_desc": "arrow-down",
    "sort_neutral": "arrows-down-up",
    "boolean_true": "check",
    "boolean_false": "x",
    "deadline": "clock",
    "deadline_override": "clock",
    "sentiment_good": "thumbs-up",
    "sentiment_bad": "thumbs-down",
    "unknown": "question",
    "star": "star",
    "notes": "file-text",
}

HEROICONS_VARIANTS: dict[str, str | None] = {
    "outline": None,
    "solid": "-solid",
    "mini": "-20-solid",
    "micro": "-16-solid",
}

LUCIDE_VARIANTS: dict[str, str | None] = {
    "outline": None,
}

TABLER_VARIANTS: dict[str, str | None] = {
    "outline": None,
    "solid": "-filled",
}

PHOSPHOR_VARIANTS: dict[str, str | None] = {
    "outline": None,
    "solid": "-fill",
    "bold": "-bold",
    "light": "-light",
    "thin": "-thin",
}

ICON_SETS: dict[str, IconSetConfig] = {
    "heroicons": IconSetConfig(
        mapping=HEROICONS_MAPPING,
        variants=HEROICONS_VARIANTS,
    ),
    "lucide": IconSetConfig(
        mapping=LUCIDE_MAPPING,
        variants=LUCIDE_VARIANTS,
    ),
    "tabler": IconSetConfig(
        mapping=TABLER_MAPPING,
        variants=TABLER_VARIANTS,
    ),
    "phosphor": IconSetConfig(
        mapping=PHOSPHOR_MAPPING,
        variants=PHOSPHOR_VARIANTS,
    ),
}

# Validate at import time that all mappings cover the same keys as SEMANTIC_ICON_NAMES
for _set_name, _config in ICON_SETS.items():
    _mapping_keys = set(_config.mapping.keys())
    if _mapping_keys != SEMANTIC_ICON_NAMES:
        _missing = SEMANTIC_ICON_NAMES - _mapping_keys
        _extra = _mapping_keys - SEMANTIC_ICON_NAMES
        raise RuntimeError(
            f"Icon set {_set_name!r} mapping keys mismatch: "
            f"missing={_missing}, extra={_extra}"
        )
