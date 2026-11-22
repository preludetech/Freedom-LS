"""The shipped demo content loads through `content_save` on a clean database.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

import shutil
from pathlib import Path

import pytest

from django.conf import settings as django_settings
from django.contrib.sites.models import Site
from django.core.management import call_command

from freedom_ls.content_engine.models import ContentSave
from freedom_ls.tests.git_repos import commit_all, init_repo
from freedom_ls.tests.site_context import drop_ambient_request

pytestmark = pytest.mark.fls_internal


@pytest.mark.django_db
def test_demo_content_loads_with_no_flag_and_records_one_save(
    site: Site, mock_site_context, settings, tmp_path: Path
) -> None:
    settings.DEBUG = True
    repo_dir = tmp_path / "demo_copy"
    shutil.copytree(Path(django_settings.BASE_DIR) / "demo_content", repo_dir)
    init_repo(repo_dir)
    commit_all(repo_dir)
    drop_ambient_request()

    call_command("content_save", str(repo_dir), site.name, "--traceback")

    assert ContentSave.objects.count() == 1
