import json
from pathlib import Path
from typing import TypedDict

from django.conf import settings


class IconEntry(TypedDict, total=False):
    body: str
    width: int
    height: int


class IconifyData(TypedDict, total=False):
    prefix: str
    icons: dict[str, IconEntry]
    width: int
    height: int


_cache: dict[str, IconifyData] = {}

PACKAGE_MAP: dict[str, str] = {
    "heroicons": "heroicons",
    "lucide": "lucide",
    "tabler": "tabler",
    "phosphor": "ph",
}


def iconify_json_path(pkg: str) -> Path:
    """Return the path to an Iconify JSON file within node_modules."""
    return (
        Path(settings.BASE_DIR) / "node_modules" / f"@iconify-json/{pkg}" / "icons.json"
    )


def load_iconify_data(set_name: str) -> IconifyData:
    """Read and cache icons.json for the given icon set from node_modules."""
    if set_name in _cache:
        return _cache[set_name]
    pkg = PACKAGE_MAP.get(set_name)
    if pkg is None:
        raise ValueError(
            f"Unknown icon set: {set_name!r}. Available: {sorted(PACKAGE_MAP)}"
        )
    json_path = iconify_json_path(pkg)
    data: IconifyData = json.loads(json_path.read_text())
    _cache[set_name] = data
    return data
