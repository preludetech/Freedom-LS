"""course_access public API.

Re-exports get_course_access_backend for ergonomic imports.
The import is deferred inside the function body to guard against
AppRegistryNotReady at import time (mirrors freedom_ls.icons pattern).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freedom_ls.course_access.backends import CourseAccessBackend


def get_course_access_backend() -> CourseAccessBackend:
    """Re-export: return the active course-access backend (cached).

    Import is deferred to avoid AppRegistryNotReady at module import time.
    See freedom_ls.course_access.loader.get_course_access_backend for the
    real implementation and test cache-clear caveat.
    """
    from freedom_ls.course_access.loader import get_course_access_backend as _get

    return _get()
