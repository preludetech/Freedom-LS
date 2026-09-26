"""Tests for the overlay host blocks in the shared interface shell."""

from __future__ import annotations

from pathlib import Path

import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

BASE_INTERFACE_TEMPLATE: Path = (
    FREEDOM_LS_PACKAGE_DIR / "base" / "templates" / "_base_interface.html"
)


@pytest.mark.django_db
def test_course_player_renders_with_empty_overlay_host_blocks(
    mock_site_context: Site,
) -> None:
    course = CourseFactory(title="Shell Course", slug="shell-course")
    topic = TopicFactory(title="Only Topic", slug="only-topic", content="x")
    course.items.create(child=topic, order=0)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "shell-course", "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200


def test_shell_defines_empty_overlay_host_blocks_outside_the_side_panel() -> None:
    """quick_view_host and modal_host must sit outside #interface-main and the
    sidebar <dialog>, so an overlay they carry survives an htmx swap of
    #main-content."""
    html = BASE_INTERFACE_TEMPLATE.read_text()

    side_panel_grid_index = html.index('class="side-panel-grid')
    interface_main_index = html.index('id="interface-main"')
    quick_view_index = html.index(
        "{% block quick_view_host %}{% endblock quick_view_host %}"
    )
    modal_host_index = html.index("{% block modal_host %}{% endblock modal_host %}")
    end_body_block_index = html.index("{% endblock body %}")

    assert side_panel_grid_index < interface_main_index < quick_view_index
    assert quick_view_index < modal_host_index < end_body_block_index
