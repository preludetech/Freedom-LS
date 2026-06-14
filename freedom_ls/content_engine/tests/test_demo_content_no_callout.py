"""Regression guard: demo_content must not contain c-callout.

c-callout was removed from the MARKDOWN_ALLOWED_TAGS allowlist in Phase 2
and replaced by c-admonition. Any c-callout left in demo_content/ would
silently strip the tag and its attributes from rendered output, yielding
degraded content without a visible error.

This test asserts that no file under demo_content/ contains the string
"c-callout" so the regression is caught at CI time.
"""

from __future__ import annotations

from pathlib import Path

from config.settings_base import BASE_DIR

DEMO_CONTENT_DIR = BASE_DIR / "demo_content"


def _files_containing_callout() -> list[Path]:
    """Return all files under demo_content/ that mention c-callout."""
    offenders = []
    for path in DEMO_CONTENT_DIR.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "c-callout" in text:
            offenders.append(path)
    return offenders


def test_demo_content_contains_no_c_callout():
    """No file under demo_content/ may use the deprecated c-callout component."""
    offenders = _files_containing_callout()

    assert not offenders, (
        "demo_content/ files still contain 'c-callout' (deprecated; use c-admonition): "
        + ", ".join(str(p.relative_to(BASE_DIR)) for p in offenders)
    )
