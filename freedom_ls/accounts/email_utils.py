import re
from pathlib import Path


def parse_tailwind_colors(css_file_path: str) -> dict[str, str]:
    """Parse --color-* custom properties from a CSS file.

    Returns a dict like {"primary": "#2B6CB0", "foreground": "#1A2332", ...}
    Only captures hex color values (e.g., #XXXXXX or #XXX).
    """
    path = Path(css_file_path)
    if not path.exists():
        return {}

    content = path.read_text()
    pattern = re.compile(r"--color-([\w-]+):\s*(#[0-9A-Fa-f]{3,8});")
    return dict(pattern.findall(content))
