"""One command that runs ordered checks against the dev Postgres server and its engine.

Each check function returns a list of `Finding`s from I/O it performs itself (`docker`,
`docker compose`, the filesystem). `main` prints one line per finding and exits non-zero
when any of them failed. Checks run in order and later checks are skipped once the engine
itself is unreachable, since they all depend on it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from dev_db import server, stale_dbs

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAPER_SCRIPT = (
    _REPO_ROOT
    / "claude_plugins"
    / "django-stack"
    / "scripts"
    / "reap_playwright_mcp.sh"
)
_PGDATA_VOLUME = "fls_dev_db_pgdata"


class Verdict(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class Finding:
    check: str
    verdict: Verdict
    message: str
    next_step: str = ""


def format_finding(finding: Finding) -> str:
    line = f"[{finding.verdict}] {finding.check}: {finding.message}"
    if finding.next_step:
        line += f" -> next: {finding.next_step}"
    return line


# Literal substrings of Docker Desktop log lines that name its file-service failure mode.
DESKTOP_SIGNATURES = ("injecting event blocked for", "Service fs failed")

_RECENT_DAYS = 3


@dataclass(frozen=True)
class SignatureHits:
    count: int
    last_occurrence: str


def match_signature(line: str, signatures: tuple[str, ...]) -> str | None:
    for signature in signatures:
        if signature in line:
            return signature
    return None


def summarise(
    lines: Iterable[str], signatures: tuple[str, ...]
) -> dict[str, SignatureHits]:
    hits: dict[str, SignatureHits] = {}
    for line in lines:
        signature = match_signature(line, signatures)
        if signature is None:
            continue
        previous = hits.get(signature)
        count = previous.count + 1 if previous is not None else 1
        hits[signature] = SignatureHits(count=count, last_occurrence=line)
    return hits


def _desktop_log_dirs() -> list[Path]:
    if sys.platform == "darwin":
        return [Path.home() / "Library/Containers/com.docker.docker/Data/log"]
    return [
        Path.home() / ".docker/desktop/log/host",
        Path.home() / ".docker/desktop/log/vm",
    ]


def _recent_desktop_log_lines() -> list[str]:
    cutoff = datetime.now(UTC) - timedelta(days=_RECENT_DAYS)
    lines: list[str] = []
    for log_dir in _desktop_log_dirs():
        if not log_dir.is_dir():
            continue
        for log_file in sorted(log_dir.iterdir()):
            if not log_file.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            if mtime < cutoff:
                continue
            try:
                lines.extend(log_file.read_text(errors="replace").splitlines())
            except OSError:
                continue
    return lines


def check_engine_reachable() -> list[Finding]:
    result = subprocess.run(
        ["docker", "info"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return [Finding("engine", Verdict.OK, "The Docker engine is reachable.")]

    findings = [
        Finding(
            "engine",
            Verdict.FAIL,
            "docker info failed; the engine is not reachable.",
            "Start Docker (or the container engine) and try again.",
        )
    ]
    hits = summarise(_recent_desktop_log_lines(), DESKTOP_SIGNATURES)
    if hits:
        last_occurrence = sorted(hits.values(), key=lambda hit: hit.last_occurrence)[-1]
        findings.append(
            Finding(
                "engine",
                Verdict.FAIL,
                f"Docker Desktop file-service failure: {last_occurrence.last_occurrence}",
                "Restart Docker Desktop.",
            )
        )
    return findings


def check_engine_kind() -> list[Finding]:
    result = subprocess.run(
        ["docker", "info", "--format", "{{json .}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [
            Finding("engine_kind", Verdict.WARN, "Could not parse docker info output.")
        ]

    findings: list[Finding] = []
    operating_system = str(info.get("OperatingSystem", ""))
    if "Docker Desktop" in operating_system and sys.platform == "linux":
        findings.append(
            Finding(
                "engine_kind",
                Verdict.WARN,
                "Docker Desktop is running on Linux.",
                "Use Docker Engine instead; it doesn't run Linux containers in a VM.",
            )
        )

    mem_total = info.get("MemTotal")
    gib = 1024**3
    if isinstance(mem_total, int) and mem_total < 4 * gib:
        findings.append(
            Finding(
                "engine_kind",
                Verdict.WARN,
                f"The engine reports {mem_total / gib:.1f} GiB total memory, under 4 GiB.",
                "Raise the engine's (or its VM's) memory limit.",
            )
        )

    if not findings:
        findings.append(
            Finding("engine_kind", Verdict.OK, "Engine kind and memory are fine.")
        )
    return findings


def check_old_project() -> list[Finding]:
    result = subprocess.run(
        [  # noqa: S607
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=com.docker.compose.project=dev_db",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    names = [line for line in result.stdout.splitlines() if line]
    if names:
        return [
            Finding(
                "old_project",
                Verdict.FAIL,
                f"Containers from the old dev_db compose project are still present: {', '.join(names)}.",
                "docker compose -p dev_db down",
            )
        ]
    return [
        Finding(
            "old_project",
            Verdict.OK,
            "No leftover containers from the old dev_db project.",
        )
    ]


def check_container() -> list[Finding]:
    id_result = server.compose("ps", "-a", "-q", "postgres")
    container_id = id_result.stdout.strip()
    if not container_id:
        return [
            Finding(
                "container",
                Verdict.FAIL,
                "No postgres container exists for this compose project.",
                f"docker compose -f {server.COMPOSE_FILE} up -d",
            )
        ]

    inspect_result = subprocess.run(  # noqa: S603
        ["docker", "inspect", container_id],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        data = json.loads(inspect_result.stdout)[0]
    except (json.JSONDecodeError, IndexError):
        return [
            Finding(
                "container",
                Verdict.FAIL,
                "docker inspect failed for the postgres container.",
            )
        ]

    state = data.get("State", {})
    running = bool(state.get("Running"))
    health = state.get("Health", {}).get("Status", "none")
    oom_killed = bool(state.get("OOMKilled"))
    exit_code = state.get("ExitCode")
    restart_count = data.get("RestartCount")
    started_at = state.get("StartedAt", "")
    created = data.get("Created", "")
    working_dir = (
        data.get("Config", {})
        .get("Labels", {})
        .get("com.docker.compose.project.working_dir", "")
    )

    message = (
        f"running={running} health={health} OOMKilled={oom_killed} ExitCode={exit_code} "
        f"RestartCount={restart_count} StartedAt={started_at} Created={created}"
    )
    try:
        created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        created_at = None
    if created_at is not None and datetime.now(UTC) - created_at < timedelta(hours=24):
        message += f"; recreated at {created} from {working_dir}"

    verdict = Verdict.OK
    next_step = ""
    if not running or health == "unhealthy" or oom_killed:
        verdict = Verdict.FAIL
        next_step = (
            "Check the container's logs, then docker compose up -d to restart it."
        )

    return [Finding("container", verdict, message, next_step)]


# Literal substrings of Postgres log lines that name a known failure. `PANIC` and
# "No space left on device" are the only two that mean the server already lost data or
# stopped writing; the rest are near-misses the role's connection limit and timeout guard
# against.
POSTGRES_SIGNATURES = (
    "too many clients",
    "remaining connection slots",
    "could not resize shared memory",
    "terminated by signal",
    "No space left on device",
    "PANIC",
    "being accessed by other users",
    "idle-in-transaction timeout",
)

_POSTGRES_FAIL_SIGNATURES = ("PANIC", "No space left on device")

_POSTGRES_LOG_NEXT_STEPS: dict[str, str] = {
    "too many clients": "Check connections below; lower -n.",
    "remaining connection slots": "Check connections below; lower -n.",
    "could not resize shared memory": "Raise shm_size in dev_db/docker-compose.yaml.",
    "terminated by signal": "Check dmesg for an OOM kill; raise mem_limit.",
    "No space left on device": "Free disk space on the Docker volume.",
    "PANIC": "Check the container's logs; recovery may need cleanup_devdb.sh.",
    "being accessed by other users": "Retry once the other session's query finishes.",
    "idle-in-transaction timeout": (
        "A session was auto-ended; check for a script holding a transaction open."
    ),
}

# Postgres writes English weekday abbreviations into log_filename whatever the server's
# locale, so recent_log_names indexes this tuple instead of using strftime("%a").
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def recent_log_names(today: date, days: int = 3) -> list[str]:
    weekday = today.weekday()
    return [
        f"postgresql-{_WEEKDAYS[(weekday - offset) % 7]}.log" for offset in range(days)
    ]


def _read_postgres_log_lines(names: list[str]) -> list[str]:
    paths = " ".join(f'"$PGDATA"/log/{name}' for name in names)
    result = server.compose(
        "exec", "-T", "postgres", "sh", "-c", f"cat {paths} 2>/dev/null"
    )
    if result.returncode == 0:
        return result.stdout.splitlines()

    # The container isn't running. Only fall back to a throwaway container on the data
    # volume when that volume already exists -- `docker run -v <name>:...` on a name that
    # doesn't exist yet silently creates it, which diagnose must never do.
    volume_check = subprocess.run(  # noqa: S603
        ["docker", "volume", "inspect", _PGDATA_VOLUME],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if volume_check.returncode != 0:
        return []

    fallback_paths = " ".join(f"/data/log/{name}" for name in names)
    fallback = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "run",
            "--rm",
            "-v",
            f"{_PGDATA_VOLUME}:/data",
            "postgres:17",
            "sh",
            "-c",
            f"cat {fallback_paths} 2>/dev/null",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return fallback.stdout.splitlines()


def check_postgres_logs() -> list[Finding]:
    lines = _read_postgres_log_lines(recent_log_names(datetime.now(UTC).date()))
    hits = summarise(lines, POSTGRES_SIGNATURES)
    if not hits:
        return [
            Finding(
                "postgres_logs",
                Verdict.OK,
                "No known failure signatures in the recent Postgres logs.",
            )
        ]

    findings = []
    for signature, hit in hits.items():
        verdict = (
            Verdict.FAIL if signature in _POSTGRES_FAIL_SIGNATURES else Verdict.WARN
        )
        findings.append(
            Finding(
                "postgres_logs",
                verdict,
                f"{signature} x{hit.count}, last: {hit.last_occurrence}",
                _POSTGRES_LOG_NEXT_STEPS[signature],
            )
        )
    return findings


def check_postgres_activity() -> list[Finding]:
    try:
        return _check_postgres_activity()
    except server.ServerUnavailable as exc:
        return [
            Finding(
                "postgres_activity", Verdict.FAIL, f"Could not query Postgres: {exc}"
            )
        ]


def _check_postgres_activity() -> list[Finding]:
    findings: list[Finding] = []

    max_connections = int(server.psql("SHOW max_connections")[0][0])
    activity_rows = server.psql(
        "SELECT application_name, state, count(*) FROM pg_stat_activity "
        "WHERE backend_type = 'client backend' GROUP BY application_name, state"
    )
    total_connections = sum(int(row[2]) for row in activity_rows)
    breakdown = ", ".join(
        f"{row[0] or '-'}/{row[1] or '-'}={row[2]}" for row in activity_rows
    )
    over_80_percent = total_connections > max_connections * 0.8
    findings.append(
        Finding(
            "postgres_activity",
            Verdict.WARN if over_80_percent else Verdict.OK,
            f"{total_connections}/{max_connections} connections ({breakdown})",
            "Lower -n, or investigate the busiest application_name."
            if over_80_percent
            else "",
        )
    )

    idle_rows = server.psql(
        "SELECT application_name FROM pg_stat_activity WHERE state = "
        "'idle in transaction' AND now() - state_change > interval '5 minutes'"
    )
    findings.append(
        Finding(
            "postgres_activity",
            Verdict.WARN if idle_rows else Verdict.OK,
            f"{len(idle_rows)} session(s) idle in transaction for over 5 minutes"
            + (
                f": {', '.join(row[0] or '-' for row in idle_rows)}"
                if idle_rows
                else "."
            ),
            "The role's 15-minute timeout will end these; investigate if that's too slow."
            if idle_rows
            else "",
        )
    )

    # The container's own /dev/shm, not a local temp path.
    disk_result = server.compose(
        "exec",
        "-T",
        "postgres",
        "df",
        "-h",
        "/var/lib/postgresql/data",
        "/dev/shm",  # noqa: S108  # nosec B108
    )
    findings.append(
        Finding(
            "postgres_activity",
            Verdict.OK,
            disk_result.stdout.strip() or "Could not read disk usage.",
        )
    )

    stale_report, _sizes = stale_dbs.find_stale()
    stale_count = len(stale_report.stale)
    findings.append(
        Finding(
            "postgres_activity",
            Verdict.WARN if stale_count else Verdict.OK,
            f"{stale_count} stale per-branch database(s).",
            "uv run python -m dev_db.stale_dbs --drop" if stale_count else "",
        )
    )

    return findings


def is_orphan(ppid: int, subreaper_pid: int | None) -> bool:
    """A process is orphaned when its parent is PID 1 or the user's own `systemd --user`.

    The same rule lives in `claude_plugins/django-stack/scripts/reap_playwright_mcp.sh`.
    """
    return ppid == 1 or (subreaper_pid is not None and ppid == subreaper_pid)


def _reaper_candidate_count() -> int:
    result = subprocess.run(  # noqa: S603
        [str(_REAPER_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line for line in result.stdout.splitlines() if line]
    if not lines or lines[0].startswith("No orphaned"):
        return 0
    return len(lines) - 1  # The first line is the "pid age rss command" header.


def _orphaned_pytest_pids() -> list[int]:
    result = subprocess.run(
        ["ps", "-A", "-o", "pid=,ppid=,uid=,args="],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    rows: list[tuple[int, int, int, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) < 4:
            continue
        pid, ppid, uid, args = parts
        rows.append((int(pid), int(ppid), int(uid), args))

    current_uid = os.getuid()
    subreaper_pid = next(
        (
            pid
            for pid, _ppid, row_uid, args in rows
            if row_uid == current_uid and "systemd --user" in args
        ),
        None,
    )
    return [
        pid
        for pid, ppid, row_uid, args in rows
        if row_uid == current_uid
        and is_orphan(ppid, subreaper_pid)
        and "pytest" in args
    ]


def check_orphaned_processes() -> list[Finding]:
    findings: list[Finding] = []

    candidate_count = _reaper_candidate_count()
    findings.append(
        Finding(
            "orphaned_processes",
            Verdict.WARN if candidate_count else Verdict.OK,
            f"{candidate_count} orphaned Playwright MCP process(es) or browser(s).",
            ".claude/ds/scripts/reap_playwright_mcp.sh --kill"
            if candidate_count
            else "",
        )
    )

    pytest_pids = _orphaned_pytest_pids()
    findings.append(
        Finding(
            "orphaned_processes",
            Verdict.WARN if pytest_pids else Verdict.OK,
            f"{len(pytest_pids)} orphaned pytest process(es)"
            + (
                f": {', '.join(str(pid) for pid in pytest_pids)}"
                if pytest_pids
                else "."
            ),
            "Check whether these runs are still needed; end them if not."
            if pytest_pids
            else "",
        )
    )

    return findings


def main() -> int:
    findings = check_engine_reachable()
    if findings[0].verdict != Verdict.FAIL:
        findings += check_engine_kind() + check_old_project() + check_container()
        findings += (
            check_postgres_logs()
            + check_postgres_activity()
            + check_orphaned_processes()
        )

    for finding in findings:
        print(format_finding(finding))

    return 1 if any(finding.verdict == Verdict.FAIL for finding in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
