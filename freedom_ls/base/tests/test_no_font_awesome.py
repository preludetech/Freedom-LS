import re
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent  # freedom_ls/

FA_PATTERNS = [
    (re.compile(r"\bfa-\w+"), "Font Awesome icon class"),
    (re.compile(r"\bfas\b"), "Font Awesome solid shorthand"),
    (re.compile(r"\bfar\b"), "Font Awesome regular shorthand"),
    (re.compile(r"\bfab\b"), "Font Awesome brands shorthand"),
    (re.compile(r"\bfal\b"), "Font Awesome light shorthand"),
    (re.compile(r"font-awesome", re.IGNORECASE), "Font Awesome reference"),
    (re.compile(r"cdnjs\.cloudflare\.com"), "CDN reference"),
]


def _get_template_files() -> list[Path]:
    return list(TEMPLATE_DIR.glob("**/*.html"))


def test_no_font_awesome_patterns_in_templates() -> None:
    violations: list[str] = []
    for path in _get_template_files():
        content = path.read_text()
        for pattern, description in FA_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                rel_path = path.relative_to(TEMPLATE_DIR)
                violations.append(f"{rel_path}: {description} ({matches})")
    assert not violations, "Font Awesome references found:\n" + "\n".join(violations)


def test_no_inline_svg_icons_in_templates() -> None:
    svg_icon_pattern = re.compile(
        r"<svg[^>]*viewBox=\"0 0 \d+ \d+\"[^>]*>.*?</svg>",
        re.DOTALL,
    )
    violations: list[str] = []
    for path in _get_template_files():
        content = path.read_text()
        for match in svg_icon_pattern.finditer(content):
            if "<path" in match.group():
                rel_path = path.relative_to(TEMPLATE_DIR)
                violations.append(f"{rel_path}: inline SVG icon found")
    assert not violations, (
        "Inline SVG icons found (use <c-icon /> instead):\n" + "\n".join(violations)
    )


COTTON_ICON_PATH = Path("base/templates/cotton/icon.html")


def test_no_direct_icon_tags_load_outside_cotton() -> None:
    """Ensure {% load icon_tags %} only appears in cotton/icon.html.

    All templates must use <c-icon /> instead of loading icon_tags directly.
    """
    icon_tags_pattern = re.compile(r"\{%\s*load\s+icon_tags\b")
    violations: list[str] = []
    for path in _get_template_files():
        rel_path = path.relative_to(TEMPLATE_DIR)
        if rel_path == COTTON_ICON_PATH:
            continue
        content = path.read_text()
        if icon_tags_pattern.search(content):
            violations.append(str(rel_path))
    assert not violations, (
        "Templates must use <c-icon /> instead of {% load icon_tags %} directly:\n"
        + "\n".join(violations)
    )
