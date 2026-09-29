"""The one way every `dev_db` tool reaches the shared dev Postgres server.

Every tool addresses the server through the compose file, never a container name, so a tool
still works after the container is recreated.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

COMPOSE_FILE = Path(__file__).resolve().parent / "docker-compose.yaml"


class ServerUnavailable(Exception):  # noqa: N818 -- every dev_db tool catches it by this name
    """The compose project isn't up, or the command run inside it failed."""


def compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def psql(sql: str) -> list[list[str]]:
    """Run sql as pguser inside the postgres service; return rows of tab-separated fields.

    It connects over the container's local socket, which the postgres image trusts, so no
    password is passed.
    """
    result = compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "pguser",
        "-d",
        "postgres",
        "-AtX",
        "-F",
        "\t",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    )
    if result.returncode != 0:
        raise ServerUnavailable(result.stderr)
    return [line.split("\t") for line in result.stdout.splitlines()]
