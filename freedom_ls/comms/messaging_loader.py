"""Loader for the active messaging policy."""

from __future__ import annotations

import functools

from django.utils.module_loading import import_string

from freedom_ls.comms.config import config
from freedom_ls.comms.messaging_policy import MessagingPolicy


@functools.cache
def get_messaging_policy() -> MessagingPolicy:
    """The configured policy, instantiated once per process.

    Tests that override MESSAGING_POLICY rely on the autouse fixture in
    freedom_ls/conftest.py clearing this cache before and after each test.
    """
    policy_class: type[MessagingPolicy] = import_string(config.MESSAGING_POLICY)
    return policy_class()
