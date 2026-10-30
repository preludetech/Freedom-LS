"""Helpers for tests that read the plugin markdown files."""

from __future__ import annotations

import re

# "uv run", any options, then "pytest" as a whole word on one line of code: an invocation.
# Prose that mentions both words separately is not one, and neither is "pytest-cov" as an
# option value.
PYTEST_INVOCATION = re.compile(
    r"\buv run(?:\s+-{1,2}[\w-]+(?:[ =][^\s`]+)?)*\s+pytest(?![\w-])"
)

_FENCE = "```"
_INLINE_SPAN = re.compile(r"`([^`\n]+(?:\n[^`\n]+)*)`")


def code_fragments(text: str) -> list[str]:
    """Each line inside a fenced block, and each inline-code span outside the fences.

    A span may wrap across lines in the source, so its whitespace is collapsed to one space.
    """
    fenced_lines: list[str] = []
    prose_lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(_FENCE):
            in_fence = not in_fence
        elif in_fence:
            fenced_lines.append(line)
        else:
            prose_lines.append(line)
    spans = [
        " ".join(span.split()) for span in _INLINE_SPAN.findall("\n".join(prose_lines))
    ]
    return fenced_lines + spans
