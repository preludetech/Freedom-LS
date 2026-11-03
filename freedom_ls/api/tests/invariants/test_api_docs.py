"""The Python example in docs/api.md compiles.

Readers copy the example as their starting sync script, so a syntax error in it
is a broken client in someone else's codebase.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

pytestmark = pytest.mark.fls_internal

API_DOCS: Path = FREEDOM_LS_PACKAGE_DIR.parent / "docs" / "api.md"
PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```$", re.DOTALL | re.MULTILINE)


def test_api_docs_python_example_compiles():
    blocks = PYTHON_BLOCK.findall(API_DOCS.read_text())

    assert blocks, f"{API_DOCS} has no python code block"
    for block in blocks:
        compile(block, str(API_DOCS), "exec")
