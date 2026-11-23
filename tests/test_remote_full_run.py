"""Tests for `claude_plugins/fls-dev/scripts/remote_full_run.py`.

The script runs as a subprocess with `cwd=tmp_path` and a `PATH` holding only stub `gh` and
`git` executables. Each stub answers from a per-test JSON script keyed by the start of its
arguments and logs every call, so no test reaches the network, GitHub or a real repository.
`DS_TEST_TIME_SCALE=0` removes the poll interval. The job-shape rules of the classifier are also
tested directly, where the subprocess adds nothing.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.dev_tooling

SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1] / "claude_plugins" / "fls-dev" / "scripts"
)
SCRIPT = SCRIPTS_DIR / "remote_full_run.py"

HEAD = "a1b2c3d" + "0" * 33
RUN_URL = "https://github.com/octo/repo/actions/runs/777"
CREATED_AT = "2026-01-01T00:00:00Z"
UPDATED_AT = "2026-01-01T00:01:05Z"
UNAVAILABLE_EXIT = 69

# Answers from the JSON script the test wrote: the longest key that starts the joined
# arguments wins, a list of responses is served one call at a time (the last repeats), and
# `files` are written under the directory given after `-D`. `@RUN_TOKEN@` in a response's
# stdout becomes the token the latest `gh workflow run` passed.
STUB_TOOL = f"""#!{sys.executable}
import json
import re
import os
import re
import sys
from pathlib import Path

tool = os.path.basename(sys.argv[0])
line = " ".join(sys.argv[1:])
with open(os.environ["STUB_LOG_FILE"], "a") as log:
    log.write(f"{{tool}} {{line}}\\n")
script_path = Path(os.environ["STUB_SCRIPT"])
answers = json.loads(script_path.read_text())[tool]
keys = [key for key in answers if line.startswith(key)]
if not keys:
    sys.stderr.write(f"stub: no answer for {{tool}} {{line}}\\n")
    sys.exit(127)
key = max(keys, key=len)
state_path = script_path.with_suffix(".state")
served = json.loads(state_path.read_text()) if state_path.exists() else {{}}
index = served.get(f"{{tool}} {{key}}", 0)
served[f"{{tool}} {{key}}"] = index + 1
state_path.write_text(json.dumps(served))
responses = answers[key]
response = responses[min(index, len(responses) - 1)]
if "-D" in sys.argv:
    target = Path(sys.argv[sys.argv.index("-D") + 1])
    for relative, text in response.get("files", {{}}).items():
        (target / relative).parent.mkdir(parents=True, exist_ok=True)
        (target / relative).write_text(text)
stdout = response.get("stdout", "")
tokens = re.findall(r"run_token=(\\S+)", Path(os.environ["STUB_LOG_FILE"]).read_text())
if tokens:
    stdout = stdout.replace("@RUN_TOKEN@", tokens[-1])
sys.stdout.write(stdout)
sys.stderr.write(response.get("stderr", ""))
sys.exit(response.get("status", 0))
"""


def load_remote_full_run() -> ModuleType:
    """The script as a module, imported by path (its sibling `ds_runner` must resolve)."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("remote_full_run", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


remote = load_remote_full_run()


def report_text(
    collected: list[str], failed: dict[str, str] | None = None, passed: bool = True
) -> str:
    """A group report: every collected test passes, except the `failed` ones."""
    failed = failed or {}
    events: list[dict[str, object]] = [
        {"event": "attempt", "n": 1, "k": 1},
        {"event": "collected", "nodeids": collected},
    ]
    events += [
        {"event": "outcome", "nodeid": node, "outcome": "failed", "longrepr": text}
        for node, text in failed.items()
    ]
    events += [
        {"event": "outcome", "nodeid": node, "outcome": "passed"}
        for node in collected
        if passed and node not in failed
    ]
    events.append({"event": "finished", "exitstatus": 1 if failed else 0})
    return "".join(json.dumps(event) + "\n" for event in events)


@dataclass
class JobSpec:
    """One job of the run as `gh run view` lists it, and the report it uploaded."""

    name: str
    conclusion: str = "success"
    failed_step: str | None = None
    report: str | None = None  # None: a passing report for the job's own test
    uploads_report: bool = True

    def node(self) -> str:
        return f"tests/test_{self.name.replace('-', '_')}.py::test_it"

    def report_file(self) -> str | None:
        if not self.uploads_report:
            return None
        if self.report is not None:
            return self.report
        return report_text([self.node()])

    def as_view(self) -> dict[str, object]:
        step = self.failed_step or "Run tests"
        step_conclusion = "failure" if self.failed_step else self.conclusion
        return {
            "name": self.name,
            "status": "completed",
            "conclusion": self.conclusion,
            "steps": [
                {"name": "Set up job", "conclusion": "success"},
                {"name": step, "conclusion": step_conclusion},
            ],
        }


def passing_jobs() -> list[JobSpec]:
    return [
        JobSpec("unit-1"),
        JobSpec("unit-2"),
        JobSpec("playwright-1"),
        JobSpec("standalone-icons", report=report_text(["components/test_icon.py::t"])),
        JobSpec("coverage"),
        JobSpec("test-verdict"),
    ]


def listed_run(title: str, run_id: int = 777) -> dict[str, object]:
    return {
        "databaseId": run_id,
        "displayTitle": title,
        "url": f"https://github.com/octo/repo/actions/runs/{run_id}",
    }


def run_list(*runs: dict[str, object]) -> str:
    return json.dumps(list(runs))


@dataclass
class Scenario:
    """The stub tools' answers for one run of the script."""

    branch: str = "feature"
    jobs: list[JobSpec] = field(default_factory=passing_jobs)
    run_view_head: str = HEAD
    coverage_total: str | None = None
    answers: dict[str, dict[str, list[dict[str, object]]]] = field(default_factory=dict)

    def tool_answers(self) -> dict[str, dict[str, list[dict[str, object]]]]:
        completed = {
            "status": "completed",
            "conclusion": "success",
            "headSha": self.run_view_head,
            "createdAt": CREATED_AT,
            "updatedAt": UPDATED_AT,
            "jobs": [job.as_view() for job in self.jobs],
        }
        files = {
            f"group-report-{job.name}/group-report.jsonl": text
            for job in self.jobs
            if (text := job.report_file()) is not None
            and job.name not in {"coverage", "test-verdict"}
        }
        if self.coverage_total is not None:
            files["coverage-total/coverage_total.txt"] = self.coverage_total
        defaults: dict[str, dict[str, list[dict[str, object]]]] = {
            "git": {
                "status": [{}],
                "symbolic-ref": [{"stdout": f"{self.branch}\n"}],
                "rev-parse HEAD": [{"stdout": f"{HEAD}\n"}],
                "rev-parse --abbrev-ref": [{}],
                "ls-remote": [{"stdout": f"{HEAD}\trefs/heads/{self.branch}\n"}],
                "merge-base --is-ancestor": [{}],
                "push": [{}],
            },
            "gh": {
                "auth status": [{}],
                "workflow run": [{}],
                "run list": [{"stdout": run_list(listed_run("@RUN_TOKEN@"))}],
                "run view": [{"stdout": json.dumps(completed)}],
                "run download": [{"files": files}],
                "run cancel": [{}],
            },
        }
        for tool, tool_defaults in defaults.items():
            tool_defaults.update(self.answers.get(tool, {}))
        return defaults

    def answer(self, tool: str, key: str, *responses: dict[str, object]) -> None:
        self.answers.setdefault(tool, {})[key] = list(responses)


@dataclass
class Outcome:
    process: subprocess.CompletedProcess[str]
    calls: list[str]
    cwd: Path

    @property
    def lines(self) -> list[str]:
        return self.process.stdout.splitlines()


def run_script(
    scenario: Scenario,
    cwd: Path,
    pyproject: str = "",
    with_gh: bool = True,
) -> Outcome:
    bin_dir = cwd / "bin"
    bin_dir.mkdir()
    for tool in ("git", "gh") if with_gh else ("git",):
        (bin_dir / tool).write_text(STUB_TOOL)
        (bin_dir / tool).chmod(0o755)
    script_file = cwd / "stub_script.json"
    script_file.write_text(json.dumps(scenario.tool_answers()))
    (cwd / "pyproject.toml").write_text(pyproject)
    log = cwd / "calls.log"
    process = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT)],
        cwd=cwd,
        env={
            "PATH": str(bin_dir),
            "DS_TEST_TIME_SCALE": "0",
            "STUB_LOG_FILE": str(log),
            "STUB_SCRIPT": str(script_file),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return Outcome(process, calls, cwd)


def unavailable_line(outcome: Outcome) -> str:
    return next(line for line in outcome.lines if "RESULT" in line)


def runs_started(outcome: Outcome) -> list[str]:
    return [call for call in outcome.calls if call.startswith("gh workflow run")]


def test_a_pass_prints_the_run_url_first_and_the_closing_lines_last(
    tmp_path: Path,
) -> None:
    outcome = run_script(Scenario(), tmp_path)

    assert outcome.lines[0] == f"remote: run {RUN_URL}"
    assert outcome.lines[-3:] == [
        f"run: tested {HEAD}",
        f"run: url {RUN_URL}",
        "run: RESULT PASS",
    ]


def test_a_pass_exits_zero(tmp_path: Path) -> None:
    outcome = run_script(Scenario(), tmp_path)

    assert outcome.process.returncode == 0


def test_a_pass_prints_a_line_per_job_between_the_run_url_and_the_closing_lines(
    tmp_path: Path,
) -> None:
    outcome = run_script(Scenario(), tmp_path)

    assert "remote: unit-1 success" in outcome.lines[1:-3]


def test_a_pass_prints_the_runner_count_lines_with_the_run_duration(
    tmp_path: Path,
) -> None:
    outcome = run_script(Scenario(), tmp_path)

    assert (
        "run: summary (merged): 4 passed, 0 failed, 0 skipped in 65.0s" in outcome.lines
    )


@pytest.mark.parametrize(
    ("scenario_edit", "reason"),
    [
        ("dirty", "tracked files have uncommitted changes"),
        ("detached", "HEAD is detached"),
        ("no_auth", "gh is not logged in"),
    ],
)
def test_a_failed_precondition_is_unavailable_and_dispatches_nothing(
    tmp_path: Path, scenario_edit: str, reason: str
) -> None:
    scenario = Scenario()
    edits = {
        "dirty": lambda: scenario.answer("git", "status", {"stdout": " M a.py\n"}),
        "detached": lambda: scenario.answer("git", "symbolic-ref", {"status": 1}),
        "no_auth": lambda: scenario.answer("gh", "auth status", {"status": 1}),
    }
    edits[scenario_edit]()

    outcome = run_script(scenario, tmp_path)

    assert (
        outcome.process.returncode,
        unavailable_line(outcome),
        runs_started(outcome),
    ) == (UNAVAILABLE_EXIT, f"run: RESULT UNAVAILABLE {reason}", [])


def test_an_unexpected_error_is_unavailable_with_a_result_line(tmp_path: Path) -> None:
    outcome = run_script(Scenario(), tmp_path, pyproject="[tool.test_tiers.remote\n")

    assert (
        outcome.process.returncode,
        outcome.lines[-1].startswith("run: RESULT UNAVAILABLE TOMLDecodeError: "),
    ) == (UNAVAILABLE_EXIT, True)


def test_a_missing_gh_is_unavailable_and_dispatches_nothing(tmp_path: Path) -> None:
    outcome = run_script(Scenario(), tmp_path, with_gh=False)

    assert (outcome.process.returncode, unavailable_line(outcome)) == (
        UNAVAILABLE_EXIT,
        "run: RESULT UNAVAILABLE gh is not installed",
    )


def test_an_untracked_file_alone_does_not_stop_the_run(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer("git", "status --porcelain --untracked-files=no", {"stdout": ""})

    outcome = run_script(scenario, tmp_path)

    assert "git status --porcelain --untracked-files=no" in outcome.calls
    assert outcome.lines[-1] == "run: RESULT PASS"


def test_main_missing_from_origin_is_unavailable_and_never_pushed(
    tmp_path: Path,
) -> None:
    scenario = Scenario(branch="main")
    scenario.answer("git", "ls-remote", {"stdout": ""})

    outcome = run_script(scenario, tmp_path)

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE origin/main lacks HEAD and main is never pushed from here"
    )
    assert [call for call in outcome.calls if call.startswith("git push")] == []


def test_main_that_origin_has_is_dispatched(tmp_path: Path) -> None:
    outcome = run_script(Scenario(branch="main"), tmp_path)

    assert [call.split(" -f ")[0] for call in runs_started(outcome)] == [
        "gh workflow run tests.yml --ref=main"
    ]


def test_a_rejected_push_is_unavailable_and_names_the_rejection(
    tmp_path: Path,
) -> None:
    scenario = Scenario()
    scenario.answer("git", "ls-remote", {"stdout": ""})
    scenario.answer(
        "git", "push", {"status": 1, "stderr": "! [rejected] feature\nmore"}
    )

    outcome = run_script(scenario, tmp_path)

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE push rejected: ! [rejected] feature"
    )


def test_an_origin_branch_that_head_does_not_contain_is_unavailable_and_not_pushed(
    tmp_path: Path,
) -> None:
    scenario = Scenario()
    scenario.answer("git", "ls-remote", {"stdout": "f" * 40 + "\trefs/heads/feature\n"})
    scenario.answer("git", "merge-base --is-ancestor", {"status": 1})

    outcome = run_script(scenario, tmp_path)

    assert (
        unavailable_line(outcome),
        [call for call in outcome.calls if call.startswith("git push")],
    ) == (
        "run: RESULT UNAVAILABLE origin/feature has diverged from HEAD; "
        "push it with --force-with-lease first",
        [],
    )


def test_the_push_is_a_plain_push_of_head_without_force(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer("git", "ls-remote", {"stdout": ""})

    outcome = run_script(scenario, tmp_path)

    assert [call for call in outcome.calls if call.startswith("git push")] == [
        "git push origin HEAD:refs/heads/feature"
    ]


def test_a_branch_without_an_upstream_is_pushed_with_u(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer("git", "ls-remote", {"stdout": ""})
    scenario.answer("git", "rev-parse --abbrev-ref", {"status": 128})

    outcome = run_script(scenario, tmp_path)

    assert [call for call in outcome.calls if call.startswith("git push")] == [
        "git push -u origin HEAD:refs/heads/feature"
    ]


def test_an_origin_already_at_head_is_not_pushed_to(tmp_path: Path) -> None:
    outcome = run_script(Scenario(), tmp_path)

    assert [call for call in outcome.calls if call.startswith("git push")] == []


def test_an_unreachable_origin_is_unavailable(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer("git", "ls-remote", {"status": 128})

    outcome = run_script(scenario, tmp_path)

    assert unavailable_line(outcome) == "run: RESULT UNAVAILABLE cannot reach origin"


def test_the_dispatch_passes_a_run_token(tmp_path: Path) -> None:
    outcome = run_script(Scenario(), tmp_path)

    (started,) = runs_started(outcome)
    assert re.fullmatch(
        r"gh workflow run tests\.yml --ref=feature -f run_token=[0-9a-f]{32}", started
    )


def test_the_run_is_listed_by_branch_and_dispatch_event(tmp_path: Path) -> None:
    outcome = run_script(Scenario(), tmp_path)

    (listing,) = [call for call in outcome.calls if call.startswith("gh run list")]
    assert "--workflow=tests.yml --branch=feature --event=workflow_dispatch" in listing


def test_a_failed_dispatch_is_unavailable_and_names_the_error(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer(
        "gh", "workflow run", {"status": 1, "stderr": "HTTP 404: Not Found\n"}
    )

    outcome = run_script(scenario, tmp_path)

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE gh workflow run failed: HTTP 404: Not Found"
    )


def test_a_run_listed_only_on_a_later_listing_is_found(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer(
        "gh",
        "run list",
        {"stdout": run_list()},
        {"status": 1},
        {"stdout": run_list(listed_run("@RUN_TOKEN@"))},
    )

    outcome = run_script(scenario, tmp_path)

    assert (outcome.lines[0], outcome.lines[-1]) == (
        f"remote: run {RUN_URL}",
        "run: RESULT PASS",
    )


def test_the_run_titled_with_this_dispatchs_token_is_the_one_followed(
    tmp_path: Path,
) -> None:
    scenario = Scenario()
    scenario.answer(
        "gh",
        "run list",
        {
            "stdout": run_list(
                listed_run("another-dispatchs-token", 888),
                listed_run("@RUN_TOKEN@"),
            )
        },
    )

    outcome = run_script(scenario, tmp_path)

    views = [call for call in outcome.calls if call.startswith("gh run view")]
    assert (outcome.lines[0], {view.split()[3] for view in views}) == (
        f"remote: run {RUN_URL}",
        {"777"},
    )


def test_a_dispatched_run_that_never_appears_is_unavailable_and_named_by_its_title(
    tmp_path: Path,
) -> None:
    scenario = Scenario()
    scenario.answer("gh", "run list", {"stdout": run_list()})

    outcome = run_script(scenario, tmp_path)

    token = re.findall(r"run_token=(\S+)", "\n".join(runs_started(outcome)))[-1]
    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE the dispatched run did not appear in gh run list; "
        f"it may still be running on GitHub, titled {token}"
    )


def test_a_run_that_tests_another_commit_is_unavailable_and_cancelled(
    tmp_path: Path,
) -> None:
    outcome = run_script(Scenario(run_view_head="f" * 40), tmp_path)

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE run 777 tests fffffff, not HEAD a1b2c3d"
    )
    assert "gh run cancel 777" in outcome.calls


def queued_view(
    status: str, job_status: str, *other_jobs: dict[str, object]
) -> dict[str, object]:
    return {
        "stdout": json.dumps(
            {
                "status": status,
                "conclusion": "",
                "headSha": HEAD,
                "createdAt": CREATED_AT,
                "updatedAt": UPDATED_AT,
                "jobs": [
                    *other_jobs,
                    {"name": "unit-1", "status": job_status, "steps": []},
                ],
            }
        )
    }


def skipped_job(name: str) -> dict[str, object]:
    """A job its `if:` skips on a dispatch: completed at once, with no runner."""
    return {"name": name, "status": "completed", "conclusion": "skipped", "steps": []}


def test_skipped_non_test_jobs_do_not_count_as_a_started_run(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer(
        "gh",
        "run view",
        queued_view("queued", "queued", skipped_job("lint"), skipped_job("type-check")),
    )

    outcome = run_script(
        scenario, tmp_path, pyproject="[tool.test_tiers.remote]\nstart_timeout_s = 1\n"
    )

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE no job started within 1 s"
    )
    assert "gh run cancel 777" in outcome.calls


def test_a_run_whose_jobs_never_start_is_cancelled_when_the_start_budget_ends(
    tmp_path: Path,
) -> None:
    scenario = Scenario()
    scenario.answer("gh", "run view", queued_view("queued", "queued"))

    outcome = run_script(
        scenario, tmp_path, pyproject="[tool.test_tiers.remote]\nstart_timeout_s = 1\n"
    )

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE no job started within 1 s"
    )
    assert "gh run cancel 777" in outcome.calls


def test_a_run_that_outlasts_the_run_budget_is_cancelled(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer("gh", "run view", queued_view("in_progress", "in_progress"))

    outcome = run_script(
        scenario, tmp_path, pyproject="[tool.test_tiers.remote]\nrun_timeout_s = 1\n"
    )

    assert unavailable_line(outcome) == "run: RESULT UNAVAILABLE run exceeded 1 s"
    assert "gh run cancel 777" in outcome.calls


def test_a_failed_cancel_is_named_in_the_reason(tmp_path: Path) -> None:
    scenario = Scenario(run_view_head="f" * 40)
    scenario.answer("gh", "run cancel", {"status": 1, "stderr": "HTTP 403\n"})

    outcome = run_script(scenario, tmp_path)

    assert unavailable_line(outcome).endswith("(gh run cancel failed: HTTP 403)")


def test_three_failed_views_in_a_row_are_unavailable(tmp_path: Path) -> None:
    scenario = Scenario()
    scenario.answer("gh", "run view", {"status": 1})

    outcome = run_script(scenario, tmp_path)

    assert unavailable_line(outcome) == "run: RESULT UNAVAILABLE GitHub unreachable"


def test_a_view_that_recovers_after_one_failure_is_not_unreachable(
    tmp_path: Path,
) -> None:
    scenario = Scenario()
    completed = scenario.tool_answers()["gh"]["run view"][0]
    scenario.answer("gh", "run view", {"status": 1}, completed)

    outcome = run_script(scenario, tmp_path)

    assert outcome.lines[-1] == "run: RESULT PASS"


UNIT_FAILURE = {"tests/test_unit_1.py::test_it": "AssertionError: 1 != 2"}


def failing_unit_jobs() -> list[JobSpec]:
    jobs = passing_jobs()
    jobs[0] = JobSpec(
        "unit-1",
        conclusion="failure",
        failed_step="Run tests",
        report=report_text(["tests/test_unit_1.py::test_it"], UNIT_FAILURE),
    )
    jobs[-2] = JobSpec(
        "coverage", conclusion="failure", failed_step="Check combined coverage"
    )
    jobs[-1] = JobSpec(
        "test-verdict",
        conclusion="failure",
        failed_step="Check every test job succeeded",
    )
    return jobs


def test_a_test_failure_prints_the_quoted_node_id_and_fails(tmp_path: Path) -> None:
    outcome = run_script(Scenario(jobs=failing_unit_jobs()), tmp_path)

    assert "run: failed tests/test_unit_1.py::test_it" in outcome.lines
    assert (outcome.process.returncode, outcome.lines[-1]) == (1, "run: RESULT FAIL")


def test_a_node_id_with_a_space_is_printed_shell_quoted(tmp_path: Path) -> None:
    jobs = failing_unit_jobs()
    node = "tests/test_unit_1.py::test_it[a b]"
    jobs[0].report = report_text([node], {node: "boom"})

    outcome = run_script(Scenario(jobs=jobs), tmp_path)

    assert f"run: failed '{node}'" in outcome.lines


def test_a_test_failure_writes_its_text_to_the_log_and_prints_the_path(
    tmp_path: Path,
) -> None:
    outcome = run_script(Scenario(jobs=failing_unit_jobs()), tmp_path)

    log = tmp_path / ".sdd-work" / "remote_full_run_feature.txt"
    assert "AssertionError: 1 != 2" in log.read_text()
    assert (
        f"run: log {Path('.sdd-work') / 'remote_full_run_feature.txt'}" in outcome.lines
    )


def test_a_branch_with_a_slash_is_logged_under_a_dashed_name(tmp_path: Path) -> None:
    run_script(Scenario(branch="feature/x", jobs=failing_unit_jobs()), tmp_path)

    assert (tmp_path / ".sdd-work" / "remote_full_run_feature-x.txt").is_file()


def failing_standalone_jobs() -> list[JobSpec]:
    jobs = passing_jobs()
    jobs[3] = JobSpec(
        "standalone-icons",
        conclusion="failure",
        failed_step="Run tests",
        report=report_text(
            ["components/test_icon.py::t"], {"components/test_icon.py::t": "boom"}
        ),
    )
    jobs[-1] = JobSpec(
        "test-verdict",
        conclusion="failure",
        failed_step="Check every test job succeeded",
    )
    return jobs


STANDALONE_NODE = "freedom_ls/icons/tests/components/test_icon.py::t"
STANDALONE_CONFIG = "freedom_ls/icons/tests/standalone_pytest.ini"


def test_a_standalone_failure_prints_the_node_id_with_the_app_test_directory_prefix(
    tmp_path: Path,
) -> None:
    outcome = run_script(Scenario(jobs=failing_standalone_jobs()), tmp_path)

    assert f"run: failed {STANDALONE_NODE}" in outcome.lines


def test_a_standalone_failure_prints_its_re_run_command_with_the_standalone_config(
    tmp_path: Path,
) -> None:
    outcome = run_script(Scenario(jobs=failing_standalone_jobs()), tmp_path)

    assert (
        "remote: standalone-icons failures re-run with: "
        f"uv run pytest -c {STANDALONE_CONFIG} {STANDALONE_NODE}"
    ) in outcome.lines


def test_a_standalone_failure_names_its_config_in_the_log(tmp_path: Path) -> None:
    run_script(Scenario(jobs=failing_standalone_jobs()), tmp_path)

    log = (tmp_path / ".sdd-work" / "remote_full_run_feature.txt").read_text()
    assert (
        f"{STANDALONE_NODE}\n(standalone-icons: run with -c {STANDALONE_CONFIG})\nboom"
        in log
    )


def test_a_unit_failure_prints_no_standalone_re_run_command(tmp_path: Path) -> None:
    outcome = run_script(Scenario(jobs=failing_unit_jobs()), tmp_path)

    assert not [line for line in outcome.lines if "re-run with" in line]


def test_a_test_failing_in_two_reports_is_counted_once(tmp_path: Path) -> None:
    jobs = failing_unit_jobs()
    shared = "tests/test_shared.py::test_it"
    jobs[0].report = report_text([shared], {shared: "boom"})
    jobs[1] = JobSpec(
        "unit-2",
        conclusion="failure",
        failed_step="Run tests",
        report=report_text([shared], {shared: "boom"}),
    )

    outcome = run_script(Scenario(jobs=jobs), tmp_path)

    assert [line for line in outcome.lines if line.startswith("run: failed ")] == [
        f"run: failed {shared}"
    ]


def coverage_failing_jobs() -> list[JobSpec]:
    jobs = passing_jobs()
    jobs[-2] = JobSpec(
        "coverage", conclusion="failure", failed_step="Check combined coverage"
    )
    jobs[-1] = JobSpec(
        "test-verdict",
        conclusion="failure",
        failed_step="Check every test job succeeded",
    )
    return jobs


def test_a_coverage_failure_prints_the_percentages_and_no_failed_test(
    tmp_path: Path,
) -> None:
    scenario = Scenario(
        jobs=coverage_failing_jobs(), coverage_total="total=91\nfail_under=92\n"
    )

    outcome = run_script(scenario, tmp_path)

    assert "run: coverage 91% below 92%" in outcome.lines
    assert [line for line in outcome.lines if line.startswith("run: failed")] == []
    assert (outcome.process.returncode, outcome.lines[-1]) == (1, "run: RESULT FAIL")


def test_a_coverage_failure_after_a_unit_group_retried_is_unavailable(
    tmp_path: Path,
) -> None:
    jobs = coverage_failing_jobs()
    retried = report_text([jobs[0].node()]) + "".join(
        json.dumps(event) + "\n"
        for event in (
            {"event": "attempt", "n": 2, "k": 1},
            {"event": "finished", "exitstatus": 0},
        )
    )
    jobs[0] = replace(jobs[0], report=retried)
    scenario = Scenario(jobs=jobs, coverage_total="total=91\nfail_under=92\n")

    outcome = run_script(scenario, tmp_path)

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE coverage incomplete: unit-1 retried after a crash"
    )


def test_a_coverage_failure_without_a_coverage_total_is_unavailable(
    tmp_path: Path,
) -> None:
    outcome = run_script(Scenario(jobs=coverage_failing_jobs()), tmp_path)

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE coverage failed and uploaded no coverage-total"
    )


def with_job(name: str, **changes: object) -> list[JobSpec]:
    """The passing jobs with the job `name` replaced by a changed copy."""
    return [
        replace(job, **changes) if job.name == name else job for job in passing_jobs()
    ]


INCOMPLETE_REPORT = report_text(["tests/test_unit_1.py::test_it"], passed=False)

UNAVAILABLE_SHAPES = {
    "a coverage job failing at its presence step": (
        with_job(
            "coverage",
            conclusion="failure",
            failed_step="Check every group's coverage data is present",
        ),
        "coverage failure at Check every group's coverage data is present",
    ),
    "a failed partition step": (
        with_job(
            "test-verdict", conclusion="failure", failed_step="Check the partition"
        ),
        "test-verdict failure at Check the partition",
    ),
    "a cancelled test job": (
        with_job("unit-1", conclusion="cancelled"),
        "unit-1 cancelled",
    ),
    "a test job failing at a setup step": (
        with_job("unit-1", conclusion="failure", failed_step="Install uv"),
        "unit-1 failure at Install uv",
    ),
    "a missing group report": (
        with_job("unit-1", uploads_report=False),
        "unit-1 uploaded no group report",
    ),
    "a test job failing with only unfinished tests": (
        with_job(
            "unit-1",
            conclusion="failure",
            failed_step="Run tests",
            report=INCOMPLETE_REPORT,
        ),
        "unit-1 failed with no failed test",
    ),
    "test-verdict failing at a setup step": (
        with_job("test-verdict", conclusion="failure", failed_step="Install uv"),
        "test-verdict failure at Install uv",
    ),
}


@pytest.mark.parametrize(
    ("jobs", "reason"), UNAVAILABLE_SHAPES.values(), ids=UNAVAILABLE_SHAPES.keys()
)
def test_a_run_without_a_test_verdict_is_unavailable(
    tmp_path: Path, jobs: list[JobSpec], reason: str
) -> None:
    outcome = run_script(Scenario(jobs=jobs), tmp_path)

    assert (outcome.process.returncode, unavailable_line(outcome)) == (
        UNAVAILABLE_EXIT,
        f"run: RESULT UNAVAILABLE {reason}",
    )


def test_a_malformed_group_report_is_unavailable(tmp_path: Path) -> None:
    jobs = with_job("unit-1", report="not json\n" + report_text(["a::b"]))

    outcome = run_script(Scenario(jobs=jobs), tmp_path)

    assert unavailable_line(outcome) == (
        "run: RESULT UNAVAILABLE unit-1 group report is malformed"
    )


def test_the_download_directory_is_removed_after_an_unavailable_run(
    tmp_path: Path,
) -> None:
    jobs = with_job("unit-1", report="not json\n" + report_text(["a::b"]))

    outcome = run_script(Scenario(jobs=jobs), tmp_path)

    download = next(
        call for call in outcome.calls if call.startswith("gh run download")
    )
    directory = Path(download.split()[download.split().index("-D") + 1])
    assert not directory.exists()


def test_failures_past_the_runner_cap_print_the_runners_and_more_line(
    tmp_path: Path,
) -> None:
    extra = 3
    nodes = [
        f"tests/test_many.py::test_{index}"
        for index in range(remote.run_tests.FAILED_SET_LINE_LIMIT + extra)
    ]
    jobs = failing_unit_jobs()
    jobs[0].report = report_text(nodes, dict.fromkeys(nodes, "boom"))

    outcome = run_script(Scenario(jobs=jobs), tmp_path)

    assert f"run: failed ... and {extra} more" in outcome.lines


def verdict_jobs(*, verdict_step: str | None, verdict_conclusion: str) -> list[object]:
    return [
        remote.Job(
            "test-verdict",
            "completed",
            verdict_conclusion,
            (remote.Step(verdict_step or "Run tests", verdict_conclusion),),
        )
    ]


def test_a_verdict_job_failing_only_its_job_check_has_a_verdict() -> None:
    jobs = verdict_jobs(
        verdict_step="Check every test job succeeded", verdict_conclusion="failure"
    )

    assert remote.require_verdict_job(jobs) is None


def test_a_verdict_job_failing_at_a_setup_step_has_no_verdict() -> None:
    jobs = verdict_jobs(verdict_step="Install uv", verdict_conclusion="failure")

    with pytest.raises(remote.Unavailable, match="test-verdict failure at Install uv"):
        remote.require_verdict_job(jobs)


def test_a_bug_is_raised_not_reported_unavailable_and_the_run_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    progress = remote.Progress(url=RUN_URL, run_id="777", cancellable=True)

    def execute(_progress: object) -> int:
        raise KeyError("a bug")

    def run_tool(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(remote, "Progress", lambda: progress)
    monkeypatch.setattr(remote, "execute", execute)
    monkeypatch.setattr(remote, "run_tool", run_tool)

    with pytest.raises(KeyError):
        remote.main()
    assert calls == [["gh", "run", "cancel", "777"]]
