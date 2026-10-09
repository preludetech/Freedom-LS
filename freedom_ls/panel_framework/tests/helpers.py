"""Constructors for the stub models and the staff user that panel_framework tests share.

``make_staff_user`` stands in for ``UserFactory`` so this app's tests need no
other FLS app. The stub models are test-only (see ``stub_models.py``) and get
no factory_boy factories, so the ``make_stub*`` helpers play that role.
"""

from __future__ import annotations

import itertools
from typing import cast

from django.contrib.auth import get_user_model

from .stub_models import StubChild, StubModel, StubProtectedChild

_counter = itertools.count(1)


def make_staff_user() -> object:
    """Create a staff user with a unique email. Requires mock_site_context active."""
    User = get_user_model()
    n = next(_counter)
    return User.objects.create_user(
        email=f"staff{n}@test.local",
        password="testpass",  # pragma: allowlist secret
        is_staff=True,
    )


def make_stub(name: str | None = None, **kwargs: object) -> StubModel:
    """Create a StubModel for tests. ``name`` defaults to a unique value."""
    if name is None:
        name = f"stub-{next(_counter)}"
    return cast(StubModel, StubModel.objects.create(name=name, **kwargs))


def make_stub_child(parent: StubModel, **kwargs: object) -> StubChild:
    """Create a StubChild parented to ``parent``."""
    return cast(StubChild, StubChild.objects.create(parent=parent, **kwargs))


def make_stub_protected_child(
    parent: StubModel, **kwargs: object
) -> StubProtectedChild:
    """Create a StubProtectedChild, which blocks deletion of ``parent``."""
    return cast(
        StubProtectedChild, StubProtectedChild.objects.create(parent=parent, **kwargs)
    )
