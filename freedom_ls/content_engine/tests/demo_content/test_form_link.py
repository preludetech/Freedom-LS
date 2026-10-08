"""Regression guard for the demo-content link that reaches a Form.

`get_content_by_path` tries Topic first and falls back to Form. The fallback went
unexercised for as long as every `<c-content-link>` in the demo content pointed at
`01-what-is-git-for.md`, a file that exists in no course: a link to nowhere renders
the not-found span, which looks the same whichever branch failed to match. This
pins one link that does resolve to a form, so the branch keeps a fixture.
"""

import re
from pathlib import PurePosixPath

import pytest

from config.settings_base import BASE_DIR

pytestmark = pytest.mark.fls_internal

QUIZ_COURSE = BASE_DIR / "demo_content" / "functionality_demo_end_with_quiz"
TOPIC_BEFORE_QUIZ = QUIZ_COURSE / "2. topic" / "content.md"

_CONTENT_LINK_PATH_RE = re.compile(
    r'<c-content-link\b[^>]*?\bpath="([^"]*)"', re.IGNORECASE
)


def _resolve_from(source: PurePosixPath, relative_path: str) -> PurePosixPath:
    """Mirror `BaseContent.calculate_path_from_root` for a path on disk."""
    result = source.parent
    for part in PurePosixPath(relative_path).parts:
        result = result.parent if part == ".." else result / part
    return result


def test_topic_before_the_quiz_links_to_a_form():
    """At least one c-content-link in the demo topic resolves to a form.md."""
    markdown = TOPIC_BEFORE_QUIZ.read_text(encoding="utf-8")
    source = PurePosixPath("2. topic/content.md")

    targets = [
        _resolve_from(source, path) for path in _CONTENT_LINK_PATH_RE.findall(markdown)
    ]
    form_targets = [
        target
        for target in targets
        if target.name == "form.md" and (QUIZ_COURSE / target).is_file()
    ]

    assert form_targets, (
        "No c-content-link in '2. topic/content.md' resolves to an existing "
        f"form.md, so the Form branch of get_content_by_path has no fixture. "
        f"Resolved targets: {[str(t) for t in targets]}"
    )
