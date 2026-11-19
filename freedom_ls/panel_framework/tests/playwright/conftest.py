"""Browser-test setup for panel_framework."""

from __future__ import annotations

from pathlib import Path

import pytest

REFERENCE_CSS = (
    Path(__file__).resolve().parents[2]
    / "static"
    / "panel_framework"
    / "css"
    / "reference.css"
)


@pytest.fixture(autouse=True, scope="session")
def _reference_css_is_built() -> None:
    """The minimal shell links a compiled stylesheet that is not committed.

    Without it every flow runs against an unstyled page and fails on layout,
    far from the cause.
    """
    if not REFERENCE_CSS.exists():
        pytest.fail("reference.css is missing: run `npm run panel_framework_css`")
