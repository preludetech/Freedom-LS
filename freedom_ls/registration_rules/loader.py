"""Loader for the rule-kind classes named by REGISTRATION_RULE_KINDS."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from freedom_ls.registration_rules.config import config

if TYPE_CHECKING:
    from freedom_ls.registration_rules.kinds import AttributeRuleKind


@functools.cache
def get_rule_kind(key: str) -> AttributeRuleKind:
    """The kind class for `key`, instantiated once per process.

    Tests that override REGISTRATION_RULE_KINDS clear this cache; the autouse
    fixture in freedom_ls/conftest.py does it around every test.
    """
    paths = config.REGISTRATION_RULE_KINDS
    if key not in paths:
        raise ImproperlyConfigured(
            f"{key!r} is not a key of REGISTRATION_RULE_KINDS ({sorted(paths)})."
        )
    kind_class: type[AttributeRuleKind] = import_string(paths[key])
    return kind_class()
