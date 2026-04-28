"""Tests for the public legal-doc view."""

from __future__ import annotations

from pathlib import Path

import pytest

from django.test import Client
from django.urls import reverse

from ._git_helpers import run_git as _git

_TERMS = """---
version: "1.0"
title: "Terms"
type: "terms"
effective_date: "2026-04-27"
---

# Body

Some body text here.
"""


_TERMS_WITH_SCRIPT = """---
version: "1.0"
title: "Terms"
type: "terms"
effective_date: "2026-04-27"
---

# Body

<script>alert('xss')</script>

Body text.
"""


@pytest.fixture
def with_terms(tmp_path: Path, settings, mock_site_context):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    default_dir = tmp_path / "legal_docs" / "_default"
    default_dir.mkdir(parents=True)
    (default_dir / "terms.md").write_text(_TERMS, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None
    return tmp_path


@pytest.mark.django_db
def test_unknown_doc_type_returns_404(mock_site_context):
    client = Client()
    response = client.get(
        reverse("accounts:legal_doc", kwargs={"doc_type": "marketing"})
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_missing_doc_returns_404(mock_site_context, tmp_path, settings):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "README.md").write_text("hi\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None

    client = Client()
    response = client.get(reverse("accounts:legal_doc", kwargs={"doc_type": "terms"}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_existing_doc_renders_content(with_terms):
    client = Client()
    response = client.get(reverse("accounts:legal_doc", kwargs={"doc_type": "terms"}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Some body text here" in body
    assert "Terms" in body  # title


@pytest.mark.django_db
def test_view_strips_script_tags(tmp_path, settings, mock_site_context):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    default_dir = tmp_path / "legal_docs" / "_default"
    default_dir.mkdir(parents=True)
    (default_dir / "terms.md").write_text(_TERMS_WITH_SCRIPT, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None

    client = Client()
    response = client.get(reverse("accounts:legal_doc", kwargs={"doc_type": "terms"}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # nh3 must strip the <script> tag.
    assert "<script>" not in body
    assert "alert" not in body


@pytest.mark.django_db
def test_view_reachable_without_authentication(with_terms):
    """Legal docs are public — no login required."""
    client = Client()  # no login
    response = client.get(reverse("accounts:legal_doc", kwargs={"doc_type": "terms"}))
    assert response.status_code == 200
