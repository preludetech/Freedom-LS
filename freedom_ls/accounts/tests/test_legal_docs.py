"""Tests for `freedom_ls.accounts.legal_docs`."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from django.contrib.sites.models import Site
from django.core.checks import Warning as ChecksWarning

from freedom_ls.accounts import legal_docs

from ._git_helpers import commit_all as _commit
from ._git_helpers import init_repo as _init_repo

_TERMS_BODY = """---
version: "1.0"
title: "Default Terms"
type: "terms"
effective_date: "2026-04-27"
---

# Default terms

Body here.
"""

_PRIVACY_BODY = """---
version: "1.0"
title: "Default Privacy"
type: "privacy"
effective_date: "2026-04-27"
---

# Default privacy

Body here.
"""

_SITE_TERMS_BODY = """---
version: "2.0"
title: "Site Terms"
type: "terms"
effective_date: "2026-04-27"
---

# Site-specific terms

Body here.
"""


@pytest.fixture
def legal_docs_seeded(mock_legal_blobs):
    """Mock-backed equivalent of the previous on-disk `legal_repo` fixture.

    Seeds `_default/{terms,privacy}.md` and returns the ``add`` callable so
    tests can layer in site-specific overrides.
    """
    mock_legal_blobs("legal_docs/_default/terms.md", _TERMS_BODY)
    mock_legal_blobs("legal_docs/_default/privacy.md", _PRIVACY_BODY)
    return mock_legal_blobs


@pytest.mark.django_db
def test_get_legal_doc_returns_default_when_no_site_specific(legal_docs_seeded):
    site = Site(domain="example.com", name="example")

    doc = legal_docs.get_legal_doc(site, "terms")

    assert doc is not None
    assert doc.site_domain == "_default"
    assert doc.version == "1.0"
    assert doc.title == "Default Terms"
    assert "Body here" in doc.body_markdown
    assert len(doc.git_hash) == 40


@pytest.mark.django_db
def test_get_legal_doc_returns_site_specific_when_present(legal_docs_seeded):
    legal_docs_seeded("legal_docs/example.com/terms.md", _SITE_TERMS_BODY)

    site = Site(domain="example.com", name="example")
    doc = legal_docs.get_legal_doc(site, "terms")

    assert doc is not None
    assert doc.site_domain == "example.com"
    assert doc.version == "2.0"
    assert doc.title == "Site Terms"


@pytest.mark.django_db
def test_get_legal_doc_returns_none_when_neither_exists(mock_legal_blobs):
    site = Site(domain="example.com", name="example")
    assert legal_docs.get_legal_doc(site, "terms") is None


@pytest.mark.django_db
def test_get_legal_doc_rejects_path_traversal_in_site_domain(legal_docs_seeded):
    """A malicious `Site.domain` like `../../etc` must not escape `legal_docs/`."""
    site = Site(domain="../../etc", name="bad")

    # The site-specific lookup is rejected by SITE_DOMAIN_RE. The fallback
    # to `_default/` must still work.
    doc = legal_docs.get_legal_doc(site, "terms")

    assert doc is not None
    assert doc.site_domain == "_default"


@pytest.mark.django_db
def test_get_legal_doc_reads_from_head_not_working_tree(tmp_path: Path, settings):
    """Mutating the working-tree file must not affect what is returned.

    This test exercises the real ``git show HEAD:<path>`` path, so it can't
    use the in-memory mock — that's the whole point of this regression test.
    """
    _init_repo(tmp_path)
    default_dir = tmp_path / "legal_docs" / "_default"
    default_dir.mkdir(parents=True)
    (default_dir / "terms.md").write_text(_TERMS_BODY, encoding="utf-8")
    _commit(tmp_path, "Add default legal docs")

    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None

    target = tmp_path / "legal_docs" / "_default" / "terms.md"
    target.write_text(
        target.read_text(encoding="utf-8").replace("Body here", "TAMPERED CONTENT"),
        encoding="utf-8",
    )

    site = Site(domain="example.com", name="example")
    doc = legal_docs.get_legal_doc(site, "terms")

    assert doc is not None
    assert "TAMPERED CONTENT" not in doc.body_markdown
    assert "Body here" in doc.body_markdown


@pytest.mark.django_db
def test_read_blob_at_head_uses_manifest_when_configured(tmp_path: Path, settings):
    """When `LEGAL_DOCS_MANIFEST_PATH` is set, the manifest is the source.

    Exercises the real manifest-loading path with no git involvement.
    """
    settings.BASE_DIR = tmp_path
    rel_path = "legal_docs/_default/terms.md"
    manifest_content = '---\nversion: "99.9"\ntitle: "Manifest Terms"\ntype: "terms"\neffective_date: "2026-04-27"\n---\n\nManifest body.\n'
    manifest = {
        "head_commit": "f" * 40,
        "blobs": {
            rel_path: {
                "sha": "a" * 40,
                "content_b64": base64.b64encode(
                    manifest_content.encode("utf-8")
                ).decode("ascii"),
            }
        },
    }
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    settings.LEGAL_DOCS_MANIFEST_PATH = str(manifest_file)

    site = Site(domain="example.com", name="example")
    doc = legal_docs.get_legal_doc(site, "terms")

    assert doc is not None
    assert doc.version == "99.9"
    assert doc.title == "Manifest Terms"
    assert doc.git_hash == "a" * 40
    assert "Manifest body" in doc.body_markdown


@pytest.mark.django_db
def test_get_legal_doc_returns_none_for_unknown_doc_type(legal_docs_seeded):
    site = Site(domain="example.com", name="example")
    assert legal_docs.get_legal_doc(site, "marketing") is None


@pytest.mark.django_db
def test_has_legal_doc_returns_true_when_doc_resolves(legal_docs_seeded):
    site = Site(domain="example.com", name="example")
    assert legal_docs.has_legal_doc(site, "terms") is True


@pytest.mark.django_db
def test_has_legal_doc_returns_false_when_doc_missing(mock_legal_blobs):
    site = Site(domain="example.com", name="example")
    assert legal_docs.has_legal_doc(site, "terms") is False


@pytest.mark.django_db
def test_system_check_warns_when_required_doc_missing(
    mock_legal_blobs, mock_site_context
):
    """Sites with require_terms_acceptance=True but missing docs trigger Warning."""
    from freedom_ls.accounts.checks import check_legal_docs_present_when_required
    from freedom_ls.accounts.models import SiteSignupPolicy

    SiteSignupPolicy.objects.update_or_create(
        site=mock_site_context, defaults={"require_terms_acceptance": True}
    )

    warnings = check_legal_docs_present_when_required(app_configs=None)

    assert len(warnings) == 2
    assert all(isinstance(w, ChecksWarning) for w in warnings)
    ids = {w.id for w in warnings}
    assert ids == {"freedom_ls_accounts.W001"}


@pytest.mark.django_db
def test_system_check_silent_when_docs_present(legal_docs_seeded, mock_site_context):
    """When docs resolve via _default/, no warning is emitted."""
    from freedom_ls.accounts.checks import check_legal_docs_present_when_required
    from freedom_ls.accounts.models import SiteSignupPolicy

    SiteSignupPolicy.objects.update_or_create(
        site=mock_site_context, defaults={"require_terms_acceptance": True}
    )

    warnings = check_legal_docs_present_when_required(app_configs=None)

    assert warnings == []
