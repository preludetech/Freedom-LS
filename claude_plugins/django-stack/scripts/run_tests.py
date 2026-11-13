#!/usr/bin/env python3
# ruff: noqa: T201
"""Run one pytest command with an xdist worker count sized to the memory that is free.

Usage:
    python run_tests.py <pytest command...>
    python run_tests.py --capacity <unit-mb>

The command must start with `pytest`, `python -m pytest`, `python3 -m pytest`,
`uv run pytest` or `uv run --directory <dir> pytest`; anything else exits 2. When the
command has an xdist `-n` option, the runner appends its own `-n <k>`, which pytest
reads last. A number the command gives is a ceiling on `k`, and `-n 0` stays serial.
A pytest attempt that crashes (an xdist worker dies, or the controller is killed) is
retried for the tests that never finished, and the run ends in one verdict line. A
pytest that exits before its session starts (a usage error) is not retried. Setting `DS_TEST_MEMORY_GUARD=off` runs the command unchanged. `--capacity`
prints how many units of `<unit-mb>` fit in free memory, at least 1.

Each setting comes from its environment variable, then from `[tool.test_tiers.memory]` in
`pyproject.toml`, then from the default. Stdlib only, like its siblings.
"""

from __future__ import annotations

import contextlib
import ctypes
import functools
import importlib.util
import io
import json
import math
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# None matches any single token: the directory `uv run --directory` is given.
ACCEPTED_PREFIXES: tuple[tuple[str | None, ...], ...] = (
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("uv", "run", "pytest"),
    ("uv", "run", "--directory", None, "pytest"),
)

# Printed by `--capacity` when free memory cannot be read: large enough never to limit a caller.
UNKNOWN_CAPACITY = 999

# key -> (env var, type, default, minimum). The single list of keys: anything else in
# [tool.test_tiers.memory] is an unknown key. A per-worker memory or worker ceiling of 0
# would divide by zero or allow no worker, so those two need at least 1.
SETTINGS: dict[str, tuple[str, type[int] | type[float], float, int | None]] = {
    "per_worker_mb": ("DS_TEST_PER_WORKER_MB", int, 1024, 1),
    "reserve_mb": ("DS_TEST_RESERVE_MB", int, 2048, None),
    "max_workers": ("DS_TEST_MAX_WORKERS", int, os.cpu_count() or 1, 1),
    "psi_some_avg10_limit": ("DS_TEST_PSI_LIMIT", float, 10.0, None),
    "wait_timeout_s": ("DS_TEST_WAIT_TIMEOUT_S", int, 600, None),
    "max_retries": ("DS_TEST_MAX_RETRIES", int, 2, None),
    "oom_score_adj": ("DS_TEST_OOM_SCORE_ADJ", int, 500, None),
}

# `-nauto`, `-n4`: the attached form, which must not match other `-n...` flags like `-no:cacheprovider`.
NUMPROCESSES_ATTACHED = re.compile(r"-n(auto|logical|\d+)")

WORKER_FLAGS = frozenset({"-n", "--numprocesses"})

OOM_SCORE_FILE = Path("/proc/self/oom_score_adj")
PR_SET_CHILD_SUBREAPER = 36
# Real time, not `scaled`: a test run with `DS_TEST_TIME_SCALE=0` still cleans up.
KILL_DEADLINE_S = 5

# Node-id files written for retries and not yet deleted, so a signal handler can remove them.
LIVE_NODE_ID_FILES: list[Path] = []

DEFAULT_MEMINFO = Path("/proc/meminfo")
DEFAULT_PSI = Path("/proc/pressure/memory")

# Seconds to back off before the first and the second crash retry; later retries reuse the last.
BACKOFF_S = (30, 60)

# pytest's exit code for "tests ran and some failed", and the code this runner exits with when
# retries ran out with tests unfinished (EX_TEMPFAIL: neither a pass nor a code defect).
EXIT_TESTS_FAILED = 1
EXIT_INCOMPLETE = 75

# Seconds between memory polls while waiting, and between progress lines.
POLL_INTERVAL_S = 5
HEARTBEAT_INTERVAL_S = 60
# The first attempt sleeps up to this long so runners started together read different figures.
MAX_START_JITTER_S = 5


class ConfigError(Exception):
    """A malformed `[tool.test_tiers.memory]` table or memory environment variable."""


@dataclass(frozen=True)
class MemorySettings:
    per_worker_mb: int
    reserve_mb: int
    max_workers: int
    psi_some_avg10_limit: float
    wait_timeout_s: int
    max_retries: int
    oom_score_adj: int
    # Setting name -> "env" or "pyproject", for each setting that is not the default.
    sources: dict[str, str] = field(default_factory=dict)


def type_noun(kind: type[int] | type[float]) -> str:
    return "an integer" if kind is int else "a number"


def check_value(value: object, kind: type[int] | type[float]) -> int | float | None:
    """The value as `kind`, or None when it is the wrong type. A bool is never a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return kind(value)
    if kind is float and isinstance(value, float):
        return value
    return None


def parse_env_value(name: str, text: str, kind: type[int] | type[float]) -> int | float:
    try:
        return kind(text)
    except ValueError:
        raise ConfigError(f"{name} must be {type_noun(kind)}") from None


def read_memory_table(project_root: Path) -> dict[str, object]:
    """The `[tool.test_tiers.memory]` table. A missing file, `[tool]` or `[tool.test_tiers]`
    leaves the defaults, as the tier config does."""
    try:
        data = tomllib.loads((project_root / "pyproject.toml").read_text("utf-8"))
    except FileNotFoundError:
        return {}
    table = data.get("tool", {}).get("test_tiers", {}).get("memory", {})
    if not isinstance(table, dict):
        raise ConfigError("[tool.test_tiers] 'memory' must be a table")
    for key in table:
        if key not in SETTINGS:
            raise ConfigError(f"[tool.test_tiers.memory] unknown key '{key}'")
    return table


def load_memory_settings(
    project_root: Path, environ: Mapping[str, str]
) -> MemorySettings:
    """Resolve each setting: environment variable, then pyproject, then the default."""
    table = read_memory_table(project_root)
    values: dict[str, int | float] = {}
    sources: dict[str, str] = {}
    for key, (env_name, kind, default, minimum) in SETTINGS.items():
        if env_name in environ:
            value = parse_env_value(env_name, environ[env_name], kind)
            origin, label = "env", env_name
        elif key in table:
            checked = check_value(table[key], kind)
            if checked is None:
                raise ConfigError(
                    f"[tool.test_tiers.memory] '{key}' must be {type_noun(kind)}"
                )
            value = checked
            origin, label = "pyproject", f"[tool.test_tiers.memory] '{key}'"
        else:
            values[key] = kind(default)
            continue
        if minimum is not None and value < minimum:
            raise ConfigError(f"{label} must be at least {minimum}")
        values[key] = value
        sources[key] = origin
    return MemorySettings(
        per_worker_mb=int(values["per_worker_mb"]),
        reserve_mb=int(values["reserve_mb"]),
        max_workers=int(values["max_workers"]),
        psi_some_avg10_limit=float(values["psi_some_avg10_limit"]),
        wait_timeout_s=int(values["wait_timeout_s"]),
        max_retries=int(values["max_retries"]),
        oom_score_adj=int(values["oom_score_adj"]),
        sources=sources,
    )


def is_pytest_command(argv: list[str]) -> bool:
    """Whether argv starts with one of the accepted forms, compared token for token.

    Bare names only: a path such as `/tmp/x/pytest` is refused, because the wrapper is
    allowed prompt-free and must not run a caller-chosen executable. The flags after the
    prefix are pytest's own and are passed through, as a direct pytest call would take them.
    """
    return any(
        len(argv) >= len(prefix)
        and all(
            expected is None or token == expected
            for token, expected in zip(argv, prefix, strict=False)
        )
        for prefix in ACCEPTED_PREFIXES
    )


def run_plain(argv: list[str]) -> int:
    """Run the command as given and return its exit code."""
    return subprocess.run(argv, check=False).returncode  # noqa: S603


def meminfo_path() -> Path:
    return Path(os.environ.get("DS_TEST_MEMINFO_PATH") or DEFAULT_MEMINFO)


def mem_available_mb(meminfo: Path) -> int | None:
    """MemAvailable in MB, or None when the file is missing (no /proc on this platform)."""
    try:
        text = meminfo.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return None


def psi_path() -> Path:
    return Path(os.environ.get("DS_TEST_PSI_PATH") or DEFAULT_PSI)


def psi_some_avg10(path: Path) -> float | None:
    """The `avg10` figure of the `some` line, or None when the file is missing."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    for line in text.splitlines():
        if line.startswith("some "):
            for field_text in line.split()[1:]:
                name, _, value = field_text.partition("=")
                if name == "avg10":
                    return float(value)
    return None


def format_psi(psi: float | None) -> str:
    return "PSI n/a" if psi is None else f"PSI {psi}"


def scaled(seconds: float) -> float:
    """`seconds` times `DS_TEST_TIME_SCALE`, which lets tests shrink every wait."""
    return seconds * float(os.environ.get("DS_TEST_TIME_SCALE") or 1)


def worker_fit(available_mb: int, reserve_mb: int, per_worker_mb: int) -> int:
    """How many workers fit once `reserve_mb` is left free. Zero or negative: none."""
    return (available_mb - reserve_mb) // per_worker_mb


def wait_for_memory(settings: MemorySettings, ceiling: int, first_attempt: bool) -> int:
    """The xdist worker count to run with, after waiting for memory when it is short."""
    if first_attempt:
        # Worktrees started together would otherwise all read the same free figure.
        time.sleep(scaled(random.uniform(0, MAX_START_JITTER_S)))  # noqa: S311
    started = time.monotonic()
    announced_at: float | None = None
    while True:
        available = mem_available_mb(meminfo_path())
        if available is None:
            return ceiling
        fit = worker_fit(available, settings.reserve_mb, settings.per_worker_mb)
        psi = psi_some_avg10(psi_path())
        if fit >= 1 and (psi is None or psi <= settings.psi_some_avg10_limit):
            if announced_at is not None:
                print(f"ram: wait over after {time.monotonic() - started:.0f} s")
            return min(fit, ceiling)
        now = time.monotonic()
        if now - started >= scaled(settings.wait_timeout_s):
            print(
                f"ram: still short after {settings.wait_timeout_s} s; running with -n 1"
            )
            return 1
        if announced_at is None or now - announced_at >= scaled(HEARTBEAT_INTERVAL_S):
            announced_at = now
            print(
                f"ram: waiting for memory (MemAvailable {available} MB, "
                f"{format_psi(psi)})"
            )
        time.sleep(scaled(POLL_INTERVAL_S))


def requested_workers(argv: list[str]) -> str | None:
    """The worker count the command asks xdist for, or None when it has no worker option.

    Reads `-n <x>`, `-n<x>`, `--numprocesses <x>` and `--numprocesses=<x>`. The last one
    wins, as it does for pytest.
    """
    value: str | None = None
    for index, arg in enumerate(argv):
        attached = NUMPROCESSES_ATTACHED.fullmatch(arg)
        if arg in WORKER_FLAGS:
            value = argv[index + 1] if index + 1 < len(argv) else ""
        elif attached is not None:
            value = attached.group(1)
        elif arg.startswith("--numprocesses="):
            value = arg.partition("=")[2]
    return value


def distributes(argv: list[str]) -> bool:
    """Whether the command runs its tests on xdist workers. `-n 0` asks for none."""
    return requested_workers(argv) not in (None, "0")


def worker_ceiling(argv: list[str], max_workers: int) -> int:
    """The most workers a run may use: a count the command names is never exceeded."""
    requested = requested_workers(argv)
    if requested is not None and requested.isascii() and requested.isdigit():
        return max(1, min(max_workers, int(requested)))
    return max_workers


def describe_sources(settings: MemorySettings) -> str:
    """` (key=value from source, ...)` for each setting that is not the default."""
    parts = [
        f"{key}={getattr(settings, key)} from {origin}"
        for key, origin in settings.sources.items()
    ]
    return f" ({', '.join(parts)})" if parts else ""


def print_capacity(unit_text: str, settings: MemorySettings) -> int:
    """Print how many units of `unit_text` MB fit in free memory, never fewer than 1."""
    if not unit_text.isascii() or not unit_text.isdigit() or int(unit_text) < 1:
        print("--capacity takes a positive integer number of MB", file=sys.stderr)
        return 2
    available = mem_available_mb(meminfo_path())
    if available is None:
        print(UNKNOWN_CAPACITY)
        return 0
    print(max(1, (available - settings.reserve_mb) // int(unit_text)))
    return 0


@dataclass
class RunState:
    """What the record file says about the run so far."""

    collected: set[str] = field(default_factory=set)  # union over pytest attempts
    outcomes: dict[str, str] = field(default_factory=dict)  # first outcome written wins
    crashed_reports: int = 0  # crashed lines in the latest pytest attempt
    session_finished: bool = False  # the latest pytest attempt wrote its finished line
    crash_retried: bool = False  # any pytest attempt of this run crashed
    # The latest pytest attempt exited on its own without starting a session.
    exited_before_session: bool = False
    attempt: int = 0  # the number of the latest pytest attempt
    # Node id -> the pytest attempts in which its worker died while running it.
    crashes: dict[str, set[int]] = field(default_factory=dict)

    def unfinished(self) -> set[str]:
        return self.collected - self.outcomes.keys()

    def crashed_every_attempt(self) -> set[str]:
        """Tests whose worker died while running them in every pytest attempt.

        One attempt proves nothing. A test that takes its worker down again after the
        retries have halved the worker count is treated as broken, not as short of memory.
        """
        if self.attempt < 2:
            return set()
        return {
            nodeid
            for nodeid, attempts in self.crashes.items()
            if len(attempts) == self.attempt and nodeid not in self.outcomes
        }


def parse_record_line(line: str, is_last: bool) -> dict[str, object] | None:
    """The event on one record line. A truncated last line (the controller died mid-write)
    is None; a malformed line anywhere else is a real error."""
    try:
        event: object = json.loads(line)
    except json.JSONDecodeError:
        if is_last:
            return None
        raise
    return event if isinstance(event, dict) else None


def apply_event(event: dict[str, object], state: RunState) -> None:
    kind = event.get("event")
    nodeid = event.get("nodeid")
    nodeids = event.get("nodeids")
    outcome = event.get("outcome")
    if kind == "attempt":
        # The crash facts describe the latest pytest attempt only.
        state.crashed_reports = 0
        state.session_finished = False
        number = event.get("n")
        if isinstance(number, int):
            state.attempt = number
    elif kind == "collected" and isinstance(nodeids, list):
        state.collected.update(str(item) for item in nodeids)
    elif kind == "outcome" and isinstance(nodeid, str) and isinstance(outcome, str):
        state.outcomes.setdefault(nodeid, outcome)
    elif kind == "crashed":
        state.crashed_reports += 1
        if isinstance(nodeid, str):
            state.crashes.setdefault(nodeid, set()).add(state.attempt)
    elif kind == "finished":
        state.session_finished = True


def read_attempt(record: Path, state: RunState) -> None:
    """Fold the record file into `state`. Reading the whole file again is safe: the
    collected set and the first-written outcomes do not change on a second read."""
    lines = record.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        event = parse_record_line(line, is_last=index == len(lines) - 1)
        if event is not None:
            apply_event(event, state)


def append_record(record: Path, event: dict[str, object]) -> None:
    data = record.read_bytes()
    if data and not data.endswith(b"\n"):
        # A controller killed mid-write leaves a partial last line. Drop it, so the new
        # line starts clean and the partial one cannot turn into a malformed middle line.
        record.write_bytes(data[: data.rfind(b"\n") + 1])
    with record.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def attempt_command(
    argv: list[str], k: int, record: Path, only_file: Path | None
) -> list[str]:
    """The pytest command for one attempt: the caller's argv plus the runner's options."""
    command = list(argv)
    if distributes(argv):
        command += ["-n", str(k), "--max-worker-restart=0"]
    command += ["-p", "ds_run_record", f"--ds-record={record}"]
    if only_file is not None:
        command.append(f"--ds-only-nodeids={only_file}")
        # The runner and the pytest it starts share one environment when both go through
        # `uv run`, so this answers for the child too. A subset run must not fail a
        # coverage threshold.
        if importlib.util.find_spec("pytest_cov") is not None:
            command.append("--no-cov")
    return command


def set_oom_score(value: int) -> None:
    """Write `value` to this process's `oom_score_adj`. Runs in the pytest child before exec.

    Best effort: lowering a score below the inherited one needs privileges, and an error
    raised between fork and exec would stop the run with an opaque message.
    """
    with contextlib.suppress(OSError):
        OOM_SCORE_FILE.write_text(str(value), encoding="utf-8")


def become_subreaper() -> None:
    """Make this process the parent of any orphaned descendant.

    A browser a test launched detaches from its worker. As subreaper the runner inherits it
    when the worker dies, so it can still be found and killed.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    # prctl is variadic and takes unsigned longs; a bare int would be passed as a C int.
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    # A return of -1 is ignored: cleanup then misses detached processes and the run is
    # otherwise unaffected.
    libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)


def parent_pid(stat_text: str) -> int:
    """The parent pid from a `/proc/<n>/stat` line. The command name sits in brackets and can
    contain spaces and `)`, so the fields start after the last `)`."""
    return int(stat_text.rpartition(")")[2].split()[1])


def descendants(pid: int) -> list[int]:
    """Every process below `pid` in the process tree, read from `/proc`."""
    children: dict[int, list[int]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parent = parent_pid((entry / "stat").read_text(encoding="utf-8"))
        except (FileNotFoundError, ProcessLookupError):
            continue  # it exited during the scan
        children.setdefault(parent, []).append(int(entry.name))
    found: list[int] = []
    pending = [pid]
    while pending:
        for child in children.get(pending.pop(), []):
            found.append(child)
            pending.append(child)
    return found


def reap_children() -> None:
    """Collect every child that has exited, so it does not stay a zombie."""
    while True:
        try:
            if os.waitpid(-1, os.WNOHANG) == (0, 0):
                return
        except ChildProcessError:
            return


def kill_descendants() -> None:
    """Kill everything below this process. The scan repeats because a process can fork
    between one scan and its kill."""
    deadline = time.monotonic() + KILL_DEADLINE_S
    while (pids := descendants(os.getpid())) and time.monotonic() < deadline:
        for pid in pids:
            # It may have exited between the scan and the kill.
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        reap_children()
        time.sleep(0.05)


def exit_on_signal(signum: int, _frame: object) -> None:
    """Leave nothing behind when the runner is interrupted or terminated."""
    kill_descendants()
    for path in LIVE_NODE_ID_FILES:
        path.unlink(missing_ok=True)
    sys.exit(128 + signum)


def run_attempt(
    argv: list[str], k: int, record: Path, only_file: Path | None, oom_score_adj: int
) -> int:
    """Run one pytest attempt and return its exit code. Nothing it started outlives it."""
    scripts_dir = str(Path(__file__).resolve().parent)
    child_env = dict(os.environ)
    child_env["PYTHONPATH"] = os.pathsep.join(
        [scripts_dir, *filter(None, [child_env.get("PYTHONPATH")])]
    )
    command = attempt_command(argv, k, record, only_file)
    # The runner's own score is never written: only the pytest child gets it.
    set_score = (
        functools.partial(set_oom_score, oom_score_adj)
        if oom_score_adj != 0 and OOM_SCORE_FILE.exists()
        else None
    )
    try:
        process = subprocess.Popen(  # noqa: S603
            command, env=child_env, start_new_session=True, preexec_fn=set_score
        )
        return process.wait()
    finally:
        kill_descendants()


def died_by_signal(returncode: int) -> bool:
    """Whether an exit code means the process was killed by a signal.

    A direct child reports a negative code. `uv run` and a shell report 128 plus the signal
    number. pytest's own exit codes are 0 to 5.
    """
    return returncode < 0 or returncode > 128


def write_only_file(only_file: Path | None, nodeids: set[str]) -> Path:
    """Write the node ids to retry, one per line, reusing the file of an earlier retry."""
    if only_file is None:
        descriptor, name = tempfile.mkstemp(prefix="ds_only_nodeids_", suffix=".txt")
        os.close(descriptor)
        only_file = Path(name)
        LIVE_NODE_ID_FILES.append(only_file)
    only_file.write_text("\n".join(sorted(nodeids)) + "\n", encoding="utf-8")
    return only_file


def run_with_retries(
    argv: list[str], settings: MemorySettings, first_k: int, record: Path
) -> int:
    """Run pytest, retrying a crashed attempt for its unfinished tests; print the verdict."""
    state = RunState()
    worker_counts: list[int] = []
    elapsed_s = 0.0
    only_file: Path | None = None
    k = first_k
    only: set[str] | None = None
    returncode = 0
    try:
        for attempt in range(1, settings.max_retries + 2):
            if only is not None:
                only_file = write_only_file(only_file, only)
            append_record(record, {"event": "attempt", "n": attempt, "k": k})
            worker_counts.append(k)
            started = time.monotonic()
            returncode = run_attempt(
                argv,
                k,
                record,
                only_file if only is not None else None,
                settings.oom_score_adj,
            )
            elapsed_s += time.monotonic() - started
            read_attempt(record, state)
            # A session that finished on its own with tests unfinished stopped on purpose
            # (-x, --maxfail). Only a crashed worker or a killed controller is a crash.
            controller_killed = not state.session_finished and died_by_signal(
                returncode
            )
            if state.crashed_reports == 0 and not controller_killed:
                # No session and no signal: pytest gave up before one started (a usage
                # error, a conftest that fails to import, --help). Retrying cannot help.
                state.exited_before_session = not state.session_finished
                break
            state.crash_retried = True
            collection_lost = (
                not state.collected
            )  # the controller died before collecting
            # A worker that died after its test's outcome was final leaves nothing to re-run.
            if not collection_lost and not state.unfinished():
                break
            if attempt == settings.max_retries + 1:
                break
            only = None if collection_lost else state.unfinished()
            backoff = BACKOFF_S[min(attempt - 1, len(BACKOFF_S) - 1)]
            ceiling = max(1, math.ceil(k / 2))
            print(
                f"run: pytest attempt {attempt}/{settings.max_retries + 1} crashed "
                f"({len(state.unfinished())} tests unfinished); backing off "
                f"{backoff} s, retrying with -n {ceiling}"
            )
            time.sleep(scaled(backoff))
            k = wait_for_memory(settings, ceiling, first_attempt=False)
    finally:
        if only_file is not None:
            only_file.unlink(missing_ok=True)
            LIVE_NODE_ID_FILES.remove(only_file)
    repeat_crashers = state.crashed_every_attempt()
    if repeat_crashers:
        state.outcomes.update(dict.fromkeys(repeat_crashers, "failed"))
        print(
            "run: tests that crashed their xdist worker in every pytest attempt: "
            f"{len(repeat_crashers)} (counted as failed)"
        )
    label, exit_code = verdict(state, returncode)
    print_closing_lines(state, worker_counts, elapsed_s, label)
    if label == "PASS":
        record.unlink(missing_ok=True)
    return exit_code


def verdict(state: RunState, returncode: int) -> tuple[str, int]:
    """The `RESULT` label and the exit code for a finished run."""
    if state.exited_before_session and returncode != 0:
        return "FAIL", returncode
    if not state.crash_retried:
        return ("PASS", 0) if returncode == 0 else ("FAIL", returncode)
    # A known defect is something to fix, so a failure outranks tests left unfinished.
    if "failed" in state.outcomes.values():
        return "FAIL", EXIT_TESTS_FAILED
    if state.unfinished() or not state.collected:
        return "INCOMPLETE", EXIT_INCOMPLETE
    return "PASS", 0


def print_closing_lines(
    state: RunState, worker_counts: list[int], elapsed_s: float, label: str
) -> None:
    outcomes = list(state.outcomes.values())
    passed, failed, skipped = (
        outcomes.count(name) for name in ("passed", "failed", "skipped")
    )
    workers = " -> ".join(str(count) for count in worker_counts)
    print(f"run: pytest attempts {len(worker_counts)}, xdist workers {workers}")
    print(
        f"run: tests {len(state.collected)} collected, {len(outcomes)} finished, "
        f"{failed} failed, {len(state.unfinished())} unfinished"
    )
    print(
        f"run: summary (merged): {passed} passed, {failed} failed, "
        f"{skipped} skipped in {elapsed_s:.1f}s"
    )
    print(f"run: RESULT {label}")


def make_record_file() -> Path:
    descriptor, name = tempfile.mkstemp(prefix="ds_run_record_", suffix=".jsonl")
    os.close(descriptor)
    return Path(name)


def main() -> int:
    # pytest writes straight to the same pipe or file. Without this the runner's lines sit
    # in a block buffer and come out after pytest's output, or only at exit.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)
    if sys.platform == "linux":
        become_subreaper()
    signal.signal(signal.SIGINT, exit_on_signal)
    signal.signal(signal.SIGTERM, exit_on_signal)
    try:
        return run(sys.argv[1:])
    except (ConfigError, tomllib.TOMLDecodeError) as error:
        print(f"run_tests.py: {error}", file=sys.stderr)
        return 2


def run(argv: list[str]) -> int:
    if argv[:1] == ["--capacity"]:
        settings = load_memory_settings(Path.cwd(), os.environ)
        return print_capacity(argv[1] if len(argv) == 2 else "", settings)
    if not is_pytest_command(argv):
        print(
            "run_tests.py runs only a pytest command. Accepted forms: "
            "pytest, python -m pytest, python3 -m pytest, uv run pytest, "
            "uv run --directory <dir> pytest.",
            file=sys.stderr,
        )
        return 2
    if os.environ.get("DS_TEST_MEMORY_GUARD") == "off":
        return run_plain(argv)
    settings = load_memory_settings(Path.cwd(), os.environ)
    if mem_available_mb(meminfo_path()) is None:
        print("ram: no /proc/meminfo on this platform; running the command as given")
        return run_plain(argv)
    ceiling = worker_ceiling(argv, settings.max_workers)
    k = wait_for_memory(settings, ceiling, first_attempt=True)
    record = make_record_file()
    print(
        f"ram: MemAvailable {mem_available_mb(meminfo_path())} MB, "
        f"{format_psi(psi_some_avg10(psi_path()))}, xdist workers -n {k}"
        f"{describe_sources(settings)}"
    )
    print(f"run: record {record}")
    return run_with_retries(argv, settings, k, record)


if __name__ == "__main__":
    sys.exit(main())
