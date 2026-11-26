"""The shipped timed demo quiz validates, saves and carries its time limit.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from django.conf import settings
from django.contrib.sites.models import Site

from freedom_ls.content_engine.validate import validate
from freedom_ls.form_engine.models import Form

pytestmark = pytest.mark.fls_internal

DEMO_COURSE = "functionality_demo_quiz_time_limit"
QUIZ_TITLE = "Timed quiz"


def test_the_timed_demo_course_passes_validation() -> None:
    validate(Path(settings.BASE_DIR) / "demo_content")


@pytest.mark.django_db
def test_the_saved_timed_demo_quiz_has_a_ten_minute_limit_and_two_pages(
    site: Site,
    loaded_demo_content: Site,
    mock_site_context: object,
) -> None:
    form = Form.objects.get(title=QUIZ_TITLE, site=site)

    assert (form.time_limit_minutes, form.pages.count()) == (10, 2)
