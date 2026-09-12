"""Tests for the public legal-doc view."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.icons.loader import _cache

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


@pytest.fixture
def cold_icon_cache() -> Iterator[None]:
    """Empty the icon loader's cache around the test.

    The loader reads its JSON from ``BASE_DIR/node_modules`` once and memoises
    it, so a page only re-reads that path when the cache is cold. Emptying it
    makes the read happen here rather than depending on which tests ran first.
    """
    _cache.clear()
    yield
    _cache.clear()


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
def test_missing_doc_returns_404_with_a_cold_icon_cache(
    mock_site_context, mock_legal_blobs, cold_icon_cache
):
    """The stubbed BASE_DIR must still reach the real node_modules.

    `mock_legal_blobs` repoints BASE_DIR at a tmp dir so the legal-doc loader
    reads fixture blobs. The icon loader reads that same setting, and the 404
    page it renders carries icons, so they have to resolve under the stub too.
    """
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
    # nh3 must strip the <script> tag and its contents.
    assert "<script>" not in body
    assert "alert('xss')" not in body


@pytest.mark.django_db
def test_view_reachable_without_authentication(with_terms):
    """Legal docs are public — no login required."""
    client = Client()  # no login
    response = client.get(reverse("accounts:legal_doc", kwargs={"doc_type": "terms"}))
    assert response.status_code == 200
