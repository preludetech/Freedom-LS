"""The stub-table session fixture must hand the database back blocked.

If it held `django_db_blocker.unblock()` open across its `yield`, every later
test in the whole run could write to the database outside a transaction, and
those rows would leak into unrelated tests until the next flush.
"""

from __future__ import annotations

import pytest

from django.contrib.auth import get_user_model


def test_database_is_blocked_for_a_test_without_the_db_marker() -> None:
    with pytest.raises(RuntimeError, match="Database access not allowed"):
        get_user_model().objects.exists()
