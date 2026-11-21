import json
from pathlib import Path

from freedom_ls.icons.loader import PACKAGE_MAP


def write_icon_set(root: Path, set_name: str, data: dict[str, object]) -> Path:
    """Write `data` as the icons.json of `set_name` under `root`, in node_modules' layout."""
    path = root / PACKAGE_MAP[set_name] / "icons.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path
