import re
from pathlib import Path

import pytest

FREEDOM_LS_DIR = Path(__file__).resolve().parents[3]
CONTENT_ENGINE_TEMPLATES = FREEDOM_LS_DIR / "content_engine" / "templates"

# Content widgets exist for authored markdown. An app page uses <c-callout>
# for a status message; the remaining content-engine components (prices,
# bylines, article cards, grids) are shared with app pages and stay allowed.
BANNED_TAGS = (
    "c-admonition",
    "c-accordion",
    "c-flashcard",
    "c-pull-quote",
    "c-equation",
    "c-youtube",
    "c-pdf-embed",
    "c-file-download",
    "c-code-block",
    "c-table",
    "c-picture",
    "c-image-grid",
    "c-card",
    "c-content-link",
    "c-article-link",
    "c-audio",
    "c-audio-reveal",
    "c-audio-clip",
    "c-content-error",
    "c-panel-notice",
)
FIX = (
    "use <c-callout> for a status message in an app page; "
    "content widgets are for authored markdown only"
)
LEVEL_FIX = "pass tone= instead of level= on a callout"

COMMENT_BLOCK = re.compile(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}", re.DOTALL)
COMMENT_INLINE = re.compile(r"{#.*?#}", re.DOTALL)
CALLOUT_WITH_LEVEL = re.compile(r"<c-(?:panel-)?callout(?![\w-])[^>]*\blevel=")


def app_templates() -> list[Path]:
    """Every app template, leaving out the content engine's own, where the widgets live and nest."""
    return sorted(
        path
        for path in FREEDOM_LS_DIR.glob("*/templates/**/*.html")
        if not path.is_relative_to(CONTENT_ENGINE_TEMPLATES)
    )


def without_comments(text: str) -> str:
    """The text with Django block comments and inline comments removed."""
    return COMMENT_INLINE.sub("", COMMENT_BLOCK.sub("", text))


def violations_in(text: str) -> list[str]:
    """Each banned tag the text uses outside a comment, matched as <c-NAME(?![\\w-]),
    plus "level=" when a callout outside a comment carries it."""
    live = without_comments(text)
    found = [tag for tag in BANNED_TAGS if re.search(rf"<{tag}(?![\w-])", live)]
    return found + ["level="] * bool(CALLOUT_WITH_LEVEL.search(live))


@pytest.mark.parametrize(
    "path",
    app_templates(),
    ids=lambda path: str(path.relative_to(FREEDOM_LS_DIR)),
)
def test_app_templates_use_no_content_widget_or_callout_level(path: Path) -> None:
    violations = violations_in(path.read_text())

    assert not violations, (
        f"{path.relative_to(FREEDOM_LS_DIR)} uses {violations}: {FIX}; "
        f"for level=, {LEVEL_FIX}"
    )


# A thick coloured bar down a box's start edge is the admonition's look.
# Thin (1-2px) start borders stay allowed: they indent threads and nested lists.
THICK_START_BORDER = re.compile(r"(?<![\w-])border-[sl]-(?:[4-8]|\[)")
ADMONITION_LOOK_EXEMPT = {
    # The toast's severity stripe is the toast's own design.
    Path("base/templates/partials/_toast.html"),
}
ADMONITION_LOOK_FIX = (
    "an app template never hand-builds the admonition look; put content in a box with "
    "a 1px border (as a chosen option row does), or use <c-callout> for a notice"
)


@pytest.mark.parametrize(
    "path",
    [
        path
        for path in app_templates()
        if path.relative_to(FREEDOM_LS_DIR) not in ADMONITION_LOOK_EXEMPT
    ],
    ids=lambda path: str(path.relative_to(FREEDOM_LS_DIR)),
)
def test_app_templates_hand_build_no_admonition_look(path: Path) -> None:
    found = THICK_START_BORDER.findall(without_comments(path.read_text()))

    assert not found, (
        f"{path.relative_to(FREEDOM_LS_DIR)} uses {found}: {ADMONITION_LOOK_FIX}"
    )


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ("<c-admonition>", "c-admonition"),
        ("<c-panel-notice>", "c-panel-notice"),
        ('<c-callout level="info">', "level="),
    ],
)
def test_violations_in_reports_banned_markup(markup: str, expected: str) -> None:
    assert expected in violations_in(markup)


@pytest.mark.parametrize(
    "markup",
    [
        "<c-course-price>",
        '<c-callout tone="info">',
        "<c-card-row>",
    ],
)
def test_violations_in_allows_permitted_markup(markup: str) -> None:
    assert violations_in(markup) == []


@pytest.mark.parametrize(
    "markup",
    [
        "{% comment %}<c-admonition>{% endcomment %}",
        '{% comment %}<c-callout level="info">{% endcomment %}',
        "{# <c-admonition> #}",
        '{# <c-callout level="info"> #}',
    ],
)
def test_violations_in_ignores_comments(markup: str) -> None:
    assert violations_in(markup) == []
