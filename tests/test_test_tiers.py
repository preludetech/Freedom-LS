"""Plugin markdown spells out a pytest invocation only in the files that own one.

Every other command and agent names a test tier and reads the tier definition, so the
pytest flags live in one place.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIRS = (
    "claude_plugins/sdd",
    "claude_plugins/django-stack",
    "claude_plugins/fls-dev",
)

# Files allowed to spell out a pytest invocation: the tier definition, the testing
# and Playwright guidance, and the downstream updater's portable subset.
ALLOWED = frozenset(
    {
        "claude_plugins/django-stack/resources/test_tiers.md",
        "claude_plugins/fls-dev/skills/testing/SKILL.md",
        "claude_plugins/fls-dev/resources/testing.md",
        "claude_plugins/fls-dev/resources/playwright-testing.md",
        "claude_plugins/fls-dev/skills/playwright-tests/SKILL.md",
        "claude_plugins/fls-dev/commands/concrete/update_fls.md",
        # The triage gate describes the full tier as the ordinary pytest suite.
        "claude_plugins/fls-dev/commands/do_qa.md",
        # Still to convert:
        "claude_plugins/django-stack/commands/rebase_main.md",
        "claude_plugins/django-stack/commands/commit.md",
        "claude_plugins/sdd/commands/implement_plan.md",
        "claude_plugins/sdd/commands/address_pr_review.md",
    }
)


def files_spelling_out_pytest() -> set[str]:
    return {
        path.relative_to(REPO_ROOT).as_posix()
        for plugin_dir in PLUGIN_DIRS
        for path in (REPO_ROOT / plugin_dir).rglob("*.md")
        if "uv run pytest" in path.read_text()
    }


def test_only_allowlisted_plugin_files_spell_out_a_pytest_invocation() -> None:
    assert files_spelling_out_pytest() == ALLOWED
