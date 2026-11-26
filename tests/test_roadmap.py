"""Tests for `claude_plugins/sdd/scripts/roadmap.py`.

Each test writes a small `spec_dd/` tree into `tmp_path` and runs the script on its roadmap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._script_trees import run_script, write_tree

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "sdd" / "scripts" / "roadmap.py"
ROADMAP = "spec_dd/1. next/roadmap.md"

COLLIDING_ROADMAP = """\
# Spec roadmap

## Up next

## Quizzes

Quiz controls.

- `quiz-limits` — **ready** — Quizzes cap attempts. Collides with `quiz-timer`.
- `quiz-timer` — **in progress** — Quizzes get a time limit.
"""


def up_next_group(roadmap: str, heading: str) -> str:
    """The lines under one `### <heading>` of the Up next section."""
    after = roadmap.split(f"### {heading}\n", 1)[1]
    return after.split("###", 1)[0].split("## ", 1)[0]


def test_ready_spec_colliding_with_in_progress_spec_is_not_ready_to_start(
    tmp_path: Path,
) -> None:
    write_tree(
        tmp_path,
        {
            ROADMAP: COLLIDING_ROADMAP,
            "spec_dd/1. next/quiz-limits/idea.md": "# Limits\n",
            "spec_dd/2. in progress/quiz-timer/idea.md": "# Timer\n",
            "spec_dd/3. done/.keep": "",
        },
    )

    run_script(SCRIPT, tmp_path, ROADMAP)

    roadmap = (tmp_path / ROADMAP).read_text(encoding="utf-8")
    assert "`quiz-limits`" in up_next_group(roadmap, "Waiting on a collision")
    assert "`quiz-limits`" not in up_next_group(roadmap, "Ready to start")
