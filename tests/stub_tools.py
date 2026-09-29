"""Stub executables shared by shell-script tests.

The shell scripts under test call real tools (`uv`, `npm`, `psql`, ...). These
helpers write a fake executable for any tool name onto a temporary `PATH`
that only logs its own invocation, so a test never runs a real install,
build, or database query.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _stub_script(*, exit_var: str, output_var: str | None, capture_stdin: bool) -> str:
    lines = [
        "#!/bin/sh",
        'printf \'%s %s\\n\' "$(basename "$0")" "$*" >> "$STUB_LOG_FILE"',
    ]
    if capture_stdin:
        # A caller piping a script through `-f -` gets it logged too, so a
        # test can assert on what ran, not only on the flags passed.
        lines += [
            'case "$*" in',
            '    *"-f -"*) cat >> "$STUB_LOG_FILE" ;;',
            "esac",
        ]
    if output_var is not None:
        lines += [
            f'if [ -n "${{{output_var}:-}}" ]; then',
            f"    printf '%s\\n' \"${{{output_var}}}\"",
            "fi",
        ]
    lines.append(f'exit "${{{exit_var}:-0}}"')
    return "\n".join(lines) + "\n"


def write_stub(
    path: Path,
    *,
    exit_var: str,
    output_var: str | None = None,
    capture_stdin: bool = False,
) -> None:
    """Write a stub executable at `path` that logs its invocation to `$STUB_LOG_FILE`.

    `exit_var` names the environment variable a test sets to make the stub
    fail. `output_var`, when given, is printed to stdout whenever that
    environment variable is non-empty. `capture_stdin` also appends stdin to
    the log when the stub is called with `-f -`.
    """
    path.write_text(
        _stub_script(
            exit_var=exit_var, output_var=output_var, capture_stdin=capture_stdin
        )
    )
    path.chmod(0o755)


@dataclass
class StubTools:
    """A directory of stub executables on a temporary `PATH`, and their shared log."""

    bin_dir: Path
    log_file: Path

    def env(self, **variables: str | int) -> dict[str, str]:
        """Build a subprocess environment with `bin_dir` first on `PATH`.

        Extra keywords become environment variables, typically a stub's
        `exit_var` or `output_var`.
        """
        child_env = dict(os.environ)
        child_env["PATH"] = f"{self.bin_dir}{os.pathsep}{child_env.get('PATH', '')}"
        child_env["STUB_LOG_FILE"] = str(self.log_file)
        for name, value in variables.items():
            child_env[name] = str(value)
        return child_env

    def log_lines(self) -> list[str]:
        if not self.log_file.exists():
            return []
        return self.log_file.read_text().splitlines()


def run_script(
    script: Path, cwd: Path, env: dict[str, str], args: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(script), *(args or [])],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
