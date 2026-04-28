"""Tests for the public legal-doc view."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

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
def with_terms(mock_legal_blobs, mock_site_context):
    mock_legal_blobs("legal_docs/_default/terms.md", _TERMS)
    return mock_legal_blobs


@pytest.mark.django_db
def test_unknown_doc_type_returns_404(mock_site_context):
    client = Client()
    response = client.get(
        reverse("accounts:legal_doc", kwargs={"doc_type": "marketing"})
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_missing_doc_returns_404(mock_site_context, mock_legal_blobs):
    # No blobs registered → lookup raises FileNotFoundError → view returns 404.
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
def test_view_strips_script_tags(mock_legal_blobs, mock_site_context):
    mock_legal_blobs("legal_docs/_default/terms.md", _TERMS_WITH_SCRIPT)

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
