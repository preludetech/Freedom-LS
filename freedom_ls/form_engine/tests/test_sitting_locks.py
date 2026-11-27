from datetime import timedelta

import pytest
import time_machine

from django.contrib.sites.models import Site

from freedom_ls.form_engine import sitting_locks
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.form_engine.sitting_locks import (
    register_sitting_lock,
    sitting_is_locked,
)


@pytest.fixture
def no_registered_locks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sitting_locks, "_locks", [])


@pytest.mark.django_db
def test_an_open_sitting_with_no_locks_is_not_locked(
    mock_site_context: Site, no_registered_locks: None
) -> None:
    form_progress: FormProgress = FormProgressFactory(completed_time=None)

    assert not sitting_is_locked(form_progress)


@pytest.mark.django_db
def test_a_completed_sitting_is_locked(
    mock_site_context: Site, no_registered_locks: None
) -> None:
    form_progress: FormProgress = FormProgressFactory(completed_time=None)
    form_progress.complete()

    assert sitting_is_locked(form_progress)


@pytest.mark.django_db
def test_a_registered_lock_locks_an_open_sitting(
    mock_site_context: Site, no_registered_locks: None
) -> None:
    form_progress: FormProgress = FormProgressFactory(completed_time=None)
    register_sitting_lock(lambda fp: fp.pk == form_progress.pk)

    assert sitting_is_locked(form_progress)


@pytest.mark.django_db
def test_a_lock_registered_twice_is_kept_once(no_registered_locks: None) -> None:
    def lock(form_progress: FormProgress) -> bool:
        return False

    register_sitting_lock(lock)
    register_sitting_lock(lock)

    assert sitting_locks._locks == [lock]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("minutes_in", "locked"), [(30, False), (31, True)], ids=["at_expiry", "expired"]
)
def test_a_timed_sitting_is_locked_once_its_time_has_run_out(
    mock_site_context: Site, no_registered_locks: None, minutes_in: int, locked: bool
) -> None:
    form_progress: FormProgress = FormProgressFactory(
        form=FormFactory(time_limit_minutes=30), completed_time=None
    )

    with time_machine.travel(
        form_progress.start_time + timedelta(minutes=minutes_in), tick=False
    ):
        assert sitting_is_locked(form_progress) is locked
