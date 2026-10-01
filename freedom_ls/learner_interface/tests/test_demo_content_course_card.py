"""The mixed-grid demo article links both demo courses.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
Lives in `learner_interface` because the course card is rendered from there.
"""

from __future__ import annotations

import pytest

from django.conf import settings
from django.urls import reverse

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Article, Course
from freedom_ls.tests.app_guards import app_not_installed

pytestmark = [
    pytest.mark.fls_internal,
    pytest.mark.skipif(
        app_not_installed("freedom_ls.blog"), reason="blog not installed"
    ),
]


@pytest.fixture
def loaded_demo_content(site, mock_site_context) -> None:
    save_content_to_db(settings.BASE_DIR / "demo_content", site.name)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "course_dir",
    ["functionality_demo_price_fixed", "functionality_demo_application_gated"],
)
def test_the_mixed_grid_article_links_each_demo_course(
    site, loaded_demo_content, course_dir
):
    course = Course.objects.get(site=site, file_path=f"{course_dir}/course.md")
    article = Article.objects.get(site=site, slug="getting-started-with-articles")

    rendered = article.rendered_content()

    assert course.title in rendered
    assert (
        reverse("learner_interface:course_detail", kwargs={"course_slug": course.slug})
        in rendered
    )
