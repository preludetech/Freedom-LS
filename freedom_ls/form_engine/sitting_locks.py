"""Whether a sitting still takes answers.

form_engine closes a sitting when it completes. An app built on top of
form_engine can close one for its own reasons too (an application that is no
longer a draft, say) without form_engine importing it: it registers a check
here from its `AppConfig.ready()`.
"""

from collections.abc import Callable

from freedom_ls.form_engine.models import FormProgress

SittingLock = Callable[[FormProgress], bool]

_locks: list[SittingLock] = []


def register_sitting_lock(lock: SittingLock) -> None:
    """Add a check that returns True when a sitting may no longer be changed."""
    if lock not in _locks:
        _locks.append(lock)


def sitting_is_locked(form_progress: FormProgress) -> bool:
    """Whether answers to this sitting may no longer be written."""
    if form_progress.completed_time is not None:
        return True
    return any(lock(form_progress) for lock in _locks)
