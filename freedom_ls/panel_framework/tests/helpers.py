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

from .stub_models import (
    StubChild,
    StubEntry,
    StubEntryProtectedChild,
    StubEntryRestrictedChild,
    StubFileModel,
    StubModel,
    StubProtectedChild,
    StubRestrictedChild,
)

_counter = itertools.count(1)


def make_site(name: str, domain: str) -> Site:
    """Create a Site row. The one place framework tests create one."""
    return Site.objects.create(name=name, domain=domain)


def make_staff_user(site: Site | None = None) -> object:
    """Create a staff user with a unique email. Without ``site`` it requires
    mock_site_context to be active; with one the user is saved on that site, so
    a test that must not fake the ambient site can still have a user."""
    User = get_user_model()
    n = next(_counter)
    if site is not None:
        user = User(email=f"staff{n}@test.local", is_staff=True, site=site)
        user.set_unusable_password()
        user.save()
        return user
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


def make_stub_entry(parent: StubModel, title: str, detail: str = "") -> StubEntry:
    """Create a StubEntry under ``parent``."""
    return cast(
        StubEntry, StubEntry.objects.create(parent=parent, title=title, detail=detail)
    )


def make_stub_entry_protected_child(entry: StubEntry) -> StubEntryProtectedChild:
    """Create a StubEntryProtectedChild, which blocks removal of ``entry``."""
    return cast(
        StubEntryProtectedChild, StubEntryProtectedChild.objects.create(entry=entry)
    )


def make_stub_entry_restricted_child(entry: StubEntry) -> StubEntryRestrictedChild:
    """Create a StubEntryRestrictedChild, which blocks removal of ``entry``."""
    return cast(
        StubEntryRestrictedChild, StubEntryRestrictedChild.objects.create(entry=entry)
    )


def make_stub_restricted_child(parent: StubModel) -> StubRestrictedChild:
    """Create a StubRestrictedChild, which blocks deletion of ``parent``."""
    return cast(StubRestrictedChild, StubRestrictedChild.objects.create(parent=parent))


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
