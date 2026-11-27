"""Every `uv sync` in the Tests workflow installs exactly what `uv.lock` records."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.dev_tooling

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/tests.yml"


def _uv_sync_steps() -> list[tuple[str, str]]:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    return [
        (f"{job_name}-step{index}", step["run"])
        for job_name, job in jobs.items()
        for index, step in enumerate(job.get("steps", []))
        if "uv sync" in step.get("run", "")
    ]


UV_SYNC_STEPS = _uv_sync_steps()


def test_workflow_has_uv_sync_steps() -> None:
    assert UV_SYNC_STEPS


@pytest.mark.parametrize(
    "command",
    [command for _, command in UV_SYNC_STEPS],
    ids=[step_id for step_id, _ in UV_SYNC_STEPS],
)
def test_uv_sync_step_uses_locked(command: str) -> None:
    assert "uv sync --locked" in command
