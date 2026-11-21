"""Every uuid in the shipped demo content is written down, so loading it rewrites no file.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

import pytest

from freedom_ls.content_base.schema import BaseBaseContentModel
from freedom_ls.content_engine.management.commands.content_save import missing_uuids

pytestmark = pytest.mark.fls_internal


def test_the_demo_content_has_no_missing_uuid(
    parsed_demo_content: list[BaseBaseContentModel],
) -> None:
    assert missing_uuids(parsed_demo_content) == []
