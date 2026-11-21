import json
from pathlib import Path
from typing import TypedDict

from freedom_ls.icons.config import config


class IconEntry(TypedDict, total=False):
    body: str
    width: int
    height: int


class IconifyData(TypedDict, total=False):
    prefix: str
    icons: dict[str, IconEntry]
    width: int
    height: int


# The size build_svg draws an entry with when neither the entry nor its file gives one.
DEFAULT_ICON_SIZE = 24

_cache: dict[tuple[str, Path | None], IconifyData] = {}

# Bundled data lives inside the app and uses node_modules/@iconify-json's layout, so one
# lookup reads either root.
BUNDLED_DATA_DIR = Path(__file__).resolve().parent / "data"

PACKAGE_MAP: dict[str, str] = {
    "heroicons": "heroicons",
    "lucide": "lucide",
    "tabler": "tabler",
    "phosphor": "ph",
}


def set_file(root: Path, set_name: str) -> Path:
    """The icons.json of `set_name` under `root`, in node_modules' layout."""
    return root / PACKAGE_MAP[set_name] / "icons.json"


def usable_iconify_dir() -> Path | None:
    """The configured directory when it is an absolute path to an existing directory.

    Anything else means bundled data only, so rendering and icons.E008 agree on what counts.
    """
    value = config.SEMANTIC_ICONS_ICONIFY_DIR
    if value is None:
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() and path.is_dir() else None


def _read(path: Path) -> IconifyData:
    data: IconifyData = json.loads(path.read_text())
    return data


def load_iconify_data(set_name: str) -> IconifyData:
    """The bundled data for the set, with the configured directory's entries laid over it."""
    if set_name not in PACKAGE_MAP:
        raise ValueError(
            f"Unknown icon set: {set_name!r}. Available: {sorted(PACKAGE_MAP)}"
        )
    directory = usable_iconify_dir()
    # Keyed on the directory too, so a changed setting never serves data cached under another.
    key = (set_name, directory)
    if key not in _cache:
        data = _read(set_file(BUNDLED_DATA_DIR, set_name))
        if directory is not None and set_file(directory, set_name).is_file():
            data = _overlay(data, _read(set_file(directory, set_name)))
        _cache[key] = data
    return _cache[key]


def _overlay(bundled: IconifyData, full: IconifyData) -> IconifyData:
    """Bundled entries with the full file's entries laid over them, glyph by glyph.

    The merged root size is the bundled file's. A full-file entry whose effective size
    differs from that root carries its size explicitly, so it still draws at its own size.
    """
    default = (DEFAULT_ICON_SIZE, DEFAULT_ICON_SIZE)
    root = _size(bundled, default)
    full_root = _size(full, default)
    icons = dict(bundled["icons"])
    for name, entry in full["icons"].items():
        size = _size(entry, full_root)
        merged: IconEntry = {**entry}
        if size != root:
            merged["width"], merged["height"] = size
        icons[name] = merged
    return {**bundled, "icons": icons}


def _size(node: IconifyData | IconEntry, fallback: tuple[int, int]) -> tuple[int, int]:
    """A file's or entry's own (width, height), each falling back to `fallback`."""
    return (node.get("width", fallback[0]), node.get("height", fallback[1]))


def clear_cache() -> None:
    """Forget every loaded set, so the next read sees the current settings and files."""
    _cache.clear()
