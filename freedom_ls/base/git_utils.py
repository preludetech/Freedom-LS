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


def _read_branch(base_dir: Path) -> str | None:
    git_path = base_dir / ".git"
    if not git_path.exists():
        return None

    if git_path.is_file():
        content = git_path.read_text().strip()
        if content.startswith("gitdir:"):
            git_dir = Path(content.split("gitdir:", 1)[1].strip())
            if not git_dir.is_absolute():
                git_dir = (git_path.parent / git_dir).resolve()
            head_path = git_dir / "HEAD"
        else:
            return None
    else:
        head_path = git_path / "HEAD"

    try:
        head_content = head_path.read_text().strip()
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
