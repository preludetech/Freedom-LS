"""Constructors for the stub models and the staff user that panel_framework tests share.

``make_staff_user`` stands in for ``UserFactory`` so this app's tests need no
other FLS app. The stub models are test-only (see ``stub_models.py``) and get
no factory_boy factories, so the ``make_stub*`` helpers play that role.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path
from typing import cast

import lxml.html
import pytest

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.files.storage import FileSystemStorage

from .stub_models import StubChild, StubFileModel, StubModel, StubProtectedChild

_counter = itertools.count(1)


def make_site(name: str, domain: str) -> Site:
    """Create a Site row. The one place framework tests create one."""
    return Site.objects.create(name=name, domain=domain)


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


def make_stub_file(**kwargs: object) -> StubFileModel:
    """Create a StubFileModel for tests. ``name`` defaults to a unique value."""
    kwargs.setdefault("name", f"stub-file-{next(_counter)}")
    return cast(StubFileModel, StubFileModel.objects.create(**kwargs))


def use_temp_file_storage(
    monkeypatch: pytest.MonkeyPatch, location: Path
) -> FileSystemStorage:
    """Point ``StubFileModel.attachment`` at a directory of the test's own.

    A ``FileField`` resolves its storage once at import, so swapping the
    instance bound to the field is what reaches it.
    """
    storage = FileSystemStorage(location=str(location))
    monkeypatch.setattr(StubFileModel._meta.get_field("attachment"), "storage", storage)
    return storage


def normalised_form_markup(html: str) -> str:
    """A form render with the request-error element and the loading-label
    attribute removed, so a render that lacks them can be compared with
    one that has them."""
    root = lxml.html.fromstring(f"<div>{html}</div>")
    for holder in root.xpath("//*[@data-request-error]"):
        holder.drop_tree()
    for span in root.xpath("//*[@data-loading-label]"):
        del span.attrib["data-loading-label"]
    serialised = lxml.html.tostring(root, encoding="unicode")
    return re.sub(r">\s+<", "><", " ".join(serialised.split()))
