"""Fixtures local to the organisations test suite."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_media_root(settings, tmp_path):
    """Redirect MEDIA_ROOT to a per-test tmp dir.

    Without this, every test that saves a logo writes into the real
    working-tree media/ directory. upload_to keys on a fresh UUID pk, so
    those files are never overwritten and never cleaned up — media/ is
    gitignored, so the growth is invisible until the disk fills up.
    """
    settings.MEDIA_ROOT = tmp_path
