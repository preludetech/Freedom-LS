# ruff: noqa: T201
"""Run the full test tier on GitHub Actions and print its verdict in the test runner's shape.

Dispatches the `Tests` workflow for the current branch, waits for it, and reads each test
job's group report. Prints `run: RESULT UNAVAILABLE <reason>` and exits 69 whenever GitHub
gives no test verdict, so the caller can run the tier locally instead.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

import ds_runner

WORKFLOW = "tests.yml"
POLL_INTERVAL_S = 20
QUIET_HEARTBEAT_S = 60
EXIT_PASS, EXIT_FAIL, EXIT_UNAVAILABLE = 0, 1, 69  # 69 is sysexits' EX_UNAVAILABLE
MIN_GH = (2, 87, 0)  # the first gh whose `workflow run` prints the new run's URL
NON_TEST_JOBS = frozenset({"coverage", "test-verdict"})
TEST_JOB_PREFIXES = ("unit-", "playwright-", "standalone-")
TEST_STEP = "Run tests"
JOBS_STEP = "Check every test job succeeded"
PARTITION_STEP = "Check the partition"
COVERAGE_PRESENT_STEP = "Check every group's coverage data is present"
COVERAGE_CHECK_STEP = "Check combined coverage"
STANDALONE_PREFIX = "standalone-"
STANDALONE_NODE_PREFIX = "freedom_ls/{app}/tests/"
DEFAULT_START_TIMEOUT_S = 900
DEFAULT_RUN_TIMEOUT_S = 1800
MAX_UNREACHABLE_VIEWS = 3
RUN_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/actions/runs/(\d+)")
GH_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
VIEW_FIELDS = "status,conclusion,headSha,jobs,createdAt,updatedAt"
OUTCOME_SEVERITY = {"passed": 0, "skipped": 1, "failed": 2}
WORK_DIR = Path(".sdd-work")

run_tests = ds_runner.load_run_tests()  # the generic runner, imported by path


class RunStateView(Protocol):
    """The fields of the runner's `RunState` that this script reads."""

    collected: set[str]
    outcomes: dict[str, str]


class Unavailable(Exception):  # noqa: N818 - a verdict outcome, not an error
    """No test verdict: the reason is printed and the tier runs locally."""


@dataclass(frozen=True)
class Settings:
    start_timeout_s: int
    run_timeout_s: int


@dataclass(frozen=True)
class Step:
    name: str
    conclusion: str


@dataclass(frozen=True)
class Job:
    name: str
    status: str
    conclusion: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class RunView:
    status: str
    conclusion: str
    head_sha: str
    created_at: str
    updated_at: str
    jobs: tuple[Job, ...]


@dataclass(frozen=True)
class CoverageTotal:
    total: str
    fail_under: str


@dataclass(frozen=True)
class Verdict:
    result: str  # "PASS" or "FAIL"
    failed: frozenset[str] = frozenset()
    coverage: CoverageTotal | None = None


@dataclass
class Progress:
    """What `main` knows about the run, so a failure can cancel and name it."""

    url: str = ""
    run_id: str = ""
    cancellable: bool = False


@dataclass
class GroupReport:
    """One test job's group report: its run state and the text of each failure."""

    state: RunStateView
    failures: dict[str, str] = field(default_factory=dict)


def run_tool(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one command to completion; a tool missing from `PATH` is `Unavailable`."""
    try:
        return subprocess.run(  # noqa: S603
            argv, check=False, capture_output=True, text=True
        )
    except FileNotFoundError:
        raise Unavailable(f"{argv[0]} is not installed") from None


def first_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[0] if lines else ""


def load_settings() -> Settings:
    """The two budgets from `[tool.test_tiers.remote]`; other keys belong to the tier."""
    values = {
        "start_timeout_s": DEFAULT_START_TIMEOUT_S,
        "run_timeout_s": DEFAULT_RUN_TIMEOUT_S,
    }
    pyproject = Path("pyproject.toml")
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        tool = data.get("tool", {})
        table = tool.get("test_tiers", {}).get("remote", {})
        for key in values:
            if key not in table:
                continue
            value = table[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise Unavailable(
                    f"[tool.test_tiers.remote] '{key}' must be an integer"
                )
            values[key] = value
    return Settings(values["start_timeout_s"], values["run_timeout_s"])


def current_branch() -> str:
    result = run_tool(["git", "symbolic-ref", "--short", "-q", "HEAD"])
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        raise Unavailable("HEAD is detached")
    return branch


def check_gh() -> None:
    result = run_tool(["gh", "--version"])
    match = GH_VERSION.search(first_line(result.stdout))
    if result.returncode != 0 or match is None:
        raise Unavailable("cannot read the gh version")
    found = tuple(int(part) for part in match.groups())
    if found < MIN_GH:
        wanted = ".".join(str(part) for part in MIN_GH)
        raise Unavailable(
            f"gh {'.'.join(str(part) for part in found)} is older than {wanted}"
        )
    if run_tool(["gh", "auth", "status"]).returncode != 0:
        raise Unavailable("gh is not logged in")


def check_preconditions() -> str:
    """The branch to test, once the tree is clean, HEAD is on a branch and `gh` can dispatch."""
    status = run_tool(["git", "status", "--porcelain", "--untracked-files=no"])
    if status.stdout.strip():
        raise Unavailable("tracked files have uncommitted changes")
    branch = current_branch()
    check_gh()
    return branch


def push_if_needed(branch: str) -> str:
    """Push HEAD to `origin/<branch>` unless it is already there; returns HEAD's sha.

    A plain push: a branch another process rewrote on `origin` is rejected, never overwritten.
    """
    head = run_tool(["git", "rev-parse", "HEAD"]).stdout.strip()
    listing = run_tool(["git", "ls-remote", "origin", f"refs/heads/{branch}"])
    if listing.returncode != 0:
        raise Unavailable("cannot reach origin")
    remote_tip = listing.stdout.split()[0] if listing.stdout.strip() else ""
    if remote_tip == head:
        return head
    if branch in {"main", "master"}:
        raise Unavailable(
            f"origin/{branch} lacks HEAD and {branch} is never pushed from here"
        )
    upstream = run_tool(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
    )
    push = ["git", "push"]
    if upstream.returncode != 0:
        push.append("-u")
    push += ["origin", f"HEAD:refs/heads/{branch}"]
    result = run_tool(push)
    if result.returncode != 0:
        raise Unavailable(f"push rejected: {first_line(result.stderr)}")
    return head


def dispatch(branch: str) -> tuple[str, str]:
    """Start the workflow for `branch`; returns the run's id and URL."""
    result = run_tool(["gh", "workflow", "run", WORKFLOW, f"--ref={branch}"])
    match = RUN_URL.search(result.stdout + result.stderr)
    if result.returncode != 0 or match is None:
        raise Unavailable("gh workflow run printed no run URL")
    return match.group(1), match.group(0)


def text_field(table: dict[str, object], key: str) -> str:
    value = table.get(key)
    return value if isinstance(value, str) else ""


def parse_job(raw: object) -> Job:
    if not isinstance(raw, dict):
        raise ValueError("job is not an object")
    steps = raw.get("steps")
    return Job(
        name=text_field(raw, "name"),
        status=text_field(raw, "status"),
        conclusion=text_field(raw, "conclusion"),
        steps=tuple(
            Step(text_field(step, "name"), text_field(step, "conclusion"))
            for step in steps or []
            if isinstance(step, dict)
        ),
    )


def parse_view(text: str) -> RunView:
    """The run view from `gh run view --json`; ValueError when the output is not one."""
    raw: object = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("run view is not an object")
    jobs = raw.get("jobs")
    return RunView(
        status=text_field(raw, "status"),
        conclusion=text_field(raw, "conclusion"),
        head_sha=text_field(raw, "headSha"),
        created_at=text_field(raw, "createdAt"),
        updated_at=text_field(raw, "updatedAt"),
        jobs=tuple(parse_job(job) for job in jobs or []),
    )


def view_run(run_id: str) -> RunView | None:
    """The run's current view, or None when GitHub could not be reached or answered badly."""
    result = run_tool(["gh", "run", "view", run_id, "--json", VIEW_FIELDS])
    if result.returncode != 0:
        return None
    try:
        return parse_view(result.stdout)
    except ValueError:  # includes json.JSONDecodeError
        return None


def job_state(job: Job) -> str:
    return job.conclusion or job.status


def poll(run_id: str, head: str, settings: Settings) -> RunView:
    """Wait for the run to complete, printing a line whenever a job changes state."""
    started = time.monotonic()
    last_printed = started
    seen: dict[str, str] = {}
    ever_started = False
    first_view = True
    unreachable = 0
    while True:
        view = view_run(run_id)
        if view is None:
            unreachable += 1
            if unreachable >= MAX_UNREACHABLE_VIEWS:
                raise Unavailable("GitHub unreachable")
        else:
            unreachable = 0
            if first_view and view.head_sha != head:
                raise Unavailable(
                    f"run {run_id} tests {view.head_sha[:7]}, not HEAD {head[:7]}"
                )
            first_view = False
            for job in view.jobs:
                if seen.get(job.name) != job_state(job):
                    seen[job.name] = job_state(job)
                    print(f"remote: {job.name} {job_state(job)}")
                    last_printed = time.monotonic()
            if view.status == "completed":
                return view
            ever_started = ever_started or any(
                job.status in {"in_progress", "completed"} for job in view.jobs
            )
            elapsed = time.monotonic() - started
            if not ever_started and elapsed >= settings.start_timeout_s:
                raise Unavailable(f"no job started within {settings.start_timeout_s} s")
            if elapsed >= settings.run_timeout_s:
                raise Unavailable(f"run exceeded {settings.run_timeout_s} s")
            if time.monotonic() - last_printed >= QUIET_HEARTBEAT_S:
                done = sum(job.status == "completed" for job in view.jobs)
                print(
                    f"remote: waiting, {done} of {len(view.jobs)} jobs done, "
                    f"{elapsed:.0f} s"
                )
                last_printed = time.monotonic()
        time.sleep(run_tests.scaled(POLL_INTERVAL_S))


def download(run_id: str, directory: Path) -> None:
    result = run_tool(
        [
            "gh",
            "run",
            "download",
            run_id,
            "-D",
            str(directory),
            "-p",
            "group-report-*",
            "-p",
            "coverage-total",
        ]
    )
    if result.returncode != 0:
        raise Unavailable("could not download the group reports")


def is_test_job(job: Job) -> bool:
    return job.name not in NON_TEST_JOBS and job.name.startswith(TEST_JOB_PREFIXES)


def find_job(jobs: list[Job], name: str) -> Job:
    for job in jobs:
        if job.name == name:
            return job
    raise Unavailable(f"the run has no {name} job")


def failed_steps(job: Job) -> set[str]:
    return {step.name for step in job.steps if step.conclusion == "failure"}


def describe_failure(job: Job, ignoring: set[str]) -> str:
    """`<job> <conclusion>`, plus ` at <step>` for the first failed step not ignored."""
    others = [
        step.name
        for step in job.steps
        if step.conclusion == "failure" and step.name not in ignoring
    ]
    return f"{job.name} {job.conclusion}" + (f" at {others[0]}" if others else "")


def require_test_verdicts(jobs: list[Job]) -> None:
    """Raise Unavailable for a test job that was cancelled or skipped, or failed in a step
    other than the test step: such a job left no test verdict."""
    for job in jobs:
        if not is_test_job(job) or job.conclusion == "success":
            continue
        if job.conclusion != "failure" or failed_steps(job) != {TEST_STEP}:
            raise Unavailable(describe_failure(job, {TEST_STEP}))


def require_verdict_job(jobs: list[Job]) -> None:
    """`test-verdict` fails its job check whenever a test job or `coverage` failed, which is
    a verdict. Any other failed step (the partition check, a setup step) or a cancelled
    job is not."""
    verdict_job = find_job(jobs, "test-verdict")
    if verdict_job.conclusion not in {"success", "failure"} or not (
        failed_steps(verdict_job) <= {JOBS_STEP}
    ):
        raise Unavailable(describe_failure(verdict_job, {JOBS_STEP}))


def classify(
    jobs: list[Job],
    states: dict[str, RunStateView],
    coverage_total: CoverageTotal | None,
) -> Verdict:
    """The verdict of a run whose jobs all left a test verdict."""
    failed = frozenset(
        node
        for state in states.values()
        for node, outcome in state.outcomes.items()
        if outcome == "failed"
    )
    failing_jobs = [
        job for job in jobs if is_test_job(job) and job.conclusion == "failure"
    ]
    if failing_jobs:
        if not failed:
            raise Unavailable(f"{failing_jobs[0].name} failed with no failed test")
        return Verdict("FAIL", failed=failed)
    coverage_job = find_job(jobs, "coverage")
    if coverage_job.conclusion == "success":
        return Verdict("PASS")
    if failed_steps(coverage_job) == {COVERAGE_CHECK_STEP}:
        if coverage_total is None:
            raise Unavailable("coverage failed and uploaded no coverage-total")
        return Verdict("FAIL", coverage=coverage_total)
    raise Unavailable(describe_failure(coverage_job, set()))


def prefixed(report: GroupReport, prefix: str) -> GroupReport:
    """The report with `prefix` added to every node ID, as a local re-run needs them."""
    state = run_tests.RunState()
    state.collected = {prefix + node for node in report.state.collected}
    state.outcomes = {prefix + node: out for node, out in report.state.outcomes.items()}
    return GroupReport(
        state, {prefix + node: text for node, text in report.failures.items()}
    )


def failure_texts(path: Path) -> dict[str, str]:
    """The `longrepr` of each failed test in a group report; the first outcome wins."""
    texts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event: object = json.loads(line)
        except json.JSONDecodeError:
            continue  # a truncated last line; `read_attempt` rejects any other
        if not isinstance(event, dict) or event.get("event") != "outcome":
            continue
        node = event.get("nodeid")
        if isinstance(node, str) and event.get("outcome") == "failed":
            texts.setdefault(node, str(event.get("longrepr", "")))
    return texts


def load_group_report(job: Job, directory: Path) -> GroupReport:
    path = directory / f"group-report-{job.name}" / "group-report.jsonl"
    if not path.is_file():
        raise Unavailable(f"{job.name} uploaded no group report")
    state = run_tests.RunState()
    try:
        run_tests.read_attempt(path, state)
    except json.JSONDecodeError:
        raise Unavailable(f"{job.name} group report is malformed") from None
    report = GroupReport(state, failure_texts(path))
    if job.name.startswith(STANDALONE_PREFIX):
        app = job.name.removeprefix(STANDALONE_PREFIX)
        return prefixed(report, STANDALONE_NODE_PREFIX.format(app=app))
    return report


def load_coverage_total(directory: Path) -> CoverageTotal | None:
    path = directory / "coverage-total" / "coverage_total.txt"
    if not path.is_file():
        return None
    values = dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    if "total" not in values or "fail_under" not in values:
        return None
    return CoverageTotal(values["total"].strip(), values["fail_under"].strip())


def merge_states(states: list[RunStateView]) -> RunStateView:
    """One state for printing: every collected ID, and per ID the worst outcome over the
    reports, since two reports can run the same test and a failure in either must show."""
    merged: RunStateView = run_tests.RunState()
    for state in states:
        merged.collected |= state.collected
        for node, outcome in state.outcomes.items():
            previous = merged.outcomes.get(node, outcome)
            merged.outcomes[node] = max(
                previous, outcome, key=lambda name: OUTCOME_SEVERITY.get(name, 0)
            )
    return merged


def elapsed_seconds(view: RunView) -> float:
    try:
        start = datetime.fromisoformat(view.created_at)
        end = datetime.fromisoformat(view.updated_at)
    except ValueError:
        return 0.0
    return (end - start).total_seconds()


def write_failure_log(
    branch: str, reports: list[GroupReport], failed: set[str]
) -> Path:
    """Each failed node ID and its failure text, in `.sdd-work/`; returns the file."""
    WORK_DIR.mkdir(exist_ok=True)
    path = WORK_DIR / f"remote_full_run_{branch.replace('/', '-')}.txt"
    texts: dict[str, str] = {}
    for report in reports:
        for node, text in report.failures.items():
            texts.setdefault(node, text)
    path.write_text(
        "".join(f"{node}\n{texts.get(node, '')}\n\n" for node in sorted(failed)),
        encoding="utf-8",
    )
    return path


def print_verdict(
    verdict: Verdict,
    reports: list[GroupReport],
    view: RunView,
    branch: str,
    head: str,
    url: str,
) -> None:
    state = merge_states([report.state for report in reports])
    if verdict.failed:
        for line in run_tests.failed_set_lines(state, include_unfinished=True):
            print(line)
    for line in run_tests.count_lines(state, elapsed_seconds(view)):
        print(line)
    if verdict.coverage is not None:
        print(
            f"run: coverage {verdict.coverage.total}% "
            f"below {verdict.coverage.fail_under}%"
        )
    if verdict.failed:
        print(f"run: log {write_failure_log(branch, reports, set(verdict.failed))}")
    print(f"run: tested {head}")
    print(f"run: url {url}")
    print(f"run: RESULT {verdict.result}")


def report_unavailable(reason: str, progress: Progress) -> int:
    """Cancel a run still in progress, then print why there is no verdict."""
    if progress.cancellable:
        cancel = run_tool(["gh", "run", "cancel", progress.run_id])
        if cancel.returncode != 0:
            reason += f" (gh run cancel failed: {first_line(cancel.stderr)})"
    if progress.url:
        print(f"run: url {progress.url}")
    print(f"run: RESULT UNAVAILABLE {reason}")
    return EXIT_UNAVAILABLE


def execute(progress: Progress) -> int:
    settings = load_settings()
    branch = check_preconditions()
    head = push_if_needed(branch)
    progress.run_id, progress.url = dispatch(branch)
    progress.cancellable = True
    print(f"remote: run {progress.url}")
    view = poll(progress.run_id, head, settings)
    progress.cancellable = False
    jobs = list(view.jobs)
    require_test_verdicts(jobs)
    require_verdict_job(jobs)
    with tempfile.TemporaryDirectory() as download_dir:
        directory = Path(download_dir)
        download(progress.run_id, directory)
        reports = {
            job.name: load_group_report(job, directory)
            for job in jobs
            if is_test_job(job)
        }
        verdict = classify(
            jobs,
            {name: report.state for name, report in reports.items()},
            load_coverage_total(directory),
        )
        print_verdict(verdict, list(reports.values()), view, branch, head, progress.url)
    return EXIT_PASS if verdict.result == "PASS" else EXIT_FAIL


def main() -> int:
    progress = Progress()
    try:
        return execute(progress)
    except Unavailable as error:
        return report_unavailable(str(error), progress)


if __name__ == "__main__":
    sys.exit(main())
