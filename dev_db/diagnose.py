"""One command that runs ordered checks against the dev Postgres server and its engine.

Each check function returns a list of `Finding`s from I/O it performs itself (`docker`,
`docker compose`, the filesystem). `main` prints one line per finding and exits non-zero
when any of them failed. Checks run in order and later checks are skipped once the engine
itself is unreachable, since they all depend on it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from dev_db import server


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


def main() -> int:
    findings = check_engine_reachable()
    if findings[0].verdict != Verdict.FAIL:
        findings += check_engine_kind() + check_old_project() + check_container()
        # Slice 12 appends check_postgres_logs, check_postgres_activity and
        # check_orphaned_processes here.

    for finding in findings:
        print(format_finding(finding))

    return 1 if any(finding.verdict == Verdict.FAIL for finding in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
