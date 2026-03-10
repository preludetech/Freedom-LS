# Research: Git Branch Detection for Debug Panel

## 1. Methods to Get Git Branch Name

### Option A: Read `.git/HEAD` directly (Recommended)

```python
from pathlib import Path

def get_git_branch(base_dir: Path) -> str | None:
    git_path = base_dir / ".git"

    # Handle worktrees: .git is a file containing "gitdir: /path/to/worktree"
    if git_path.is_file():
        gitdir_line = git_path.read_text().strip()
        if gitdir_line.startswith("gitdir:"):
            gitdir = Path(gitdir_line.split(":", 1)[1].strip())
            head_path = gitdir / "HEAD"
        else:
            return None
    elif git_path.is_dir():
        head_path = git_path / "HEAD"
    else:
        return None

    if not head_path.exists():
        return None

    head_content = head_path.read_text().strip()
    if head_content.startswith("ref: refs/heads/"):
        return head_content.removeprefix("ref: refs/heads/")
    # Detached HEAD - return short SHA
    return head_content[:8]
```

Pros: No dependencies, fast (~0.1ms), no subprocess overhead.
Cons: Must handle worktrees (this project uses them -- `.git` is a file pointing to `/home/sheena/workspace/lms/freedom-ls-worktrees/worktrees/main`).

### Option B: `subprocess.check_output`

```python
import subprocess

def get_git_branch() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
```

Pros: Handles all edge cases (worktrees, detached HEAD, etc.) automatically.
Cons: Subprocess overhead (~5-10ms), requires `git` binary on PATH.

### Option C: `gitpython` library

```python
from git import Repo, InvalidGitRepositoryError

def get_git_branch(base_dir: str) -> str | None:
    try:
        repo = Repo(base_dir)
        return repo.active_branch.name
    except (InvalidGitRepositoryError, TypeError):
        return None
```

Pros: Rich API if you need more than branch name later.
Cons: Heavy dependency for a single function. Adds ~2MB. Overkill here.

### Recommendation

**Option A** (read `.git/HEAD` directly). Zero dependencies, fastest, and we only need the branch name. The worktree handling is a few extra lines but straightforward.

## 2. Performance / Caching

Read the branch name **once at startup** (module-level or in `AppConfig.ready()`), store it in a module-level variable. The branch does not change while the server is running.

```python
# In freedom_ls/base/context_processors.py or a dedicated module
from pathlib import Path
from django.conf import settings

_git_branch: str | None = None
_git_branch_loaded = False

def _load_git_branch() -> str | None:
    # ... file-reading logic from Option A ...
    pass

def get_git_branch() -> str | None:
    global _git_branch, _git_branch_loaded
    if not _git_branch_loaded:
        _git_branch = _load_git_branch()
        _git_branch_loaded = True
    return _git_branch
```

This means zero filesystem reads after the first request.

## 3. Injection Method: Context Processor vs Middleware vs Template Tag

### Current project pattern

The project already uses context processors extensively:

- `freedom_ls.site_aware_models.context_processors.site_config` -- site name/title
- `freedom_ls.accounts.context_processors.signup_policy` -- signup allowed
- `freedom_ls.accounts.context_processors.email_settings` -- email colors
- `freedom_ls.base.context_processors.posthog_config` -- analytics key

All follow the same pattern: a function taking `request`, returning a dict.

### Recommendation: Context Processor

A context processor is the right fit because:
- It matches the existing project pattern exactly
- The data is a simple key-value (branch name string)
- It only needs to be available in templates
- Already have `freedom_ls/base/context_processors.py` with a similar processor (`posthog_config`)

Add a new function to `freedom_ls/base/context_processors.py`:

```python
def debug_info(request: HttpRequest) -> dict[str, str | None]:
    if not settings.DEBUG:
        return {}
    return {"git_branch": get_git_branch()}
```

Register it in `config/settings_base.py` in the `context_processors` list.

**Why not middleware:** Middleware is for modifying request/response flow. We just need a template variable.

**Why not template tag:** Template tags require `{% load %}` in every template. A context processor makes `{{ git_branch }}` available everywhere automatically.

## 4. Handling Missing `.git`

The function should return `None` when:
- `.git` file/directory does not exist (deployed without repo)
- `HEAD` file is missing or unreadable
- Unexpected file format

The context processor returns an empty dict when `DEBUG=False`, so the template variable simply won't exist in production. In templates, use:

```html
{% if git_branch %}
  <div class="...">{{ git_branch }}</div>
{% endif %}
```

No need for a try/except in templates -- Django treats missing variables as empty string by default.

## 5. Conditional Inclusion with DEBUG

Two layers of protection:

1. **Context processor** returns empty dict when `DEBUG=False` (no variable injected at all)
2. **Template** uses `{% if git_branch %}` guard (defensive, handles the `None` case too)

The context processor registration can stay in `settings_base.py` (not just `settings_dev.py`) since the processor itself checks `DEBUG`. This avoids settings-file complexity.

## 6. Where to Display It

The base template is at `freedom_ls/base/templates/_base.html`. All pages extend it (student interface, educator interface, allauth pages).

Add a small fixed-position badge, e.g. bottom-left corner of `<body>`:

```html
{% if git_branch %}
  <div class="fixed bottom-0 left-0 bg-gray-800 text-white text-xs px-2 py-1 rounded-tr opacity-75 z-50 font-mono">
    {{ git_branch }}
  </div>
{% endif %}
```

Place it just before `</body>` in `_base.html`.

## Summary of Proposed Implementation

| Aspect | Decision |
|---|---|
| Detection method | Read `.git/HEAD` directly (with worktree support) |
| Caching | Lazy singleton -- read once, cache in module variable |
| Injection | Context processor in `freedom_ls/base/context_processors.py` |
| Template | Fixed badge in `_base.html`, guarded by `{% if git_branch %}` |
| Production safety | Context processor returns `{}` when `DEBUG=False` |
| No new dependencies | Pure stdlib (`pathlib`) |

### Files to modify

1. `freedom_ls/base/context_processors.py` -- add `debug_info` function with git branch detection
2. `config/settings_base.py` -- register `freedom_ls.base.context_processors.debug_info` in `context_processors`
3. `freedom_ls/base/templates/_base.html` -- add debug badge before `</body>`
