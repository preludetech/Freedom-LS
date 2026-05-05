import re
from pathlib import Path

_cached_branch: str | None = None
_cache_set: bool = False


def _clear_branch_cache() -> None:
    global _cached_branch, _cache_set
    _cached_branch = None
    _cache_set = False


def get_current_branch(base_dir: Path | None = None) -> str | None:
    global _cached_branch, _cache_set

    if _cache_set:
        return _cached_branch

    if base_dir is None:
        from django.conf import settings

        base_dir = settings.BASE_DIR

    result = _read_branch(base_dir)
    _cached_branch = result
    _cache_set = True
    return result


def get_head_commit(base_dir: Path | None = None) -> str | None:
    """Return the full SHA of the HEAD commit, or None if it can't be read.

    Filesystem-based (no subprocess) so it works in Docker images where the
    `git` binary may be absent. Returns the full 40-character SHA.
    """
    if base_dir is None:
        from django.conf import settings

        base_dir = settings.BASE_DIR

    git_dir = _resolve_git_dir(base_dir)
    if git_dir is None:
        return None

    try:
        head_content = (git_dir / "HEAD").read_text().strip()
    except (FileNotFoundError, OSError):
        return None

    if head_content.startswith("ref: "):
        ref = head_content[len("ref: ") :]
        return _resolve_ref(git_dir, ref)
    return head_content if _looks_like_sha(head_content) else None


def _resolve_git_dir(base_dir: Path) -> Path | None:
    """Return the absolute `.git` directory, following `gitdir:` worktree files."""
    git_path = base_dir / ".git"
    if not git_path.exists():
        return None

    if git_path.is_file():
        content = git_path.read_text().strip()
        if not content.startswith("gitdir:"):
            return None
        git_dir = Path(content.split("gitdir:", 1)[1].strip())
        if not git_dir.is_absolute():
            git_dir = (git_path.parent / git_dir).resolve()
        return git_dir
    return git_path


def _resolve_ref(git_dir: Path, ref: str) -> str | None:
    """Return the SHA for `ref`, checking the loose ref file then packed-refs.

    In a git worktree the per-worktree git dir does not store refs; they live
    in the common git dir, located via the `commondir` pointer file. We try
    the per-worktree dir first (in case a worktree-local ref ever exists)
    then fall back to the common dir.
    """
    for refs_dir in _refs_search_dirs(git_dir):
        sha = _read_loose_ref(refs_dir, ref) or _read_packed_ref(refs_dir, ref)
        if sha is not None:
            return sha
    return None


def _refs_search_dirs(git_dir: Path) -> list[Path]:
    dirs = [git_dir]
    common = _read_commondir(git_dir)
    if common is not None and common != git_dir:
        dirs.append(common)
    return dirs


def _read_commondir(git_dir: Path) -> Path | None:
    try:
        content = (git_dir / "commondir").read_text().strip()
    except (FileNotFoundError, OSError):
        return None
    if not content:
        return None
    common = Path(content)
    if not common.is_absolute():
        common = (git_dir / common).resolve()
    return common


def _read_loose_ref(git_dir: Path, ref: str) -> str | None:
    try:
        sha = (git_dir / ref).read_text().strip()
    except (FileNotFoundError, OSError):
        return None
    return sha if _looks_like_sha(sha) else None


def _read_packed_ref(git_dir: Path, ref: str) -> str | None:
    try:
        lines = (git_dir / "packed-refs").read_text().splitlines()
    except (FileNotFoundError, OSError):
        return None
    for line in lines:
        if not line or line.startswith(("#", "^")):
            continue
        sha_part, _, ref_part = line.partition(" ")
        if ref_part == ref and _looks_like_sha(sha_part):
            return sha_part
    return None


def _looks_like_sha(value: str) -> bool:
    return len(value) == 40 and all(c in "0123456789abcdef" for c in value)


def _read_branch(base_dir: Path) -> str | None:
    git_dir = _resolve_git_dir(base_dir)
    if git_dir is None:
        return None

    try:
        head_content = (git_dir / "HEAD").read_text().strip()
    except (FileNotFoundError, OSError):
        return None

    if head_content.startswith("ref: refs/heads/"):
        return head_content[len("ref: refs/heads/") :]
    return head_content[:7]


def branch_to_db_name(branch: str) -> str:
    """Sanitize a branch name for use as a PostgreSQL database name.

    NOTE: dev_db_init.sh and dev_db_delete.sh mirror this logic in shell.
    If you change the sanitization rules here, update those scripts too.
    """
    sanitized = re.sub(r"[^a-z0-9]", "_", branch.lower())
    sanitized = sanitized[:50]
    return f"db_{sanitized}"
