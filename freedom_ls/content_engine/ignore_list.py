"""Finding the .fls-content.yaml ignore list that applies to a source path."""

from pathlib import Path

from freedom_ls.base.git_utils import find_repo_root
from freedom_ls.content_engine.validate import read_ignore_list


def ignore_list_for(path: Path) -> frozenset[Path]:
    """The ignore list that applies to a source path: its content repo's, or none outside a repo."""
    root = find_repo_root(path)
    return read_ignore_list(root) if root else frozenset()
