"""Security regression guard tests.

These tests scan the codebase for dangerous patterns that should never appear,
and verify authentication is enforced on protected endpoints.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from django.test import Client

from freedom_ls.accounts.factories import UserFactory

# Root of the freedom_ls package
FREEDOM_LS_DIR = Path(__file__).resolve().parent.parent / "freedom_ls"

# Dangerous patterns that must never appear in our Python source code.
# Each tuple is (pattern, explanation).
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (".raw(", "Use ORM instead of raw SQL"),
    (".extra(", "Use ORM instead of QuerySet.extra()"),
    ("RawSQL", "Use ORM instead of RawSQL expressions"),
    ("@csrf_exempt", "Never exempt views from CSRF protection"),
    ("eval(", "Never use eval()"),
    ("exec(", "Never use exec()"),
    ("pickle.loads(", "Never use pickle.loads() on untrusted data"),
    ("yaml.load(", "Use yaml.safe_load() instead of yaml.load()"),
    ("**request.POST.dict()", "Never unpack request.POST into kwargs"),
    ("**request.GET.dict()", "Never unpack request.GET into kwargs"),
]


def _collect_python_files() -> list[Path]:
    """Collect all Python files under freedom_ls/, excluding migrations and tests."""
    files: list[Path] = []
    for py_file in FREEDOM_LS_DIR.rglob("*.py"):
        # Skip migration files and test files
        parts = py_file.parts
        if "migrations" in parts:
            continue
        files.append(py_file)
    return files


def _scan_for_pattern(pattern: str) -> list[tuple[Path, int, str]]:
    """Scan all Python files for a dangerous pattern.

    Returns list of (file, line_number, line_text) tuples where pattern was found.
    """
    matches: list[tuple[Path, int, str]] = []
    for py_file in _collect_python_files():
        try:
            content = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith("#"):
                continue
            if pattern in line:
                matches.append((py_file, line_num, stripped))
    return matches


@pytest.mark.parametrize(
    ("pattern", "reason"),
    DANGEROUS_PATTERNS,
    ids=[p for p, _ in DANGEROUS_PATTERNS],
)
def test_no_dangerous_pattern_in_codebase(pattern: str, reason: str) -> None:
    """Ensure no dangerous patterns exist in the freedom_ls source code."""
    matches = _scan_for_pattern(pattern)
    if matches:
        details = "\n".join(
            f"  {path.relative_to(FREEDOM_LS_DIR)}:{line_num}: {text}"
            for path, line_num, text in matches
        )
        pytest.fail(f"Found forbidden pattern '{pattern}' ({reason}):\n{details}")


@pytest.mark.django_db
class TestEducatorInterfaceAuth:
    """Verify that the educator interface requires authentication."""

    def test_unauthenticated_request_redirects_to_login(
        self, mock_site_context
    ) -> None:
        """Unauthenticated GET to /educator/ should 302 redirect to login."""
        client = Client()
        response = client.get("/educator/")
        assert response.status_code == 302
        assert "/login" in str(response.url) or "/accounts/login" in str(response.url)

    def test_authenticated_request_returns_200(self, mock_site_context) -> None:
        """Authenticated GET to /educator/ should return 200."""
        user = UserFactory()
        client = Client()
        client.force_login(user)
        response = client.get("/educator/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestArgon2PasswordHashing:
    """Verify passwords are hashed with Argon2."""

    def test_new_user_password_uses_argon2(self, mock_site_context) -> None:
        """Creating a user with a password should hash it with Argon2."""
        user = UserFactory(password="test-password-123!")
        user.refresh_from_db()
        assert user.password.startswith("argon2")
