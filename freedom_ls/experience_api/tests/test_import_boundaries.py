"""Import-boundary guard: experience_api imports only accounts and site_aware_models.

This test is the durable guard against portability regressions. The
experience_api app is meant to be copy-pastable into any Django project; the
only internal dependencies allowed are `accounts` (for the User type) and
`site_aware_models` (for SiteAwareModel and _thread_locals).
"""

from __future__ import annotations

import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"accounts", "site_aware_models", "experience_api"}

IMPORT_PATTERN = re.compile(r"(?:from|import)\s+freedom_ls\.(?P<app>[a-z_]+)")


def test_experience_api_imports_only_allowed_apps() -> None:
    offenders: list[tuple[Path, int, str, str]] = []
    for path in APP_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for match in IMPORT_PATTERN.finditer(line):
                app = match.group("app")
                if app not in ALLOWED:
                    offenders.append((path, lineno, line, app))
    assert not offenders, (
        "experience_api must only import from accounts and site_aware_models. "
        f"Offending imports: {offenders}"
    )
