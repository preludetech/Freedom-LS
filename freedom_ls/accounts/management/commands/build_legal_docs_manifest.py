"""Build a JSON manifest of legal-doc git blob SHAs + content.

Used at build time when the runtime image will not contain a `.git`
directory. Once written, the manifest IS the source of truth: it must be
treated as part of the immutable build artifact (baked into the read-only
image filesystem; never regenerated at runtime). An attacker with write
access to the manifest controls both the content and the recorded hash, so
the V8.1 mitigation is weaker in this mode than in the git-checkout mode.

Usage:

    uv run manage.py build_legal_docs_manifest > legal_docs.manifest.json

…then point ``LEGAL_DOCS_MANIFEST_PATH`` at that file in production settings.
See ``docs/deployment-security-checklist.md`` for the full deploy procedure.
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from freedom_ls.base.git_utils import get_head_commit


def _run_git(base_dir: Path, *args: str) -> str:
    """Run ``git -C base_dir <args>`` and return text stdout."""
    cmd = ["git", "-C", str(base_dir), *args]
    return subprocess.run(  # noqa: S603
        cmd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _read_blob_sha(base_dir: Path, rel_path: str) -> str:
    return _run_git(base_dir, "rev-parse", f"HEAD:{rel_path}").strip()


def _read_blob_bytes(base_dir: Path, rel_path: str) -> bytes:
    """Read content from the git blob (not the working tree) so the recorded
    SHA and the content always match — even if the working tree has
    uncommitted changes.
    """
    cmd = ["git", "-C", str(base_dir), "show", f"HEAD:{rel_path}"]
    return subprocess.run(  # noqa: S603
        cmd,
        check=True,
        capture_output=True,
    ).stdout


class Command(BaseCommand):
    help = (
        "Walk legal_docs/ and emit a JSON manifest of "
        "{path -> {sha, content_b64}} suitable for LEGAL_DOCS_MANIFEST_PATH."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help=("Path to write the manifest to. Defaults to stdout if not supplied."),
        )

    def _collect_blobs(
        self, base_dir: Path, legal_root: Path
    ) -> dict[str, dict[str, str]]:
        blobs: dict[str, dict[str, str]] = {}
        for path in sorted(legal_root.rglob("*.md")):
            rel = str(path.relative_to(base_dir))
            try:
                sha = _read_blob_sha(base_dir, rel)
            except subprocess.CalledProcessError as err:
                self.stderr.write(f"Skipping {rel}: not in HEAD ({err.stderr!r})")
                continue
            try:
                content = _read_blob_bytes(base_dir, rel)
            except subprocess.CalledProcessError as err:
                self.stderr.write(
                    f"Skipping {rel}: could not read blob ({err.stderr!r})"
                )
                continue
            blobs[rel] = {
                "sha": sha,
                "content_b64": base64.b64encode(content).decode("ascii"),
            }
        return blobs

    def _emit(self, serialised: str, output: str | None, blob_count: int) -> None:
        if output:
            Path(output).write_text(serialised, encoding="utf-8")
            self.stdout.write(f"Wrote manifest with {blob_count} blobs to {output}")
        else:
            self.stdout.write(serialised)

    def handle(self, *args: Any, **options: Any) -> None:
        base_dir = Path(settings.BASE_DIR)
        legal_root = base_dir / "legal_docs"
        if not legal_root.is_dir():
            raise CommandError(f"{legal_root} does not exist")

        head_commit = get_head_commit(base_dir)
        if head_commit is None:
            raise CommandError(f"Could not read HEAD commit from {base_dir}/.git")
        blobs = self._collect_blobs(base_dir, legal_root)

        manifest = {"head_commit": head_commit, "blobs": blobs}
        serialised = json.dumps(manifest, indent=2, sort_keys=True)

        self._emit(serialised, options.get("output"), len(blobs))
