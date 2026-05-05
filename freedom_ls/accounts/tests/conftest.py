"""Shared fixtures for `accounts` tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import pytest


@pytest.fixture
def mock_legal_blobs(monkeypatch, tmp_path: Path, settings):
    """Replace `read_blob_at_head` with an in-memory blob store.

    Avoids spinning up a real git repo for tests that only care about
    higher-level legal-doc behaviour. Returns a function the test calls to
    register `(rel_path, content)` pairs; SHA is auto-derived from the path.

    Behaviour mirrors the real loader: missing rel_paths raise
    ``FileNotFoundError`` so the production code path is exercised.
    """
    blobs: dict[str, tuple[str, str]] = {}

    def fake_read_blob_at_head(rel_path: str) -> tuple[str, str]:
        if rel_path not in blobs:
            raise FileNotFoundError(f"no blob for {rel_path}")
        return blobs[rel_path]

    monkeypatch.setattr(
        "freedom_ls.accounts.legal_docs.read_blob_at_head",
        fake_read_blob_at_head,
    )

    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None

    def add(rel_path: str, content: str, sha: str | None = None) -> None:
        # Synthesise a deterministic 40-char hex SHA from the path so tests
        # can still assert on `git_hash` length / uniqueness.
        derived = sha or (f"{abs(hash(rel_path)):040x}"[:40])
        blobs[rel_path] = (derived, content)

    return add


def _seed_default_legal_docs(
    add: Callable[..., None],
    docs: Iterable[tuple[str, str]] = (),
) -> None:
    """Helper: register the standard `_default/<type>.md` blobs."""
    for doc_type, content in docs:
        add(f"legal_docs/_default/{doc_type}.md", content)


@pytest.fixture
def legal_repo_mock(mock_legal_blobs):
    """Pre-seed `_default/{terms,privacy}.md` with minimal frontmatter.

    Drop-in replacement for the previous on-disk `legal_repo` fixture, but
    without ``subprocess`` calls. Returns the same ``add`` function so tests
    can layer site-specific overrides.
    """
    terms = (
        '---\nversion: "1.5"\ntitle: "Terms"\ntype: "terms"\n'
        'effective_date: "2026-04-27"\n---\n\nBody.\n'
    )
    privacy = (
        '---\nversion: "1.5"\ntitle: "Privacy"\ntype: "privacy"\n'
        'effective_date: "2026-04-27"\n---\n\nBody.\n'
    )
    _seed_default_legal_docs(
        mock_legal_blobs,
        docs=(("terms", terms), ("privacy", privacy)),
    )
    return mock_legal_blobs
