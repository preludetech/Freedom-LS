"""Loader for the active deadline policy."""

from __future__ import annotations

import functools

from django.utils.module_loading import import_string

from freedom_ls.deadlines.config import config
from freedom_ls.deadlines.policy import DeadlinePolicy


@functools.cache
def get_deadline_policy() -> DeadlinePolicy:
    """The configured policy, instantiated once per process.

    Tests that override DEADLINE_POLICY rely on the autouse fixture in
    freedom_ls/conftest.py clearing this cache before and after each test.
    """
    policy_class: type[DeadlinePolicy] = import_string(config.DEADLINE_POLICY)
    return policy_class()
