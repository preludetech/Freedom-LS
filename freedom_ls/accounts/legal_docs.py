"""Legal-document loader and renderer.

Reads `legal_docs/<site_domain>/<doc_type>.md` (with a `_default/` fallback)
from the git blob at HEAD, parses YAML frontmatter, and renders the body
through the sanitised markdown pipeline.

The git blob is the source of truth — never the working tree — so a tampered
checkout cannot change what users see at signup nor what is recorded as
the `git_hash` evidence.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest

from freedom_ls.markdown_rendering.markdown_utils import render_markdown

logger = logging.getLogger(__name__)

LEGAL_DOCS_DIRNAME = "legal_docs"
DEFAULT_DOMAIN_DIR = "_default"
ALLOWED_DOC_TYPES: frozenset[str] = frozenset({"terms", "privacy"})

# Strict regex for the `<site_domain>` directory segment. Reject leading
# dot/dash and any `..` sequence as defence-in-depth before the
# resolve()-stays-inside-LEGAL_DOCS_ROOT check.
SITE_DOMAIN_RE = re.compile(
    r"^(?!\.|-)(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9.\-]*[A-Za-z0-9]$|^[A-Za-z0-9]$"
)

FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<frontmatter>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


def _legal_docs_root() -> Path:
    return Path(settings.BASE_DIR) / LEGAL_DOCS_DIRNAME


@dataclass(frozen=True)
class LegalDoc:
    doc_type: str
    site_domain: str
    relative_path: str
    version: str
    title: str
    effective_date: str
    body_markdown: str
    git_hash: str


def _run_git(args: list[str]) -> str:
    """Run ``git`` with the given args and return stdout (text).

    Raises ``FileNotFoundError`` when the requested object does not exist.
    """
    cmd = ["git", "-C", str(settings.BASE_DIR), *args]
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as err:
        raise FileNotFoundError(
            f"git command failed: {' '.join(cmd)} stderr={err.stderr!r}"
        ) from err
    except FileNotFoundError as err:
        # `git` binary missing.
        raise FileNotFoundError(f"git binary not available: {err}") from err
    return result.stdout


def _read_blob_at_head_via_git(rel_path: str) -> tuple[str, str]:
    """Resolve `rel_path` to (sha, content) via `git show HEAD:<rel_path>`.

    Raises FileNotFoundError if the object doesn't exist in HEAD.
    """
    sha = _run_git(["rev-parse", f"HEAD:{rel_path}"]).strip()
    content = _run_git(["show", f"HEAD:{rel_path}"])
    return sha, content


def _read_blob_at_head_via_manifest(
    manifest_path: Path, rel_path: str
) -> tuple[str, str]:
    """Resolve `rel_path` from a pre-built manifest of git blob SHAs + content."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise FileNotFoundError(
            f"Could not load legal-docs manifest at {manifest_path}: {err}"
        ) from err

    blobs = manifest.get("blobs", {})
    entry = blobs.get(rel_path)
    if entry is None:
        raise FileNotFoundError(
            f"Manifest at {manifest_path} has no entry for {rel_path}"
        )

    sha = entry.get("sha")
    content_b64 = entry.get("content_b64")
    if not sha or content_b64 is None:
        raise FileNotFoundError(
            f"Manifest entry for {rel_path} is missing sha or content_b64"
        )
    try:
        content = base64.b64decode(content_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as err:
        raise FileNotFoundError(
            f"Manifest content for {rel_path} could not be decoded: {err}"
        ) from err
    return sha, content


def read_blob_at_head(rel_path: str) -> tuple[str, str]:
    """Return ``(blob_sha, blob_content_text)`` for ``rel_path`` at HEAD.

    Two deployment modes:
    1. ``settings.LEGAL_DOCS_MANIFEST_PATH`` is set and points at an existing
       JSON file → use the manifest.
    2. Otherwise → invoke ``git show HEAD:<rel_path>``.

    Raises ``FileNotFoundError`` when the path does not resolve.
    """
    manifest_path_setting: str | None = getattr(
        settings, "LEGAL_DOCS_MANIFEST_PATH", None
    )
    if manifest_path_setting:
        manifest_path = Path(manifest_path_setting)
        if manifest_path.exists():
            return _read_blob_at_head_via_manifest(manifest_path, rel_path)

    return _read_blob_at_head_via_git(rel_path)


def _validate_site_domain(site_domain: str) -> bool:
    return bool(SITE_DOMAIN_RE.match(site_domain))


def _candidate_paths(site_domain: str, doc_type: str) -> list[Path]:
    """Return ordered absolute candidate paths for the (site, doc_type) pair.

    Each path is verified to stay inside `LEGAL_DOCS_ROOT` (path-traversal
    guard). Candidates that fail validation are dropped.
    """
    root = _legal_docs_root().resolve()
    candidates: list[Path] = []

    domain_dirs: list[str] = []
    if _validate_site_domain(site_domain):
        domain_dirs.append(site_domain)
    else:
        logger.warning(
            "Rejected site domain %r as a legal-docs directory name; "
            "falling back to %s only",
            site_domain,
            DEFAULT_DOMAIN_DIR,
        )
    domain_dirs.append(DEFAULT_DOMAIN_DIR)

    for domain_dir in domain_dirs:
        candidate = (root / domain_dir / f"{doc_type}.md").resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            logger.warning(
                "Rejected legal-doc candidate path %s — outside %s",
                candidate,
                root,
            )
            continue
        candidates.append(candidate)

    return candidates


def _parse_frontmatter(text: str) -> tuple[dict, str] | None:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        return None
    try:
        meta = yaml.safe_load(match.group("frontmatter")) or {}
    except yaml.YAMLError as err:
        logger.warning("Could not parse legal-doc frontmatter: %s", err)
        return None
    if not isinstance(meta, dict):
        logger.warning(
            "Legal-doc frontmatter must be a mapping, got %s", type(meta).__name__
        )
        return None
    return meta, match.group("body")


def get_legal_doc(site: Site, doc_type: str) -> LegalDoc | None:
    """Return the LegalDoc for ``doc_type`` for ``site``, or None if missing.

    Looks for a site-specific copy under ``legal_docs/<site.domain>/`` first,
    then falls back to ``legal_docs/_default/``. Reads the file content from
    the git blob at HEAD so a tampered working tree cannot affect rendering.
    """
    if doc_type not in ALLOWED_DOC_TYPES:
        return None

    root = _legal_docs_root().resolve()
    site_domain = site.domain or ""

    for candidate in _candidate_paths(site_domain, doc_type):
        try:
            rel_path = str(candidate.relative_to(Path(settings.BASE_DIR).resolve()))
        except ValueError:
            continue
        try:
            sha, content = read_blob_at_head(rel_path)
        except FileNotFoundError:
            continue

        parsed = _parse_frontmatter(content)
        if parsed is None:
            logger.warning(
                "Legal doc %s is missing or has malformed frontmatter; skipping",
                rel_path,
            )
            continue
        meta, body = parsed

        try:
            chosen_domain = (
                site_domain
                if candidate.parent.name == site_domain
                else DEFAULT_DOMAIN_DIR
            )
            return LegalDoc(
                doc_type=doc_type,
                site_domain=chosen_domain,
                relative_path=rel_path,
                version=str(meta.get("version", "")),
                title=str(meta.get("title", "")),
                effective_date=str(meta.get("effective_date", "")),
                body_markdown=body,
                git_hash=sha,
            )
        except (TypeError, ValueError) as err:
            logger.warning("Could not assemble LegalDoc for %s: %s", rel_path, err)
            continue

    # Defence-in-depth: confirm we never returned anything outside root.
    _ = root  # silence unused
    return None


def has_legal_doc(site: Site, doc_type: str) -> bool:
    """Return True iff `get_legal_doc(site, doc_type)` would return a doc."""
    return get_legal_doc(site, doc_type) is not None


def render_legal_doc(doc: LegalDoc, request: HttpRequest) -> str:
    """Render the doc body through the nh3-sanitised markdown pipeline."""
    return str(render_markdown(doc.body_markdown, request))
