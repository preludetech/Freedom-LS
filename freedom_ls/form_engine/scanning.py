"""The seam a deployment plugs a real malware scanner into.

FLS ships no scanner. The default leaves every file PENDING, which is what keeps
an unscanned upload from being mistaken for a cleared one: nothing downstream
serves a file to anyone but its owner until a superuser marks it clean.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Protocol

from django.utils.module_loading import import_string

from .config import config

if TYPE_CHECKING:
    from .models import QuestionAnswerFile


class FileScanner(Protocol):
    """Inspects a stored answer file and sets its scan_status."""

    def scan(self, answer_file: QuestionAnswerFile) -> None: ...


class NoOpScanner:
    """Clears nothing; every file stays PENDING until a superuser marks it."""

    def scan(self, answer_file: QuestionAnswerFile) -> None:
        return None


@functools.cache
def get_file_scanner() -> FileScanner:
    """The configured scanner (cached for the process lifetime).

    Test caveat, as for get_course_access_backend: a test overriding
    FILE_SCAN_BACKEND has to clear this cache, which the autouse fixture in
    form_engine/tests/conftest.py does for every test.
    """
    scanner_class: type[FileScanner] = import_string(config.FILE_SCAN_BACKEND)
    return scanner_class()
