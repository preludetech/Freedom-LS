"""Storage doubles shared across test suites."""

from __future__ import annotations

import contextlib
import os

from django.core.files.base import File
from django.core.files.storage import FileSystemStorage
from django.utils._os import safe_join


class PathlessFileSystemStorage(FileSystemStorage):
    """A FileSystemStorage that refuses `.path()`, the way S3Storage does.

    `Storage.path()` raises NotImplementedError by default and S3Storage does
    not override it, so a read implemented via `FieldFile.path` or
    `storage.path()` passes against a local FileSystemStorage in development
    and breaks in production.

    Everything else stays real, so a render can still complete end to end
    against it -- the same way S3Storage supports open/save/exists/delete
    without ever handing out a local filesystem path. FileSystemStorage's own
    _open/_save/exists/delete/size all resolve the file location by calling
    the public `self.path()`, so simply overriding `path()` to raise would
    break those too; the methods below are reimplemented against the private
    `_real_path()` instead, which is the only thing in this class allowed to
    know where the file actually lives on disk.
    """

    def _real_path(self, name: str) -> str:
        return safe_join(self.location, name)

    def path(self, name: str) -> str:
        raise NotImplementedError(
            "PathlessFileSystemStorage.path() was called -- the code under test used "
            "FieldFile.path or storage.path() instead of the storage API, which breaks "
            "on S3 in production."
        )

    def _open(self, name: str, mode: str = "rb") -> File:
        return File(open(self._real_path(name), mode))

    def _save(self, name: str, content) -> str:
        full_path = self._real_path(name)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as destination:
            for chunk in content.chunks():
                destination.write(chunk)
        return os.path.relpath(full_path, self.location).replace(os.sep, "/")

    def exists(self, name: str) -> bool:
        return os.path.lexists(self._real_path(name))

    def delete(self, name: str) -> None:
        with contextlib.suppress(FileNotFoundError):
            os.remove(self._real_path(name))

    def size(self, name: str) -> int:
        return os.path.getsize(self._real_path(name))
