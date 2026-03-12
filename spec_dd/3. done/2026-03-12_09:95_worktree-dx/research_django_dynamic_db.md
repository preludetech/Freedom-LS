# Research: Dynamic PostgreSQL Database Selection by Git Branch

## Problem

Each git worktree is checked out on a different branch. All worktrees currently share a single development database (`db`), creating bottlenecks when running migrations, tests, or loading demo content in parallel.

The goal: derive the database name from the current branch automatically in `config/settings_dev.py`.

---

## 1. Detecting the Current Git Branch

### Option A: `subprocess` call

```python
import subprocess

def get_git_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip()
```

**Pros:** Works in all git contexts (worktrees, detached HEAD returns empty string, bare repos). Most reliable.

**Cons:** Requires `git` on PATH. Spawns a subprocess.

Ref: https://git-scm.com/docs/git-branch

### Option B: Read `.git/HEAD` directly

In a normal repo, `.git/HEAD` contains `ref: refs/heads/<branch>`. Parse it:

```python
from pathlib import Path

def get_git_branch() -> str:
    head = Path(__file__).resolve().parents[1] / ".git" / "HEAD"
    content = head.read_text().strip()
    if content.startswith("ref: refs/heads/"):
        return content.removeprefix("ref: refs/heads/")
    return ""  # detached HEAD
```

**Pros:** No subprocess. Fast.

**Cons:** Breaks in worktrees (see section 2 below).

### Option C: Environment variable

Set `GIT_BRANCH` in a shell wrapper or `.env` file and read it:

```python
import os
branch = os.environ.get("GIT_BRANCH", "main")
```

**Pros:** Zero git dependency. Fully explicit.

**Cons:** Requires manual setup per worktree, or a wrapper script. Easy to forget. Defeats the "automatic" goal.

---

## 2. The Worktree Complication

In a git worktree, `.git` is **a file, not a directory**. It contains a pointer like:

```
gitdir: /home/sheena/workspace/lms/freedom-ls-worktrees/worktrees/main
```

This is the case in this project. The `.git` file at the repo root contains:

```
gitdir: /home/sheena/workspace/lms/freedom-ls-worktrees/worktrees/main
```

To read HEAD from a worktree, you must follow the indirection:

```python
from pathlib import Path

def get_git_branch() -> str:
    dot_git = Path(__file__).resolve().parents[1] / ".git"

    if dot_git.is_file():
        # Worktree: .git is a file containing "gitdir: <path>"
        gitdir = Path(dot_git.read_text().strip().removeprefix("gitdir: "))
        if not gitdir.is_absolute():
            gitdir = dot_git.parent / gitdir
        head_file = gitdir / "HEAD"
    else:
        # Normal repo
        head_file = dot_git / "HEAD"

    content = head_file.read_text().strip()
    if content.startswith("ref: refs/heads/"):
        return content.removeprefix("ref: refs/heads/")
    return ""  # detached HEAD
```

**Note:** `git branch --show-current` (Option A) handles worktrees transparently -- no special logic needed. This is a strong argument for the subprocess approach.

Ref: https://git-scm.com/docs/gitrepository-layout (see "gitdir" format)

---

## 3. Performance Considerations

Django settings are loaded **once at process startup** (and once per `manage.py` invocation). This means:

- A `subprocess.run(["git", "branch", ...])` call adds ~10-50ms to startup. Negligible.
- File reads (Option B) are faster (~1ms) but require worktree-aware logic.
- Neither approach has any runtime cost after startup.

**Verdict:** Subprocess is fine. The simplicity and worktree transparency of `git branch --show-current` outweigh the tiny startup cost.

---

## 4. Fallback Strategies

Branch detection can fail if:

- Not inside a git repo (e.g., installed as a package)
- Detached HEAD (branch name is empty)
- `git` binary not found (Option A)
- `.git` file is missing or malformed (Option B)

Recommended fallback pattern:

```python
import subprocess

def get_git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        branch = result.stdout.strip()
        if branch:
            return branch
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


def get_db_name() -> str:
    branch = get_git_branch()
    if not branch:
        return "db"  # default fallback
    # Sanitize: PostgreSQL identifiers allow letters, digits, underscores
    sanitized = branch.replace("/", "_").replace("-", "_").replace(".", "_")
    return f"db_{sanitized}"
```

Key points:

- Always fall back to the default database name (`db`) so settings never crash.
- Sanitize branch names: branches like `feature/foo-bar` become `db_feature_foo_bar`. PostgreSQL database names must be valid identifiers (letters, digits, underscores; max 63 chars).
- Consider truncating long branch names to stay under PostgreSQL's 63-character limit for identifiers.

---

## 5. Example Code for `settings_dev.py`

```python
import subprocess

def _get_branch_db_name() -> str:
    """Derive a database name from the current git branch.

    Falls back to 'db' if branch detection fails.
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        branch = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        branch = ""

    if not branch:
        return "db"

    sanitized = branch.replace("/", "_").replace("-", "_").replace(".", "_")
    return f"db_{sanitized}"[:63]


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "USER": "pguser",
        "NAME": _get_branch_db_name(),
        "PASSWORD": "password",  # pragma: allowlist secret
        "HOST": "127.0.0.1",
        "PORT": "6543",
    },
}
```

This uses the subprocess approach because:

1. It handles worktrees transparently (no special `.git` file parsing)
2. It is a single, well-tested git command
3. The performance cost is negligible at startup
4. It fails gracefully with a sensible default

---

## 6. Database Lifecycle Consideration

The dynamic name means each branch needs its own database created before first use. This pairs with the `dev_db_init.sh` script proposed in the spec, which should:

1. Detect the branch name using the same `git branch --show-current` approach
2. Create the database and test database via `psql` or `createdb`
3. Grant privileges to the dev user

The test database name will follow Django's convention of prepending `test_` to the configured `NAME`, so `db_my_branch` will automatically use `test_db_my_branch` for tests.

---

## Recommendation

Use **Option A (subprocess)** with the fallback pattern from section 4. It is the simplest, most robust approach and handles worktrees without any special-case code.
