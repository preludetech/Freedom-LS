"""Invariants of `.github/workflows/tests.yml` that every test job must keep.

Each test reads the workflow as YAML and checks a property across jobs; none copies a value
from the file, so changing a runner image or a timeout does not break them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.test_remote_full_run import remote

pytestmark = pytest.mark.dev_tooling

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "tests.yml"
)
TEST_STEP = "Run tests"
UNIT_JOB = "unit-tests"
STANDALONE_JOB = "standalone-tests"
SKIPPED_ON_DISPATCH = {"lint", "type-check"}


def as_table(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def as_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return value


def load_workflow() -> dict[str, object]:
    """The parsed workflow. PyYAML reads the `on:` key as the boolean `True`."""
    return as_table(yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8")))


def jobs() -> dict[str, dict[str, object]]:
    return {
        key: as_table(job) for key, job in as_table(load_workflow()["jobs"]).items()
    }


def steps_of(job: dict[str, object]) -> list[dict[str, object]]:
    return [as_table(step) for step in as_list(job["steps"])]


def find_test_step(job: dict[str, object]) -> dict[str, object] | None:
    for step in steps_of(job):
        if step.get("name") == TEST_STEP:
            return step
    return None


def job_keys_with_test_step() -> list[str]:
    """Keys of the jobs that have a `Run tests` step."""
    return [key for key, job in jobs().items() if find_test_step(job) is not None]


def run_command(job_id: str) -> str:
    step = find_test_step(jobs()[job_id])
    assert step is not None
    return str(step["run"])


def setup_uv_steps() -> list[tuple[str, dict[str, object]]]:
    found: list[tuple[str, dict[str, object]]] = []
    for key, job in jobs().items():
        for step in steps_of(job):
            if str(step.get("uses", "")).startswith("astral-sh/setup-uv"):
                found.append((key, step))
    return found


TEST_JOB_IDS = job_keys_with_test_step()
NON_STANDALONE_TEST_JOB_IDS = [key for key in TEST_JOB_IDS if key != STANDALONE_JOB]


def test_workflow_has_test_jobs() -> None:
    assert len(TEST_JOB_IDS) >= 3


@pytest.mark.parametrize("job_id", TEST_JOB_IDS)
def test_test_job_runs_through_run_tests_sh(job_id: str) -> None:
    command = run_command(job_id)

    assert ".claude/ds/scripts/run_tests.sh" in command


@pytest.mark.parametrize("job_id", TEST_JOB_IDS)
def test_test_job_passes_the_run_id_seed(job_id: str) -> None:
    command = run_command(job_id)

    assert "--randomly-seed=${{ github.run_id }}" in command


@pytest.mark.parametrize("job_id", TEST_JOB_IDS)
def test_test_job_has_a_timeout(job_id: str) -> None:
    job = jobs()[job_id]

    assert isinstance(job.get("timeout-minutes"), int)


@pytest.mark.parametrize("job_id", NON_STANDALONE_TEST_JOB_IDS)
def test_test_job_selects_markers_through_a_variable(job_id: str) -> None:
    command = run_command(job_id)

    assert '-m "$UNIT_MARKERS"' in command or '-m "$BROWSER_MARKERS"' in command


def test_coverage_group_count_equals_the_unit_matrix_length() -> None:
    strategy = as_table(jobs()[UNIT_JOB]["strategy"])
    unit_groups = as_list(as_table(strategy["matrix"])["group"])
    presence_env = [
        as_table(step["env"])["UNIT_GROUP_COUNT"]
        for step in steps_of(jobs()["coverage"])
        if "UNIT_GROUP_COUNT" in as_table(step.get("env", {}))
    ]

    assert presence_env == [len(unit_groups)]


def test_only_lint_and_type_check_skip_a_dispatch_run() -> None:
    skipping = {
        key
        for key, job in jobs().items()
        if "workflow_dispatch" in str(job.get("if", ""))
    }

    assert skipping == SKIPPED_ON_DISPATCH


@pytest.mark.parametrize(
    "job_id", [key for key, _ in setup_uv_steps()], ids=lambda key: key
)
def test_setup_uv_step_enables_the_cache(job_id: str) -> None:
    steps = [step for key, step in setup_uv_steps() if key == job_id]

    assert all(as_table(step["with"])["enable-cache"] is True for step in steps)


def test_concurrency_never_cancels_a_run() -> None:
    concurrency = as_table(load_workflow()["concurrency"])

    assert concurrency["cancel-in-progress"] is False


def job_name_expression(job_id: str) -> str:
    return str(jobs()[job_id]["name"])


@pytest.mark.parametrize("job_id", TEST_JOB_IDS)
def test_test_job_sets_record_path(job_id: str) -> None:
    step = find_test_step(jobs()[job_id])
    assert step is not None

    env = as_table(step["env"])

    assert env["DS_TEST_RECORD_PATH"] == "${{ runner.temp }}/group-report.jsonl"


@pytest.mark.parametrize("job_id", TEST_JOB_IDS)
def test_test_job_uploads_its_group_report_always(job_id: str) -> None:
    uploads = [
        step
        for step in steps_of(jobs()[job_id])
        if as_table(step.get("with", {})).get("name", "")
        == f"group-report-{job_name_expression(job_id)}"
    ]

    assert [(step["if"], as_table(step["with"])["path"]) for step in uploads] == [
        ("always()", "${{ runner.temp }}/group-report.jsonl")
    ]


def test_verdict_job_needs_every_test_job_and_coverage() -> None:
    needs = as_list(jobs()["test-verdict"]["needs"])

    assert set(needs) == {*TEST_JOB_IDS, "coverage"}


@pytest.mark.parametrize(
    "job_id",
    [
        key
        for key in TEST_JOB_IDS
        if "strategy" in jobs()[key] and key != STANDALONE_JOB
    ],
)
def test_split_test_job_passes_its_group_to_pytest(job_id: str) -> None:
    command = run_command(job_id)

    assert "--splits ${{ strategy.job-total }}" in command
    assert "--group ${{ matrix.group }}" in command


def step_names(job_id: str) -> list[object]:
    return [step.get("name") for step in steps_of(jobs()[job_id])]


@pytest.mark.parametrize(
    ("step_name", "job_ids"),
    [
        (remote.TEST_STEP, TEST_JOB_IDS),
        (remote.JOBS_STEP, ["test-verdict"]),
        (remote.PARTITION_STEP, ["test-verdict"]),
        (remote.COVERAGE_PRESENT_STEP, ["coverage"]),
        (remote.COVERAGE_CHECK_STEP, ["coverage"]),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_each_step_the_remote_command_reads_exists_in_its_job(
    step_name: str, job_ids: list[str]
) -> None:
    assert all(step_name in step_names(job_id) for job_id in job_ids)


@pytest.mark.parametrize("job_id", TEST_JOB_IDS)
def test_each_test_job_name_starts_with_a_prefix_the_remote_command_recognises(
    job_id: str,
) -> None:
    assert job_name_expression(job_id).startswith(remote.TEST_JOB_PREFIXES)
