"""Regression guards for demo-content c-picture authoring.

The `number="N"` attribute already supplies a "Figure N" prefix in both the
thumbnail figcaption and the spotlight heading, so a `title` that *also* begins
with "Figure N:" renders a doubled "Figure 2: Figure 2:" caption. This guards
the demo content against re-introducing that duplication (QA Bug 4).
"""

import re

from config.settings_base import BASE_DIR

CONTENT_WIDGETS_MEDIA = (
    BASE_DIR
    / "demo_content"
    / "functionality_demo_content_widgets"
    / "2. media"
    / "content.md"
)

# Captures the `number` and `title` attribute values of every <c-picture> tag.
_C_PICTURE_RE = re.compile(r"<c-picture\b[^>]*?>", re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def _pictures_with_number_and_title(markdown: str) -> list[tuple[str, str]]:
    """Yield (number, title) for every c-picture that sets both attributes."""
    pairs = []
    for tag in _C_PICTURE_RE.findall(markdown):
        attrs = dict(_ATTR_RE.findall(tag))
        number = attrs.get("number", "").strip()
        title = attrs.get("title", "").strip()
        if number and title:
            pairs.append((number, title))
    return pairs


def test_demo_media_picture_titles_do_not_duplicate_figure_prefix():
    """No numbered c-picture in the media demo may repeat its own "Figure N" prefix."""
    markdown = CONTENT_WIDGETS_MEDIA.read_text(encoding="utf-8")

    offenders = [
        (number, title)
        for number, title in _pictures_with_number_and_title(markdown)
        if title.lower().startswith(f"figure {number.lower()}")
    ]

    assert not offenders, (
        "c-picture title duplicates the 'Figure N' prefix already supplied by "
        f"number=...: {offenders}"
    )
