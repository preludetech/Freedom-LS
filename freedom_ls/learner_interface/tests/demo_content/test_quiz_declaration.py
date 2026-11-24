"""Starting the shipped declaration demo quiz leads to the declaration page.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_interface.tests.helpers import topic_completion
from freedom_ls.learner_management.tests.helpers import register_user_for_course

pytestmark = pytest.mark.fls_internal

COURSE_TITLE = "Functionality Demo - quiz declaration"


@pytest.mark.django_db
def test_starting_the_first_demo_quiz_redirects_to_its_declaration(
    site: Site,
    loaded_demo_content: Site,
    mock_site_context: object,
    client: Client,
) -> None:
    index = 2
    course = Course.objects.get(title=COURSE_TITLE, site=site)
    user = UserFactory()
    register_user_for_course(course, user)
    topic_completion(
        course, user, course.viewable_items()[0], complete_time=timezone.now()
    )
    client.force_login(user)

    response = client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": index},
        )
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:form_declaration",
        kwargs={"course_slug": course.slug, "index": index},
    )
