"""Helpers for tests that read the plugin markdown files."""

from __future__ import annotations

import re

# "uv run", any options, then "pytest" as a whole word on one line of code: an invocation.
# Prose that mentions both words separately is not one, and neither is "pytest-cov" as an
# option value.
PYTEST_INVOCATION = re.compile(
    r"\buv run(?:\s+-{1,2}[\w-]+(?:[ =][^\s`]+)?)*\s+pytest(?![\w-])"
)

_FENCES = ("```", "~~~")
_INLINE_SPAN = re.compile(r"`([^`\n]+(?:\n[^`\n]+)*)`")


def code_fragments(text: str) -> list[str]:
    """Each line inside a fenced block, and each inline-code span outside the fences.

    A fence opens with ``` or ~~~ and closes only with the same marker. A span may wrap
    across lines in the source, so its whitespace is collapsed to one space.
    """
    fenced_lines: list[str] = []
    prose_lines: list[str] = []
    open_fence: str | None = None
    for line in text.splitlines():
        marker = next((f for f in _FENCES if line.lstrip().startswith(f)), None)
        if open_fence is None and marker is not None:
            open_fence = marker
        elif open_fence is not None and marker == open_fence:
            open_fence = None
        elif open_fence is not None:
            fenced_lines.append(line)
        else:
            prose_lines.append(line)
    spans = [
        " ".join(span.split()) for span in _INLINE_SPAN.findall("\n".join(prose_lines))
    ]
    return fenced_lines + spans
