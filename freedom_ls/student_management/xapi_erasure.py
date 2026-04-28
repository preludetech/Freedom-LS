"""FLS-specific erasure blocker for ``experience_api.erase_actor``.

The ``EXPERIENCE_API_ERASURE_BLOCKERS`` setting is a list of dotted paths
to callables ``(user_id: int) -> bool`` that veto erasure when they
return ``True``. This module provides the canonical blocker:

- :func:`has_active_registrations` — refuses erasure while the user still
  has active :class:`UserCourseRegistration` rows. The concept of "active
  history" is a domain-level concern that has no place in
  ``experience_api``; wiring is via settings (per spec §"Right to
  erasure").
"""

from __future__ import annotations

from freedom_ls.student_management.models import UserCourseRegistration


def has_active_registrations(user_id: int) -> bool:
    """Return True when the user still has active course registrations.

    Used by the ``EXPERIENCE_API_ERASURE_BLOCKERS`` dispatch in
    ``erase_actor``; when it returns True the command refuses to run.
    """
    return UserCourseRegistration.objects.filter(
        user_id=user_id, is_active=True
    ).exists()
