from pathlib import Path

import pytest

from django.conf import settings

from freedom_ls.content_base.schema import BaseBaseContentModel
from freedom_ls.content_engine.validate import get_all_files, parse_single_file
from freedom_ls.tests.demo_content_fixtures import *  # noqa: F403


@pytest.fixture(scope="module")
def parsed_demo_content() -> list[BaseBaseContentModel]:
    """Every section of every content file under `demo_content/`, parsed."""
    demo_dir = Path(settings.BASE_DIR) / "demo_content"
    return [
        section
        for file_path in get_all_files(demo_dir)
        if file_path.suffix in (".md", ".yaml", ".yml")
        for section in parse_single_file(file_path)
    ]
