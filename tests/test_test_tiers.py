"""Plugin markdown spells out a pytest invocation only in the files that own one.

Every other command and agent names a test tier and reads the tier definition, so the
pytest flags live in one place.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.plugin_markdown import PYTEST_INVOCATION, code_fragments

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIRS = (
    "claude_plugins/sdd",
    "claude_plugins/django-stack",
    "claude_plugins/fls-dev",
)

# Files allowed to spell out a pytest invocation: the tier definition, the testing
# and Playwright guidance, and the shared integration procedure's portable contract test set.
ALLOWED = frozenset(
    {
        "claude_plugins/django-stack/resources/test_tiers.md",
        "claude_plugins/fls-dev/skills/testing/SKILL.md",
        "claude_plugins/fls-dev/resources/playwright-testing.md",
        "claude_plugins/fls-dev/resources/concrete_spec_integration.md",
        # The fallback for a project with no tier definition.
        "claude_plugins/sdd/commands/protected/run_test_tier.md",
    }
)


def spells_out_pytest(text: str) -> bool:
    """Prose and fenced code are scanned as written; the fragment pass adds inline spans
    that wrap across lines."""
    return bool(PYTEST_INVOCATION.search(text)) or any(
        PYTEST_INVOCATION.search(f) for f in code_fragments(text)
    )


def files_spelling_out_pytest() -> set[str]:
    return {
        path.relative_to(REPO_ROOT).as_posix()
        for plugin_dir in PLUGIN_DIRS
        for path in (REPO_ROOT / plugin_dir).rglob("*.md")
        if spells_out_pytest(path.read_text())
    }


def test_only_allowlisted_plugin_files_spell_out_a_pytest_invocation() -> None:
    assert files_spelling_out_pytest() == ALLOWED


@pytest.mark.parametrize(
    "text",
    [
        "uv run --directory /p pytest -m x",
        "uv run pytest",
    ],
)
def test_detector_matches_a_pytest_invocation(text: str) -> None:
    fenced = f"```\n{text}\n```"
    tilde_fenced = f"~~~\n{text}\n~~~"
    inline = f"Run `{text}` now"
    prose = f"then run {text} before committing"

    assert spells_out_pytest(fenced)
    assert spells_out_pytest(tilde_fenced)
    assert spells_out_pytest(inline)
    assert spells_out_pytest(prose)


@pytest.mark.parametrize(
    "text",
    [
        "run `uv run` then pytest",
        "`uv run --with pytest-cov python x.py`",
        "`uv run --with pillow python x.py`",
    ],
)
def test_detector_ignores_text_that_is_not_an_invocation(text: str) -> None:
    assert not spells_out_pytest(text)


def test_detector_matches_an_inline_span_wrapped_across_two_lines() -> None:
    text = "Run `uv run\npytest -x` to check."

    assert spells_out_pytest(text)


def test_a_backtick_fence_inside_a_tilde_fence_does_not_close_it() -> None:
    text = "~~~\n```\nuv run pytest\n```\n~~~"

    assert code_fragments(text) == ["```", "uv run pytest", "```"]
